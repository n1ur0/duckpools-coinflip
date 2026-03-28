"""
DuckPools - Bet API Routes

FastAPI endpoints for coinflip bet operations:
- Place a bet (commit phase)
- Build reveal transaction
- Bet history queries
- Pool state queries for betting

MAT-168: Input validation on /place-bet (negative amount fix)
"""

import hashlib
import hmac
import logging
import os
import time
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from game_history import BetRecord, GameHistoryService
from rate_limit import limiter  # Shared limiter instance (SECURITY: prevents dual-limiter bypass)

logger = logging.getLogger("duckpools.bet.routes")

router = APIRouter(tags=["bet"])


# ─── Constants ────────────────────────────────────────────────────

MIN_BET_NANOERG = 1_000_000            # 0.001 ERG minimum bet
MAX_BET_NANOERG = 100_000_000_000_000   # 100,000 ERG maximum bet
NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", os.getenv("API_KEY", "hello"))
BOT_API_KEY = os.getenv("BOT_API_KEY", "")  # SECURITY: Must be explicitly set in production
COINFLIP_NFT_ID = os.getenv("COINFLIP_NFT_ID", "")

# SECURITY: Validate BOT_API_KEY is set (not just falling back to NODE_API_KEY)
if not os.getenv("BOT_API_KEY"):
    logger.warning(
        "BOT_API_KEY not set - bot endpoint auth falls back to NODE_API_KEY. "
        "This violates least-privilege. Set BOT_API_KEY in .env before production."
    )



# ─── Request/Response Models ──────────────────────────────────────

class PlaceBetRequest(BaseModel):
    """Request body for placing a bet."""
    player_address: str = Field(
        ...,
        min_length=20,
        description="Player's Ergo address (P2PK or P2S)",
    )
    amount_nanoerg: int = Field(
        ...,
        gt=0,
        le=MAX_BET_NANOERG,
        description="Bet amount in nanoERG. Must be positive, min 0.001 ERG.",
    )
    choice: int = Field(
        ...,
        ge=0,
        le=1,
        description="Bet choice: 0 = heads, 1 = tails",
    )
    commitment: Optional[str] = Field(
        None,
        min_length=64,
        max_length=64,
        description="32-byte commitment hash (hex, 64 chars). If omitted, server generates one.",
    )

    @field_validator("amount_nanoerg")
    @classmethod
    def validate_min_bet(cls, v: int) -> int:
        if v < MIN_BET_NANOERG:
            raise ValueError(
                f"Bet amount too small: {v} nanoERG. Minimum is {MIN_BET_NANOERG} nanoERG (0.001 ERG)"
            )
        return v

    @field_validator("player_address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Player address cannot be empty")
        # Basic Ergo address validation: starts with 3 or 9
        if v[0] not in ("3", "9"):
            raise ValueError(f"Invalid Ergo address: must start with '3' or '9', got '{v[0]}'")
        if len(v) < 30:
            raise ValueError(f"Address too short: {len(v)} chars")
        return v


class PlaceBetResponse(BaseModel):
    """Response for a successful bet placement."""
    tx_id: str = Field(..., description="Transaction ID")
    bet_id: str = Field(..., description="Unique bet identifier (commitment hash)")
    bet_amount_nanoerg: int = Field(..., description="Bet amount in nanoERG")
    bet_amount_erg: str = Field(..., description="Bet amount in ERG (human-readable)")
    choice: int = Field(..., description="Bet choice: 0=heads, 1=tails")
    choice_label: str = Field(..., description="Human-readable choice label")
    player_address: str = Field(..., description="Player's Ergo address")
    status: str = Field("pending", description="Current bet status")
    message: str = Field(..., description="Status message")


class GamesCountResponse(BaseModel):
    """Response for total games count."""
    total_games: int = Field(..., description="Total number of games played")


class ScriptsResponse(BaseModel):
    """Response for contract scripts."""
    pending_bet_script: str = Field("", description="Hex-encoded PendingBet ErgoTree")
    house_script: str = Field("", description="Hex-encoded house payout ErgoTree")


