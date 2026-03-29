"""
DuckPools - WebSocket Routes

FastAPI WebSocket endpoint for real-time bet status updates.

SEC-A1: WebSocket authentication via signed session token.
  Two-step challenge-response flow:
  1. POST /ws/challenge  -- Get a cryptographic nonce
  2. POST /ws/auth       -- Sign the challenge with your Ergo wallet, submit proof
  3. ws://host/ws/bets/{address}?token=***  -- Subscribe with the issued token

  Signatures are verified against the Ergo node via /utils/verifySignature.
  If the node is unreachable, auth is REJECTED (fail-closed).

SEC-A2: Connection limits enforced by ConnectionManager.

Endpoints:
  POST /ws/challenge          -- Obtain a cryptographic challenge nonce
  POST /ws/auth               -- Verify signature, obtain session token
  ws://host/ws/bets/{address} -- Subscribe to bet events (requires auth token)
  GET /ws/stats               -- WebSocket connection stats

MAT-30: Real-time game history with WebSocket updates
MAT-335: Fix - WebSocket auth now verifies signatures via Ergo node
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Optional

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException
from pydantic import BaseModel, field_validator

from ws_manager import ConnectionManager, ConnectionLimitExceeded
from game_events import BetEvent, BetEventType

logger = logging.getLogger("duckpools.ws.routes")

router = APIRouter(tags=["websocket"])

# ─── SEC-A1: Token Configuration ───────────────────────────────

# Shared secret for signing session tokens.
# In production, this should be a dedicated env var. Using BOT_API_KEY as fallback.
WS_TOKEN_SECRET = os.getenv("WS_TOKEN_SECRET", os.getenv("BOT_API_KEY", ""))
WS_TOKEN_MAX_AGE = int(os.getenv("WS_TOKEN_MAX_AGE", "3600"))  # 1 hour default

# Ergo node URL for signature verification
NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")

# Challenge nonce configuration
CHALLENGE_TTL_SECONDS = 300  # 5 minutes to respond to a challenge
MAX_PENDING_CHALLENGES = 10000  # Prevent memory exhaustion from challenge spam


def _sign_token(payload: dict) -> str:
    """
    Create an HMAC-SHA256 signed token.
    Format: base64url(json_payload).base64url(hmac_signature)
    """
    import base64
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(WS_TOKEN_SECRET.encode(), payload_bytes, hashlib.sha256).digest()
    return (
        base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
        + "."
        + base64.urlsafe_b64encode(sig).decode().rstrip("=")
    )


def _verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode an HMAC-SHA256 signed token.
    Returns payload dict if valid, None if expired or tampered.
    """
    import base64
    if not WS_TOKEN_SECRET:
        logger.error("WS_TOKEN_SECRET not configured — WebSocket auth disabled")
        return None

    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        # Add padding back
        payload_b64 = parts[0] + "=" * (4 - len(parts[0]) % 4)
        sig_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        expected_sig = base64.urlsafe_b64decode(sig_b64)
        actual_sig = hmac.new(
            WS_TOKEN_SECRET.encode(), payload_bytes, hashlib.sha256
        ).digest()

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(payload_bytes)

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None

        return payload

    except Exception as e:
        logger.warning("Token verification failed: %s", e)
        return None


# ─── SEC-A1: Challenge Store ──────────────────────────────────
# Server-side store for pending auth challenges.
# Key: challenge nonce, Value: (address, created_at)
_pending_challenges: dict[str, tuple[str, float]] = {}
_challenge_lock = asyncio.Lock()


def _purge_expired_challenges() -> None:
    """Remove expired challenges from the store."""
    now = time.time()
    expired = [nonce for nonce, (_, created) in _pending_challenges.items()
               if now - created > CHALLENGE_TTL_SECONDS]
    for nonce in expired:
        del _pending_challenges[nonce]
    if expired:
        logger.debug("Purged %d expired auth challenges", len(expired))


