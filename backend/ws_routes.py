"""
DuckPools - WebSocket Routes

FastAPI WebSocket endpoint for real-time bet status updates.

SEC-A1: WebSocket authentication via signed session token.
  Clients must obtain a token from POST /ws/auth (with wallet signature)
  and pass it as ?token=<jwt> in the WebSocket URL.

SEC-A2: Connection limits enforced by ConnectionManager.

Endpoints:
  POST /ws/auth              -- Obtain a WebSocket session token
  ws://host/ws/bets/{address}  -- Subscribe to bet events (requires auth token)
  GET /ws/stats              -- WebSocket connection stats

MAT-30: Real-time game history with WebSocket updates
"""

import hashlib
import hmac
import json
import logging
import os
import time
import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException
from pydantic import BaseModel

from ws_manager import ConnectionManager, ConnectionLimitExceeded
from game_events import BetEvent, BetEventType

logger = logging.getLogger("duckpools.ws.routes")

router = APIRouter(tags=["websocket"])

# ─── SEC-A1: Token Configuration ───────────────────────────────

# Shared secret for signing session tokens.
# In production, this should be a dedicated env var. Using BOT_API_KEY as fallback.
WS_TOKEN_SECRET = os.getenv("WS_TOKEN_SECRET", os.getenv("BOT_API_KEY", ""))
WS_TOKEN_MAX_AGE = int(os.getenv("WS_TOKEN_MAX_AGE", "3600"))  # 1 hour default


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


# ─── SEC-A1: Auth Endpoint ─────────────────────────────────────

class WSAuthRequest(BaseModel):
    address: str
    signature: str
    message: str


class WSAuthResponse(BaseModel):
    token: str
    expires_at: int
    warning: Optional[str] = None


@router.post("/ws/auth", response_model=WSAuthResponse)
async def ws_authenticate(request: Request, body: WSAuthRequest):
    """
    SEC-A1: Obtain a WebSocket session token.

    The client must provide:
    - address: Their Ergo address (P2PK, starts with 3 or 9)
    - message: A random challenge string (server-issued or client-generated)
    - signature: HMAC-SHA256 or ProveDlog signature proving address ownership

    For MVP, we accept the signature as-is and bind the token to the address.
    Full Nautilus wallet signature verification will be added when the wallet
    integration layer is complete (depends on frontend wallet adapter).

    Returns a signed token valid for WS_TOKEN_MAX_AGE seconds.
    """
    address = body.address.strip()

    # Basic address validation
    if len(address) < 20 or not address.startswith(("3", "9")):
        raise HTTPException(status_code=400, detail="Invalid Ergo address format")

    if not body.signature:
        raise HTTPException(status_code=400, detail="Signature is required")

    # TODO: When wallet adapter is ready, verify the signature cryptographically
    # against the address's public key. For now, any non-empty signature is accepted
    # as proof-of-concept. This MUST be hardened before mainnet.
    # See: https://github.com/n1ur0/duckpools-coinflip/issues/58

    expires_at = int(time.time()) + WS_TOKEN_MAX_AGE

    logger.info("WS auth token issued for %s (expires %d)", address[:10], expires_at)
    logger.warning(
        "WS auth: signature NOT cryptographically verified (PoC limitation). "
        "Any non-empty signature was accepted. See MAT-335."
    )

    return WSAuthResponse(
        token=_sign_token({
            "sub": address.lower(),
            "iat": int(time.time()),
            "exp": expires_at,
        }),
        expires_at=expires_at,
        warning=(
            "SIGNATURE_NOT_VERIFIED: This is a proof-of-concept implementation. "
            "The provided signature was NOT cryptographically verified against the "
            "address public key. Any non-empty string is accepted as a signature. "
            "This endpoint MUST be hardened with Nautilus wallet signature verification "
            "before any production deployment. See MAT-335."
        ),
    )


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
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="ADMIN_API_KEY environment variable is not configured. "
                   "WebSocket stats endpoint is disabled.",
        )
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing admin API key")
    ws_manager: ConnectionManager = request.app.state.ws_manager
    stats = ws_manager.get_stats()
    return WSStatsResponse(**stats)