class CommitmentResponse(BaseModel):
    """Response for server RNG commitment."""
    commitment: str = Field(..., description="Server commitment hash (hex)")
    block_height: int = Field(..., description="Block height at commitment time")
    message: str = Field("", description="Status message")


class PendingBoxResponse(BaseModel):
    """Response for pending box search."""
    box_id: Optional[str] = Field(None, description="Box ID if found")
    found: bool = Field(..., description="Whether a box was found")


class ExpiredBetsResponse(BaseModel):
    """Response for expired bets list."""
    expired_bets: list = Field(default_factory=list, description="List of expired bet boxes")
    total: int = Field(0, description="Total expired bets found")


class RevealTxRequest(BaseModel):
    """Request body for building a reveal transaction."""
    box_id: str = Field(..., min_length=1, description="Pending bet box ID")
    player_secret: int = Field(..., ge=0, description="Player's random secret (R7)")
    block_hash: str = Field(..., min_length=1, description="Block hash for RNG")


class RefundTxRequest(BaseModel):
    """Request body for building a refund transaction."""
    box_id: str = Field(..., min_length=1, description="Expired bet box ID")


class ResolveBetRequest(BaseModel):
    """Request body for resolving a bet (bot-only)."""
    bet_id: str = Field(..., min_length=1, description="Bet identifier")
    player_secret: int = Field(..., ge=0, description="Player's random secret")
    block_hash: str = Field(..., min_length=1, description="Block hash for RNG")
    player_address: str = Field(..., min_length=1, description="Player's Ergo address")
    outcome: str = Field(..., pattern="^(win|lose)$", description="Bet outcome")
    payout_nanoerg: int = Field(..., ge=0, description="Payout amount in nanoERG")


class RevealBetRequest(BaseModel):
    """Request body for revealing a bet (bot-only)."""
    box_id: str = Field(..., min_length=1, description="Pending bet box ID")
    player_secret: int = Field(..., ge=0, description="Player's random secret (R7)")
    block_hash: str = Field(..., min_length=1, description="Block hash for RNG")


class PoolDepositRequest(BaseModel):
    """Request body for depositing ERG into the house pool."""
    amount_nanoerg: int = Field(..., gt=0, description="Deposit amount in nanoERG")


class PoolWithdrawRequest(BaseModel):
    """Request body for withdrawing ERG from the house pool."""
    amount_nanoerg: int = Field(..., gt=0, description="Withdraw amount in nanoERG")


class PlayerStatsResponse(BaseModel):
    """Response for player statistics."""
    address: str = Field(..., description="Player's Ergo address")
    total_bets: int = Field(..., description="Total bets placed")
    wins: int = Field(..., description="Number of wins")
    losses: int = Field(..., description="Number of losses")
    win_rate: float = Field(..., description="Win rate as decimal (0.0-1.0)")
    total_wagered_nanoerg: int = Field(..., description="Total amount wagered (nanoERG)")
    total_wagered_erg: str = Field(..., description="Total amount wagered (ERG)")
    total_won_nanoerg: int = Field(..., description="Total amount won (nanoERG)")
    total_won_erg: str = Field(..., description="Total amount won (ERG)")
    net_profit_nanoerg: int = Field(..., description="Net profit/loss (nanoERG)")
    net_profit_erg: str = Field(..., description="Net profit/loss (ERG)")


class LeaderboardResponse(BaseModel):
    """Response for top players leaderboard."""
    leaderboard: list = Field(default_factory=list, description="Top players sorted by profit")
    total: int = Field(0, description="Total players with history")


class PlayerCompResponse(BaseModel):
    """Response for player compensation points."""
    address: str = Field(..., description="Player's Ergo address")
    comp_points: int = Field(..., description="Compensation points earned")
    tier: str = Field(..., description="Player tier (bronze/silver/gold/platinum)")


class BetHistoryResponse(BaseModel):
    """Response for bet history query."""
    address: str
    bets: List[dict]
    total: int


class PoolStateResponse(BaseModel):
    """Pool state for betting."""
    liquidity_nanoerg: int
    liquidity_erg: str
    house_edge_bps: int
    min_bet_nanoerg: int
    max_bet_nanoerg: int
    total_games: int