async def _create_challenge(address: str) -> str:
    """
    Generate a cryptographic challenge nonce and store it.
    The client must sign this nonce with their Ergo wallet key.
    """
    async with _challenge_lock:
        # Prevent memory exhaustion
        if len(_pending_challenges) >= MAX_PENDING_CHALLENGES:
            _purge_expired_challenges()
            if len(_pending_challenges) >= MAX_PENDING_CHALLENGES:
                raise HTTPException(
                    status_code=429,
                    detail="Too many pending challenges. Please wait."
                )

        nonce = secrets.token_hex(32)
        _pending_challenges[nonce] = (address.lower(), time.time())
        return nonce


async def _consume_challenge(nonce: str, expected_address: str) -> bool:
    """
    Validate and consume a challenge nonce.
    Returns True if the nonce is valid and matches the expected address.
    """
    async with _challenge_lock:
        entry = _pending_challenges.pop(nonce, None)
        if entry is None:
            return False

        stored_address, created_at = entry

        # Check expiry
        if time.time() - created_at > CHALLENGE_TTL_SECONDS:
            return False

        # Verify address matches
        if stored_address != expected_address.lower():
            return False

        return True


# ─── SEC-A1: Ergo Node Signature Verification ──────────────────

async def _verify_ergo_signature(
    address: str,
    message: str,
    signature: str,
) -> bool:
    """
    Verify a ProveDlog signature against the Ergo node.

    Uses the node's /utils/verifySignature endpoint which checks
    that the signature was produced by the private key corresponding
    to the given address over the given message.

    Returns True if the node confirms the signature is valid.
    Returns False if verification fails or the node is unreachable.

    MAT-335: This is the critical fix — we no longer accept any non-empty
    signature. Every auth request is cryptographically verified.
    """
    try:
        headers = {}
        if NODE_API_KEY:
            headers["api_key"] = NODE_API_KEY

        payload = {
            "message": message,
            "signature": signature,
            "address": address,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{NODE_URL}/utils/verifySignature",
                json=payload,
                headers=headers,
            )

        if response.status_code == 200:
            result = response.json()
            verified = result.get("result", False)
            if verified:
                logger.info(
                    "Signature verified for %s via Ergo node",
                    address[:10],
                )
                return True
            else:
                logger.warning(
                    "Signature REJECTED for %s — node returned false",
                    address[:10],
                )
                return False
        else:
            logger.error(
                "Ergo node returned HTTP %d during signature verification: %s",
                response.status_code,
                response.text[:200],
            )
            return False

    except httpx.TimeoutException:
        logger.error(
            "Ergo node timed out during signature verification — "
            "rejecting auth (fail-closed)"
        )
        return False
    except httpx.ConnectError:
        logger.error(
            "Cannot connect to Ergo node for signature verification — "
            "rejecting auth (fail-closed)"
        )
        return False
    except Exception as e:
        logger.error(
            "Unexpected error during signature verification: %s — "
            "rejecting auth (fail-closed)", e
        )
        return False


# ─── SEC-A1: Auth Endpoints ────────────────────────────────────

class ChallengeRequest(BaseModel):
    address: str

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 26 or len(v) > 60:
            raise ValueError("Invalid Ergo address length")
        if not v.startswith(("3", "9")):
            raise ValueError("Ergo address must start with 3 (mainnet) or 9 (testnet)")
        return v


class ChallengeResponse(BaseModel):
    challenge: str
    address: str
    expires_at: int