class BetTimeoutInfo(BaseModel):
    """Timeout info for a bet box."""
    box_id: str
    current_height: int
    timeout_height: int
    blocks_remaining: int
    is_expired: bool


class FindPendingBoxRequest(BaseModel):
    tx_id: Optional[str] = None
    bet_id: Optional[str] = None


class BetErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────

def nano_to_erg(nano: int) -> str:
    """Format nanoERG as human-readable ERG string."""
    return f"{nano / 1e9:.9f}"


def get_node_headers() -> dict:
    """Get headers for node API requests."""
    return {"api_key": NODE_API_KEY, "Content-Type": "application/json"}


async def _node_get(path: str, timeout: float = 10.0) -> dict:
    """GET request to Ergo node."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{NODE_URL}{path}", headers=get_node_headers())
        resp.raise_for_status()
        return resp.json()


async def _node_post(path: str, json_data: dict, timeout: float = 30.0) -> dict:
    """POST request to Ergo node."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{NODE_URL}{path}", headers=get_node_headers(), json=json_data)
        resp.raise_for_status()
        return resp.json()


def generate_commitment(secret: bytes, choice: int) -> str:
    """Generate commitment hash: SHA256(secret || choice_byte)."""
    choice_byte = bytes([choice])
    digest = hashlib.sha256(secret + choice_byte).digest()
    return digest.hex()


# ─── Endpoints ────────────────────────────────────────────────────

@router.post("/place-bet", response_model=PlaceBetResponse, responses={400: {"model": BetErrorResponse}, 429: {"model": BetErrorResponse}})
@limiter.limit("5/minute")
async def place_bet(request: Request, body: PlaceBetRequest):
    """
    Place a coinflip bet via the backend wallet.

    The backend holds the house wallet and signs transactions on behalf of
    the protocol. Player provides their address, amount, and choice.

    Validation:
    - amount_nanoerg must be > 0 (at least MIN_BET_NANOERG)
    - amount_nanoerg must be <= MAX_BET_NANOERG
    - choice must be 0 (heads) or 1 (tails)
    - player_address must be a valid Ergo address

    Returns transaction ID and bet ID after successful on-chain submission.
    """
    logger.info(
        "place_bet request: address=%s amount=%s choice=%s",
        body.player_address[:10] + "...",
        body.amount_nanoerg,
        body.choice,
    )

    # Check node connectivity
    try:
        info = await _node_get("/info")
        current_height = info.get("fullHeight", 0)
    except httpx.HTTPError as e:
        logger.error("Node unreachable: %s", e)
        raise HTTPException(status_code=503, detail=f"Ergo node unreachable: {e}")

    # If no commitment provided, generate one
    if body.commitment is None:
        # Generate a random 8-byte secret
        import secrets
        secret = secrets.token_bytes(8)
        body.commitment = generate_commitment(secret, body.choice)

    # TODO: Build the actual PendingBet transaction with proper ErgoScript
    # For now, validate inputs and return a structured error indicating
    # the bet placement pipeline needs the off-chain bot integration.

    # The real implementation would:
    # 1. Build a tx with the PendingBet contract as output
    # 2. Set registers R4=player_tree, R5=commitment, R6=choice, R7=secret, R8=bet_id
    # 3. Include the Coinflip NFT in the box
    # 4. Sign and submit via node wallet

    logger.warning(
        "place_bet: full transaction building not yet implemented. "
        "Returning validation pass with placeholder tx_id."
    )

    bet_id = body.commitment
    choice_label = "heads" if body.choice == 0 else "tails"

    # Record bet in history service
    game_history: GameHistoryService = request.app.state.game_history
    record = BetRecord(
        bet_id=bet_id,
        tx_id="pending_implementation",
        box_id="",
        player_address=body.player_address,
        choice=body.choice,
        bet_amount_nanoerg=body.amount_nanoerg,
        outcome="pending",
        block_height=current_height,
        commitment=body.commitment,
    )
    game_history.add_bet(record)

    return PlaceBetResponse(
        tx_id="pending_implementation",
        bet_id=bet_id,
        bet_amount_nanoerg=body.amount_nanoerg,
        bet_amount_erg=nano_to_erg(body.amount_nanoerg),
        choice=body.choice,
        choice_label=choice_label,
        player_address=body.player_address,
        status="pending",
        message="Bet validated successfully. Full on-chain submission pending integration.",
    )