class WSAuthRequest(BaseModel):
    address: str
    signature: str
    challenge: str

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 26 or len(v) > 60:
            raise ValueError("Invalid Ergo address length")
        if not v.startswith(("3", "9")):
            raise ValueError("Ergo address must start with 3 (mainnet) or 9 (testnet)")
        return v

    @field_validator("signature")
    @classmethod
    def validate_signature(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Signature is required and must be non-empty")
        v = v.strip()
        # ProveDlog signatures are Base16-encoded, reasonable length check
        if len(v) < 10 or len(v) > 10000:
            raise ValueError("Signature has invalid length")
        return v

    @field_validator("challenge")
    @classmethod
    def validate_challenge(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Challenge nonce is required")
        v = v.strip()
        # Our challenges are 64-char hex (secrets.token_hex(32))
        if len(v) != 64:
            raise ValueError("Invalid challenge nonce length")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Challenge nonce must be valid hex")
        return v


class WSAuthResponse(BaseModel):
    token: str
    expires_at: int


@router.post("/ws/challenge", response_model=ChallengeResponse)
async def ws_challenge(body: ChallengeRequest):
    """
    SEC-A1 Step 1: Request a cryptographic challenge.

    The client provides their Ergo address and receives a unique
    challenge nonce. They must sign this nonce with their wallet
    and submit the signature to /ws/auth.

    The challenge expires after CHALLENGE_TTL_SECONDS (default: 5 minutes).
    """
    address = body.address.strip()

    # Purge expired challenges opportunistically
    async with _challenge_lock:
        _purge_expired_challenges()

    challenge = await _create_challenge(address)

    return ChallengeResponse(
        challenge=challenge,
        address=address.lower(),
        expires_at=int(time.time()) + CHALLENGE_TTL_SECONDS,
    )


@router.post("/ws/auth", response_model=WSAuthResponse)
async def ws_authenticate(request: Request, body: WSAuthRequest):
    """
    SEC-A1 Step 2: Verify signature and obtain a WebSocket session token.

    The client must provide:
    - address: Their Ergo address (P2PK, starts with 3 or 9)
    - challenge: The nonce obtained from POST /ws/challenge
    - signature: ProveDlog signature proving ownership of the address,
                 signing the challenge string

    The signature is verified against the Ergo node's /utils/verifySignature.
    If the node is unreachable, authentication is REJECTED (fail-closed).

    MAT-335: This endpoint previously accepted any non-empty signature,
    allowing impersonation of any Ergo address. Now requires cryptographic
    proof of address ownership.

    Returns a signed token valid for WS_TOKEN_MAX_AGE seconds.
    """
    address = body.address.strip()

    # Step 1: Validate and consume the challenge nonce
    challenge_valid = await _consume_challenge(body.challenge, address)
    if not challenge_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid, expired, or already-used challenge. "
                   "Request a new challenge from POST /ws/challenge.",
        )

    # Step 2: Verify the signature cryptographically via Ergo node
    # The message to sign is the challenge nonce itself
    signature_valid = await _verify_ergo_signature(
        address=address,
        message=body.challenge,
        signature=body.signature,
    )

    if not signature_valid:
        logger.warning(
            "WS auth REJECTED for %s — signature verification failed",
            address[:10],
        )
        raise HTTPException(
            status_code=401,
            detail="Signature verification failed. The signature does not "
                   "match the provided address and challenge.",
        )

    # Step 3: Issue session token
    expires_at = int(time.time()) + WS_TOKEN_MAX_AGE
    token = _sign_token({
        "sub": address.lower(),
        "iat": int(time.time()),
        "exp": expires_at,
    })

    logger.info("WS auth token issued for %s (expires %d)", address[:10], expires_at)

    return WSAuthResponse(token=token, expires_at=expires_at)


# ─── WebSocket Endpoint ────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxied connections."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.websocket("/ws/bets/{address}")
async def ws_bet_subscription(websocket: WebSocket, address: str):
    """
    WebSocket endpoint for real-time bet updates.

    SEC-A1: Requires a valid auth token via ?token= query parameter.
    SEC-A2: Enforces connection limits per-IP and globally.

    Client connects with: ws://host/ws/bets/{ergo_address}?token=<signed_token>

    The client will receive JSON events for all bets involving the given
    address. Events follow the BetEvent schema:

    {
        "type": "bet_placed|bet_revealed|bet_settled|bet_refunded|pool_state_update",
        "timestamp": 1711584000.0,
        "bet_id": "abc123...",
        "player_address": "3W...",
        "payload": { ... event-specific data ... }
    }

    The server sends periodic ping frames (every 30s). Clients should
    respond to keep the connection alive. If no pong is received, the
    connection will be closed after 60s.

    To subscribe to additional addresses after connecting, send a JSON message:
    {"action": "subscribe", "address": "3W..."}
    {"action": "unsubscribe", "address": "3W..."}
    """
    ws_manager: ConnectionManager = websocket.app.state.ws_manager

    # ── SEC-A1: Authenticate via token ──────────────────────────
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="Missing auth token. POST /ws/auth to obtain one.")
        return

    payload = _verify_token(token)
    if not payload:
        await websocket.close(code=4003, reason="Invalid or expired auth token.")
        return

    # The token's subject (sub) is the authenticated address
    authenticated_address = payload["sub"]

    # ── Validate path address matches token ─────────────────────
    address = address.strip().lower()
    if address != authenticated_address:
        await websocket.close(
            code=4003,
            reason=f"Token address mismatch. Token is for {authenticated_address[:10]}..., "
                   f"but path specifies {address[:10]}..."
        )
        return

    # ── SEC-A2: Enforce connection limits ───────────────────────
    client_ip = _get_client_ip(websocket)

    try:
        conn_id = await ws_manager.connect(websocket, client_ip)
    except ConnectionLimitExceeded as e:
        logger.warning("WS connection rejected from %s: %s", client_ip, e)
        await websocket.close(code=4029, reason=str(e))
        return

    # SEC-A1: Lock this connection to the authenticated address
    ws_manager.set_owner(conn_id, authenticated_address)

    try:
        await ws_manager.subscribe(conn_id, address, websocket)
    except ConnectionLimitExceeded as e:
        logger.warning("WS subscription rejected for conn %d: %s", conn_id, e)
        await ws_manager.disconnect(conn_id)
        await websocket.close(code=4029, reason=str(e))
        return

    logger.info("WS connection %d authenticated for %s from %s", conn_id, address, client_ip)

    # Send confirmation
    await websocket.send_json({
        "type": "subscribed",
        "address": address,
        "conn_id": conn_id,
        "message": f"Authenticated and subscribed to bet events for {address[:10]}...{address[-6:]}",
    })

    # Track active subscriptions for this connection
    subscribed_addresses = {address}

    try:
        # Background ping task
        async def ping_loop():
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

        ping_task = asyncio.create_task(ping_loop())

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    action = msg.get("action", "")

                    if action == "subscribe":
                        new_addr = msg.get("address", "").strip().lower()
                        if not new_addr or len(new_addr) < 20:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Invalid address for subscription",
                            })
                            continue

                        # SEC-A1: Only allow subscribing to the authenticated address
                        if new_addr != authenticated_address:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Cannot subscribe to other addresses. "
                                           f"This connection is locked to {authenticated_address[:10]}...",
                            })
                            continue

                        try:
                            await ws_manager.subscribe(conn_id, new_addr, websocket)
                            subscribed_addresses.add(new_addr)
                            await websocket.send_json({
                                "type": "subscribed",
                                "address": new_addr,
                                "message": f"Subscribed to {new_addr[:10]}...{new_addr[-6:]}",
                            })
                        except ConnectionLimitExceeded as e:
                            await websocket.send_json({
                                "type": "error",
                                "message": str(e),
                            })

                    elif action == "unsubscribe":
                        old_addr = msg.get("address", "")
                        if old_addr:
                            await ws_manager.unsubscribe(conn_id, old_addr)
                            subscribed_addresses.discard(old_addr)
                            await websocket.send_json({
                                "type": "unsubscribed",
                                "address": old_addr,
                            })

                    elif action == "ping":
                        await websocket.send_json({"type": "pong"})

                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown action: {action}",
                        })

                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })

        finally:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info("WS client %d disconnected normally", conn_id)
    except Exception as e:
        logger.error("WS error for conn %d: %s", conn_id, e)
    finally:
        for addr in subscribed_addresses:
            await ws_manager.unsubscribe(conn_id, addr)
        await ws_manager.disconnect(conn_id)


# ─── REST Stats Endpoint ────────────────────────────────────────

class WSStatsResponse(BaseModel):
    active_connections: int
    subscriptions_count: int
    tracked_addresses: int
    limits: dict
    unique_ips: int


@router.get("/ws/stats", response_model=WSStatsResponse)
async def ws_stats(request: Request):
    """Get WebSocket connection manager statistics. Requires admin API key."""
    import os
    api_key = request.headers.get("X-Api-Key", "")
    expected = os.getenv("ADMIN_API_KEY", "")
    if not expected or not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Admin API key required")
    ws_manager: ConnectionManager = request.app.state.ws_manager
    stats = ws_manager.get_stats()
    return WSStatsResponse(**stats)