@router.get("/pool/state", response_model=PoolStateResponse)
async def get_pool_state(request: Request):
    """Get current pool state for betting (liquidity, house edge, limits)."""
    try:
        info = await _node_get("/info")
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Ergo node unreachable")

    # Try to get wallet balance as proxy for pool liquidity
    try:
        balances = await _node_get("/wallet/balances")
        liquidity = balances.get("balance", 0)
    except httpx.HTTPError:
        liquidity = 0

    game_history = request.app.state.game_history
    return PoolStateResponse(
        liquidity_nanoerg=liquidity,
        liquidity_erg=nano_to_erg(liquidity),
        house_edge_bps=300,
        min_bet_nanoerg=MIN_BET_NANOERG,
        max_bet_nanoerg=MAX_BET_NANOERG,
        total_games=game_history.get_stats()["total_games"],
    )


@router.get("/pool/games-count", response_model=GamesCountResponse)
async def get_games_count(request: Request):
    """Get total number of games played."""
    game_history = request.app.state.game_history
    stats = game_history.get_stats()
    return {"total_games": stats["total_games"]}


@router.get("/scripts", response_model=ScriptsResponse)
async def get_scripts(request: Request):
    """Get PendingBet and house ErgoTree scripts."""
    # TODO: return actual script hashes from config
    return {
        "pending_bet_script": os.getenv("PENDING_BET_SCRIPT", ""),
        "house_script": "",
    }


@router.get("/history/{address:path}", response_model=BetHistoryResponse)
async def get_bet_history(request: Request, address: str, limit: int = Query(default=50, ge=1, le=200)):
    """Get bet history for an address."""
    game_history = request.app.state.game_history
    bets = game_history.get_history(address, limit=limit)
    total = game_history.get_history_count(address)
    return BetHistoryResponse(address=address, bets=bets, total=total)


@router.get("/commitment", response_model=CommitmentResponse)
async def get_server_commitment(request: Request):
    """Get server's RNG commitment for fairness verification."""
    # TODO: implement proper server commitment protocol
    return {
        "commitment": "",
        "block_height": 0,
        "message": "Server commitment not yet implemented",
    }


@router.get("/find-pending-box", response_model=PendingBoxResponse, responses={400: {"model": BetErrorResponse}})
async def find_pending_box(tx_id: Optional[str] = None, bet_id: Optional[str] = None):
    """Find a pending bet box by transaction ID or bet ID."""
    if not tx_id and not bet_id:
        raise HTTPException(status_code=400, detail="Must provide tx_id or bet_id")

    # TODO: implement box search via node API
    return {"box_id": None, "found": False}


@router.get("/bet/timeout-info")
async def get_bet_timeout_info(box_id: str = Query(..., min_length=1)):
    """Get timeout info for a pending bet box."""
    try:
        box = await _node_get(f"/blockchain/box/byId/{box_id}")
        info = await _node_get("/info")
        current_height = info.get("fullHeight", 0)

        # R9 should hold the timeout height
        registers = box.get("additionalRegisters", {})
        timeout_reg = registers.get("R9", {}).get("renderedValue", "0")
        try:
            timeout_height = int(timeout_reg)
        except (ValueError, TypeError):
            timeout_height = 0

        return BetTimeoutInfo(
            box_id=box_id,
            current_height=current_height,
            timeout_height=timeout_height,
            blocks_remaining=max(0, timeout_height - current_height),
            is_expired=current_height >= timeout_height,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Box {box_id} not found")
        raise


@router.get("/bet/expired", response_model=ExpiredBetsResponse)
async def list_expired_bets(request: Request):
    """List expired bets eligible for refund."""
    # TODO: scan for expired PendingBet boxes
    return {"expired_bets": [], "total": 0}


@router.post("/build-reveal-tx", responses={501: {"model": BetErrorResponse}})
async def build_reveal_tx(request: Request, body: RevealTxRequest):
    """Build a reveal transaction for signing (bot endpoint)."""
    # TODO: implement reveal tx building
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/bet/build-refund-tx", responses={400: {"model": BetErrorResponse}, 501: {"model": BetErrorResponse}})
async def build_refund_tx(request: Request, body: RefundTxRequest):
    """Build a refund transaction for an expired bet."""
    # box_id is now validated by Pydantic (required, min_length=1)

    # TODO: implement refund tx building
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/resolve-bet", responses={403: {"model": BetErrorResponse}, 404: {"model": BetErrorResponse}, 429: {"model": BetErrorResponse}})
@limiter.limit("30/minute")
async def resolve_bet(request: Request, body: ResolveBetRequest):
    """Resolve a bet (bot-only endpoint, requires API key).

    Updates the bet record in game history with outcome and payout.
    Does NOT build or submit on-chain transactions -- the bot handles that.
    """
    # Verify API key (header only — query params are logged and unsafe for secrets)
    api_key = request.headers.get("X-Api-Key")
    if not api_key or not hmac.compare_digest(api_key, BOT_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")

    game_history: GameHistoryService = request.app.state.game_history
    updated = game_history.update_bet(
        bet_id=body.bet_id,
        outcome=body.outcome,
        payout_nanoerg=body.payout_nanoerg,
    )

    if not updated:
        raise HTTPException(status_code=404, detail=f"Bet {body.bet_id} not found in history")

    logger.info(
        "Bet resolved: bet_id=%s outcome=%s payout=%s address=%s",
        body.bet_id[:12] + "...",
        body.outcome,
        body.payout_nanoerg,
        body.player_address[:10] + "...",
    )

    return {
        "status": "resolved",
        "bet_id": body.bet_id,
        "outcome": body.outcome,
        "payout_nanoerg": body.payout_nanoerg,
        "player_address": body.player_address,
    }


@router.post("/reveal-bet", responses={403: {"model": BetErrorResponse}, 501: {"model": BetErrorResponse}, 429: {"model": BetErrorResponse}})
@limiter.limit("30/minute")
async def reveal_bet(request: Request, body: RevealBetRequest):
    """Reveal a bet (bot endpoint, requires API key)."""
    api_key = request.headers.get("X-Api-Key")
    if not api_key or not hmac.compare_digest(api_key, BOT_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")

    # TODO: implement bet reveal
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/pool/deposit", responses={501: {"model": BetErrorResponse}})
async def pool_deposit(request: Request, body: PoolDepositRequest):
    """Deposit ERG into the house pool."""
    # TODO: implement pool deposit
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/pool/withdraw", responses={501: {"model": BetErrorResponse}})
async def pool_withdraw(request: Request, body: PoolWithdrawRequest):
    """Withdraw ERG from the house pool."""
    # TODO: implement pool withdraw
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/player/stats/{address:path}", response_model=PlayerStatsResponse)
async def get_player_stats(request: Request, address: str):
    """Get player statistics (wins, losses, volume)."""
    game_history = request.app.state.game_history
    bets = game_history.get_history(address, limit=10000)
    wins = sum(1 for b in bets if b["outcome"] == "win")
    losses = sum(1 for b in bets if b["outcome"] == "loss")
    total_bets = len(bets)
    win_rate = wins / total_bets if total_bets > 0 else 0.0
    total_wagered = sum(int(b.get("betAmount", "0")) for b in bets)
    total_won = sum(int(b.get("payout", "0")) for b in bets if b["outcome"] == "win")
    net_profit = total_won - total_wagered
    return {
        "address": address,
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_wagered_nanoerg": total_wagered,
        "total_wagered_erg": nano_to_erg(total_wagered),
        "total_won_nanoerg": total_won,
        "total_won_erg": nano_to_erg(total_won),
        "net_profit_nanoerg": net_profit,
        "net_profit_erg": nano_to_erg(net_profit),
    }


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(limit: int = Query(default=10, ge=1, le=100)):
    """Get top players leaderboard."""
    # TODO: integrate with player_stats service
    return {"leaderboard": [], "total": 0}


@router.get("/player/comp/{address:path}", response_model=PlayerCompResponse)
async def get_player_comp(address: str):
    """Get player compensation points."""
    # TODO: integrate with comp points service
    return {"address": address, "comp_points": 0, "tier": "bronze"}
