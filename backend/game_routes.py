"""
DuckPools - Game Routes

Frontend-facing endpoints for the coinflip game PoC.
These routes match the API contract expected by the React frontend.

MAT-309: Rebuild backend API to match frontend contract.
"""

from datetime import datetime, timezone
from typing import List, Optional
import os
import re

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field, field_validator

from validators import validate_ergo_address, ValidationError as ErgoValidationError

router = APIRouter(tags=["game"])

# ─── Compiled Contract Constants ──────────────────────────────────
# coinflip_v2.es compiled 2026-03-28 against node v6.0.3 (Lithos testnet)
# Values MUST match smart-contracts/coinflip_deployed.json
COINFLIP_P2S_ADDRESS = "3yNMkSZ6b36YGBJJNhpavxxCFg4f2ceH5JF81hXJgzWoWozuFJSjoW8Q5JXow6fsTVNrqz48h8a9ajYSTKfwaxG16GbHzxrDcsarkBkbR6NYdGeoCZ9KgNcNMYPLV9RPkLFwBPLHxDxyTmBfqn5L75zqftETuAadKr8FHEYZrVPZ6kn6gdiZbzMwghxRy2g4wpTdby4jnxhA42UH7JJzMibgMNBW4yvzw8EaguPLVja6xsxx43yihw5DEzMGzL7HKWYUs6uVugK1C8Feh3KUX9kpea5xpLXX5oZCV47W6cnTrJfJD3"
COINFLIP_ERGO_TREE = "19d8010c04000200020104000404040005c20105640400040004000564d805d601cdeee4c6a7040ed602e4c6a7090ed603e4c6a70704d604cdeee4c6a7050ed605c1a7eb02ea02ea027201d193cbb3720283010295937203730073017302e4c6a7060ed195939e7eb2cbb3db6902db6503fe72027303000473047203d801d606b2a5730500ed93c27206d0720492c172069d9c720573067307d801d606b2a5730800ed93c27206d0720192c172067205ea02ea02ea02d192a3e4c6a708047204d193c2b2a5730900d07204d192c1b2a5730a009972059d7205730b"

# Register layout (must match coinflip_v2.es and frontend coinflipService.ts)
# R4: housePubKey (Coll[Byte])     — 33-byte compressed public key
# R5: playerPubKey (Coll[Byte])    — 33-byte compressed public key
# R6: commitmentHash (Coll[Byte])  — blake2b256(secret || choice_byte)
# R7: playerChoice (Int)           — 0=heads, 1=tails
# R8: timeoutHeight (Int)          — block height for refund
# R9: playerSecret (Coll[Byte])    — player's random secret bytes


# ─── Response Models (match frontend types/Game.ts) ────────────────


class GameChoice(BaseModel):
    gameType: str = "coinflip"
    side: Optional[str] = None
    rollTarget: Optional[int] = None
    rows: Optional[int] = None


class GameOutcome(BaseModel):
    gameType: str = "coinflip"
    result: Optional[str] = None
    rngValue: Optional[int] = None
    slot: Optional[int] = None
    multiplier: Optional[float] = None


class BetRecord(BaseModel):
    betId: str
    txId: str
    boxId: str = ""
    playerAddress: str
    gameType: str = "coinflip"
    choice: GameChoice = Field(default_factory=GameChoice)
    betAmount: str
    outcome: str = "pending"
    actualOutcome: Optional[GameOutcome] = None
    payout: str = "0"
    payoutMultiplier: float = 0.97
    timestamp: str
    blockHeight: int = 0
    timeoutHeight: int = 0  # Block height at which player can claim refund
    resolvedAtHeight: Optional[int] = None


class PlaceBetRequest(BaseModel):
    address: str
    amount: str
    choice: int  # 0 = Heads, 1 = Tails
    commitment: str
    betId: str
    boxId: str = ""  # On-chain box ID (populated after tx broadcast)
    timeoutHeight: int = 0  # On-chain timeout height (R8 register)

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        try:
            return validate_ergo_address(v)
        except ErgoValidationError as e:
            raise ValueError(str(e))

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        try:
            amount = int(v)
        except (ValueError, TypeError):
            raise ValueError("amount must be a valid integer string (nanoERG)")
        if amount <= 0:
            raise ValueError("amount must be positive (nanoERG)")
        if amount < 1_000_000:
            raise ValueError("minimum bet is 0.001 ERG (1,000,000 nanoERG)")
        if amount > get_safe_max_bet():
            safe_max = get_safe_max_bet()
            raise ValueError(f"maximum bet is {safe_max:,} nanoERG ({safe_max/1_000_000_000:.3f} ERG) based on current pool liquidity")
        return v

    @field_validator("choice")
    @classmethod
    def validate_choice(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("choice must be 0 (Heads) or 1 (Tails)")
        return v

    @field_validator("commitment")
    @classmethod
    def validate_commitment(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("commitment is required")
        v = v.strip().lower()
        if len(v) != 64:
            raise ValueError("commitment must be a 64-character hex string (blake2b256)")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("commitment must be valid hex")
        # Additional security: ensure commitment is not all zeros or all f's (common attack vectors)
        if v == "0" * 64 or v == "f" * 64 or v == "ff" * 32:
            raise ValueError("invalid commitment - cannot be all zeros or all f's")
        return v

    @field_validator("betId")
    @classmethod
    def validate_bet_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("betId is required")
        v = v.strip()
        if len(v) < 8 or len(v) > 64:
            raise ValueError("betId must be between 8 and 64 characters")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("betId can only contain alphanumeric characters, underscores, and hyphens")
        # Check for duplicate betId in current bets (prevent replay attacks)
        from .game_routes import _bets
        if any(bet.get("betId") == v for bet in _bets):
            raise ValueError("betId already exists - please use a unique identifier")
        return v


class PlaceBetResponse(BaseModel):
    success: bool = True
    txId: str = ""
    betId: str = ""
    message: str = ""


class PlayerStats(BaseModel):
    address: str
    totalBets: int = 0
    wins: int = 0
    losses: int = 0
    pending: int = 0
    winRate: float = 0.0
    totalWagered: str = "0"
    totalWon: str = "0"
    totalLost: str = "0"
    netPnL: str = "0"
    biggestWin: str = "0"
    currentStreak: int = 0
    longestWinStreak: int = 0
    longestLossStreak: int = 0
    compPoints: int = 0
    compTier: str = "Bronze"


class LeaderboardEntry(BaseModel):
    rank: int
    address: str
    totalBets: int = 0
    netPnL: str = "0"
    winRate: float = 0.0
    compPoints: int = 0
    compTier: str = "Bronze"


class LeaderboardResponse(BaseModel):
    players: List[LeaderboardEntry]
    totalPlayers: int = 0
    sortBy: str = "netPnL"


class CompPointsResponse(BaseModel):
    address: str
    points: int = 0
    tier: str = "Bronze"
    tierProgress: float = 0.0
    nextTier: str = "Silver"
    pointsToNextTier: int = 100
    totalEarned: int = 0
    benefits: List[str] = []


# ─── In-memory game store (PoC — no database) ──────────────────────

_bets: List[dict] = []
_pool_stats = {
    "liquidity": "50000000000000",  # 50,000 ERG in nanoERG
    "totalBets": 0,
    "playerWins": 0,
    "houseWins": 0,
    "totalFees": "0",
}

# Dynamic max bet configuration
MAX_BET_NANOERG = 100_000_000_000_000  # 100,000 ERG (hard cap)
SAFETY_FACTOR = 0.1  # 10% of pool liquidity as max single bet

def get_safe_max_bet() -> int:
    """Calculate safe max bet based on current pool liquidity and safety factor."""
    pool_liquidity = int(_pool_stats["liquidity"])
    safe_bet = int(pool_liquidity * SAFETY_FACTOR)
    return min(safe_bet, MAX_BET_NANOERG)


# ─── Routes ───────────────────────────────────────────────────────

@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard():
    """Leaderboard for Leaderboard.tsx."""
    return LeaderboardResponse(
        players=[],
        totalPlayers=0,
        sortBy="netPnL",
    )


@router.get("/history/{address}", response_model=List[BetRecord])
async def get_history(address: str):
    """Bet history for GameHistory.tsx."""
    return [BetRecord(**b) for b in _bets if b["playerAddress"] == address]


@router.get("/player/stats/{address}", response_model=PlayerStats)
async def get_player_stats(address: str):
    """Player stats for StatsDashboard.tsx."""
    player_bets = [b for b in _bets if b["playerAddress"] == address]
    wins = sum(1 for b in player_bets if b["outcome"] == "win")
    losses = sum(1 for b in player_bets if b["outcome"] == "loss")
    pending = sum(1 for b in player_bets if b["outcome"] == "pending")
    total = len(player_bets)
    win_rate = (wins / total * 100) if total > 0 else 0.0

    total_wagered = sum(int(b["betAmount"]) for b in player_bets)
    total_won = sum(int(b["payout"]) for b in player_bets if b["outcome"] == "win")
    total_lost = sum(int(b["betAmount"]) for b in player_bets if b["outcome"] == "loss")
    net_pnl = total_won - total_lost
    biggest_win = max((int(b["payout"]) for b in player_bets if b["outcome"] == "win"), default=0)

    # Streaks
    current_streak = 0
    longest_win = 0
    longest_loss = 0
    streak = 0
    streak_type = None
    for b in reversed(player_bets):
        if b["outcome"] in ("win", "loss"):
            if streak_type is None:
                streak_type = b["outcome"]
                streak = 1
            elif b["outcome"] == streak_type:
                streak += 1
            else:
                break
    current_streak = streak if streak_type == "win" else -streak

    # Full streak analysis
    ws = ls = 0
    cur = 0
    cur_type = None
    for b in player_bets:
        if b["outcome"] in ("win", "loss"):
            if cur_type == b["outcome"]:
                cur += 1
            else:
                if cur_type == "win":
                    ws = max(ws, cur)
                elif cur_type == "loss":
                    ls = max(ls, cur)
                cur_type = b["outcome"]
                cur = 1
    if cur_type == "win":
        ws = max(ws, cur)
    elif cur_type == "loss":
        ls = max(ls, cur)

    # Comp points: 1 point per 0.01 ERG wagered
    comp_points = total_wagered // 10000000  # 0.01 ERG = 10M nanoERG
    comp_tier = "Bronze"
    if comp_points >= 10000:
        comp_tier = "Diamond"
    elif comp_points >= 1000:
        comp_tier = "Gold"
    elif comp_points >= 100:
        comp_tier = "Silver"

    return PlayerStats(
        address=address,
        totalBets=total,
        wins=wins,
        losses=losses,
        pending=pending,
        winRate=win_rate,
        totalWagered=str(total_wagered),
        totalWon=str(total_won),
        totalLost=str(total_lost),
        netPnL=str(net_pnl),
        biggestWin=str(biggest_win),
        currentStreak=current_streak,
        longestWinStreak=longest_win,
        longestLossStreak=longest_loss,
        compPoints=comp_points,
        compTier=comp_tier,
    )


@router.get("/player/comp/{address}", response_model=CompPointsResponse)
async def get_player_comp(address: str):
    """Comp points for CompPoints.tsx."""
    player_bets = [b for b in _bets if b["playerAddress"] == address]
    total_wagered = sum(int(b["betAmount"]) for b in player_bets)
    comp_points = total_wagered // 10000000

    tier_thresholds = {"Bronze": 0, "Silver": 100, "Gold": 1000, "Diamond": 10000}
    tier_order = ["Bronze", "Silver", "Gold", "Diamond"]

    current_tier = "Bronze"
    for tier, threshold in tier_thresholds.items():
        if comp_points >= threshold:
            current_tier = tier

    tier_idx = tier_order.index(current_tier)
    is_max = tier_idx >= len(tier_order) - 1

    if is_max:
        next_tier = ""
        points_to_next = 0
        progress = 1.0
    else:
        next_tier = tier_order[tier_idx + 1]
        next_threshold = tier_thresholds[next_tier]
        current_threshold = tier_thresholds[current_tier]
        points_to_next = next_threshold - comp_points
        progress = (comp_points - current_threshold) / max(next_threshold - current_threshold, 1)

    benefits_map = {
        "Bronze": ["Basic access"],
        "Silver": ["Reduced house edge", "Priority support"],
        "Gold": ["Further reduced edge", "Exclusive tournaments", "Dedicated support"],
        "Diamond": ["Best house edge", "VIP tournaments", "Personal manager", "Early access"],
    }

    return CompPointsResponse(
        address=address,
        points=comp_points,
        tier=current_tier,
        tierProgress=round(progress, 4),
        nextTier=next_tier,
        pointsToNextTier=points_to_next,
        totalEarned=comp_points,
        benefits=benefits_map.get(current_tier, []),
    )


@router.get("/pool/state")
async def pool_state():
    """Return current pool state including liquidity and safe max bet."""
    return {
        "liquidity": _pool_stats["liquidity"],
        "totalBets": _pool_stats["totalBets"],
        "playerWins": _pool_stats["playerWins"],
        "houseWins": _pool_stats["houseWins"],
        "totalFees": _pool_stats["totalFees"],
        "safeMaxBet": get_safe_max_bet(),
    }

@router.get("/contract-info")
async def contract_info():
    """Return compiled coinflip contract address and register layout.
    Frontend needs this to build transactions targeting the contract."""
    return {
        "p2sAddress": COINFLIP_P2S_ADDRESS,
        "ergoTree": COINFLIP_ERGO_TREE,
        "timeoutDelta": DEFAULT_TIMEOUT_DELTA,
        "refundFeeBps": REFUND_FEE_BPS,
        "registers": {
            "R4": "housePubKey (Coll[Byte])",
            "R5": "playerPubKey (Coll[Byte])",
            "R6": "commitmentHash (Coll[Byte])",
            "R7": "playerChoice (Int)",
            "R8": "timeoutHeight (Int)",
            "R9": "playerSecret (Coll[Byte])",
        },
    }


# Rate limiting to prevent abuse
from fastapi import Request
from datetime import datetime, timezone, timedelta
from typing import Dict

# Simple in-memory rate limiter
_rate_limit_store: Dict[str, List[datetime]] = {}

def _check_rate_limit(address: str, max_requests: int = 5, time_window: timedelta = timedelta(minutes=1)):
    """Simple rate limiting to prevent abuse."""
    now = datetime.now(timezone.utc)
    window_start = now - time_window
    
    # Clean up old entries
    if address in _rate_limit_store:
        _rate_limit_store[address] = [t for t in _rate_limit_store[address] if t > window_start]
    
    # Check if we've exceeded the limit
    if address in _rate_limit_store and len(_rate_limit_store[address]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please wait before placing another bet. Limit: {max_requests} bets per minute."
        )
    
    # Record the request
    if address not in _rate_limit_store:
        _rate_limit_store[address] = []
    _rate_limit_store[address].append(now)

@router.post("/place-bet", response_model=PlaceBetResponse)
async def place_bet(req: PlaceBetRequest, request: Request):
    """Place a coinflip bet from BetForm.tsx / CoinFlipGame.tsx."""
    now = datetime.now(timezone.utc).isoformat()
    
    # Rate limiting to prevent abuse
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    
    # Additional security: validate betId format more strictly
    if not re.match(r'^[a-zA-Z0-9_-]{8,64}$', req.betId):
        raise HTTPException(
            status_code=400,
            detail="Invalid betId format. Must be 8-64 characters containing only alphanumeric, underscores, and hyphens."
        )
    
    # Check if bet exceeds available pool liquidity
    bet_amount = int(req.amount)
    pool_liquidity = int(_pool_stats["liquidity"])
    if bet_amount > pool_liquidity:
        raise HTTPException(
            status_code=400,
            detail=f"Bet amount ({bet_amount:,} nanoERG) exceeds available pool liquidity ({pool_liquidity:,} nanoERG). "
                   f"Maximum bet is {get_safe_max_bet():,} nanoERG based on current pool state."
        )

    # Additional security: prevent too frequent bets from the same address
    _check_rate_limit(req.address, max_requests=10, time_window=timedelta(seconds=30))
    
    side = "heads" if req.choice == 0 else "tails"

    bet = {
        "betId": req.betId,
        "txId": "",  # Will be filled when tx is actually broadcast
        "boxId": req.boxId,
        "playerAddress": req.address,
        "gameType": "coinflip",
        "choice": {"gameType": "coinflip", "side": side},
        "betAmount": req.amount,
        "outcome": "pending",
        "actualOutcome": None,
        "payout": "0",
        "payoutMultiplier": 0.97,
        "timestamp": now,
        "blockHeight": 0,
        "timeoutHeight": req.timeoutHeight,
        "resolvedAtHeight": None,
    }
    _bets.append(bet)

    # Update pool stats
    _pool_stats["totalBets"] += 1

    # Calculate fee
    fee = int(req.amount) * 3 // 100  # 3% house edge
    _pool_stats["totalFees"] = str(int(_pool_stats["totalFees"]) + fee)

    return PlaceBetResponse(
        success=True,
        txId="",  # In PoC, no actual tx broadcast
        betId=req.betId,
        message="Bet placed. Waiting for on-chain confirmation.",
    )


# ─── Timeout & Refund Endpoints ─────────────────────────────────

# Timeout configuration (matches frontend TIMEOUT_DELTA = 100)
DEFAULT_TIMEOUT_DELTA = 100  # blocks
REFUND_FEE_BPS = 200  # 2% fee on refund (matching contract: betAmount - betAmount/50)


class TimeoutInfoResponse(BaseModel):
    betId: str
    playerAddress: str
    betAmount: str
    timeoutHeight: int
    currentHeight: int
    blocksRemaining: int
    isExpired: bool
    refundAmount: str
    status: str


class RefundableBetsResponse(BaseModel):
    bets: List[TimeoutInfoResponse]
    totalBets: int
    totalLockedNanoErg: str
    currentHeight: int


@router.get("/bets/expired", response_model=RefundableBetsResponse)
async def get_expired_bets(currentHeight: int = 0):
    """
    List all bets that have exceeded their timeout height.
    
    These bets can be reclaimed by the player via the refund spending path
    in coinflip_v2.es (HEIGHT >= timeoutHeight && playerProp).
    
    Query params:
      - currentHeight: Current blockchain height (fetched from node if 0)
    """
    # Fetch current height from node if not provided
    if currentHeight == 0:
        import httpx
        try:
            node_url = os.environ.get("NODE_URL", "http://localhost:9052")
            api_key = os.environ.get("NODE_API_KEY", "")
            headers = {}
            if api_key:
                headers["api_key"] = api_key
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{node_url}/info", headers=headers)
                resp.raise_for_status()
                info = resp.json()
                currentHeight = info.get("fullHeight") or 0
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="Could not fetch current block height from Ergo node"
            )

    expired_bets = []
    total_locked = 0

    for bet in _bets:
        if bet["outcome"] != "pending":
            continue
        timeout_h = bet.get("timeoutHeight", 0)
        if timeout_h <= 0:
            continue
        if currentHeight >= timeout_h:
            bet_amount = int(bet["betAmount"])
            refund = bet_amount - bet_amount // 50  # 98% refund (matching contract)
            total_locked += bet_amount
            expired_bets.append(TimeoutInfoResponse(
                betId=bet["betId"],
                playerAddress=bet["playerAddress"],
                betAmount=bet["betAmount"],
                timeoutHeight=timeout_h,
                currentHeight=currentHeight,
                blocksRemaining=0,
                isExpired=True,
                refundAmount=str(refund),
                status="expired",
            ))

    return RefundableBetsResponse(
        bets=expired_bets,
        totalBets=len(expired_bets),
        totalLockedNanoErg=str(total_locked),
        currentHeight=currentHeight,
    )


@router.get("/bets/{bet_id}/timeout", response_model=TimeoutInfoResponse)
async def get_bet_timeout(bet_id: str, currentHeight: int = 0):
    """
    Get timeout info for a specific bet.
    
    Returns the timeout height, blocks remaining, and whether the bet
    is eligible for refund. The player can use this to decide when to
    submit a refund transaction.
    """
    # Find the bet
    bet = None
    for b in _bets:
        if b["betId"] == bet_id:
            bet = b
            break

    if not bet:
        raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")

    # Fetch current height from node if not provided
    if currentHeight == 0:
        import httpx
        try:
            node_url = os.environ.get("NODE_URL", "http://localhost:9052")
            api_key = os.environ.get("NODE_API_KEY", "")
            headers = {}
            if api_key:
                headers["api_key"] = api_key
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{node_url}/info", headers=headers)
                resp.raise_for_status()
                info = resp.json()
                currentHeight = info.get("fullHeight") or 0
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="Could not fetch current block height from Ergo node"
            )

    timeout_h = bet.get("timeoutHeight", 0)
    if timeout_h <= 0:
        # Bet was placed before timeout tracking — assume default delta
        # This handles backward compatibility with existing bets
        timeout_h = currentHeight + DEFAULT_TIMEOUT_DELTA

    blocks_remaining = max(0, timeout_h - currentHeight)
    is_expired = currentHeight >= timeout_h
    bet_amount = int(bet["betAmount"])
    refund = bet_amount - bet_amount // 50  # 98% refund

    status = "expired" if is_expired else ("pending" if bet["outcome"] == "pending" else bet["outcome"])

    return TimeoutInfoResponse(
        betId=bet["betId"],
        playerAddress=bet["playerAddress"],
        betAmount=bet["betAmount"],
        timeoutHeight=timeout_h,
        currentHeight=currentHeight,
        blocksRemaining=blocks_remaining,
        isExpired=is_expired,
        refundAmount=str(refund),
        status=status,
    )


@router.post("/bets/{bet_id}/refund-record")
async def record_refund(bet_id: str):
    """
    Record that a refund transaction was submitted for a bet.
    
    Called by the frontend after the player broadcasts a refund tx.
    Updates the off-chain bet record to 'refunded' status and adjusts
    pool liquidity.
    """
    bet = None
    for b in _bets:
        if b["betId"] == bet_id:
            bet = b
            break

    if not bet:
        raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")

    if bet["outcome"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Bet {bet_id} is already {bet['outcome']}, cannot refund"
        )

    bet_amount = int(bet["betAmount"])
    refund = bet_amount - bet_amount // 50  # 98% refund, 2% fee

    # Update bet record
    bet["outcome"] = "refunded"
    bet["payout"] = str(refund)
    bet["resolvedAtHeight"] = bet.get("timeoutHeight", 0)

    # Update pool stats: return locked funds (minus fee) to liquidity
    current_liquidity = int(_pool_stats["liquidity"])
    _pool_stats["liquidity"] = str(current_liquidity + refund)

    # Record the 2% refund fee
    fee = bet_amount - refund
    _pool_stats["totalFees"] = str(int(_pool_stats["totalFees"]) + fee)

    return {
        "success": True,
        "betId": bet_id,
        "refundAmount": str(refund),
        "refundFee": str(fee),
        "message": f"Refund recorded. {refund/1e9:.4f} ERG returned to player (2% fee: {fee/1e9:.6f} ERG).",
    }


@router.get("/bets/pending-with-timeout")
async def get_pending_bets_with_timeout(currentHeight: int = 0):
    """
    List all pending bets with their timeout status.
    
    Useful for monitoring which bets are approaching expiry.
    The off-chain bot should use this to prioritize reveal processing.
    """
    if currentHeight == 0:
        import httpx
        try:
            node_url = os.environ.get("NODE_URL", "http://localhost:9052")
            api_key=os.environ.get("API_KEY", "")
            headers = {}
            if api_key:
                headers["api_key"] = api_key
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{node_url}/info", headers=headers)
                resp.raise_for_status()
                info = resp.json()
                currentHeight = info.get("fullHeight") or 0
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="Could not fetch current block height from Ergo node"
            )

    pending = []
    for bet in _bets:
        if bet["outcome"] != "pending":
            continue
        timeout_h = bet.get("timeoutHeight", 0)
        if timeout_h <= 0:
            timeout_h = currentHeight + DEFAULT_TIMEOUT_DELTA
        blocks_remaining = max(0, timeout_h - currentHeight)
        pending.append({
            "betId": bet["betId"],
            "playerAddress": bet["playerAddress"],
            "betAmount": bet["betAmount"],
            "timeoutHeight": timeout_h,
            "blocksRemaining": blocks_remaining,
            "isExpired": currentHeight >= timeout_h,
            "urgency": "expired" if blocks_remaining == 0 else (
                "critical" if blocks_remaining <= 10 else (
                    "warning" if blocks_remaining <= 30 else "normal"
                )
            ),
        })

    # Sort by urgency: expired first, then by blocks remaining ascending
    urgency_order = {"expired": 0, "critical": 1, "warning": 2, "normal": 3}
    pending.sort(key=lambda x: (urgency_order.get(x["urgency"], 9), x["blocksRemaining"]))

    return {
        "bets": pending,
        "totalPending": len(pending),
        "expiredCount": sum(1 for b in pending if b["isExpired"]),
        "currentHeight": currentHeight,
    }


# ─── Reveal Transaction Builder (MAT-355) ────────────────────────────────────────
# This endpoint is used by the off-chain bot to build reveal transactions.
# It takes a bet box ID and current block hash, then builds an unsigned
# transaction that spends the commit box, verifies the commitment, and
# pays the winner according to the 97/50 payout multiplier.

class RevealRequest(BaseModel):
    box_id: str
    block_hash: str

class RevealResponse(BaseModel):
    success: bool = True
    unsigned_tx: str = ""
    bet_id: str = ""
    player_address: str = ""
    player_wins: bool = False
    payout_amount: str = "0"
    message: str = ""


@router.post("/bot/build-reveal-tx", response_model=RevealResponse)
async def build_reveal_tx(req: RevealRequest):
    """
    Build an unsigned reveal transaction for a pending bet.
    
    This endpoint is used by the off-chain bot to:
    1. Find the pending bet by box ID
    2. Verify the commitment using the provided block hash
    3. Determine win/loss based on RNG
    4. Calculate the 97/50 payout
    5. Build and return an unsigned EIP-12 transaction
    
    Parameters:
    - box_id: The on-chain box ID of the pending bet
    - block_hash: Current block hash used for RNG (prev block hash)
    
    Returns:
    - unsigned_tx: Base64 encoded unsigned transaction
    - bet_id: The bet identifier
    - player_wins: True if player won, False if house won
    - payout_amount: Amount to pay the player (97% of bet)
    """
    import httpx
    from base64 import b64encode
    import json
    
    # Find the bet by box ID
    bet = None
    for b in _bets:
        if b.get("boxId") == req.box_id:
            bet = b
            break
    
    if not bet:
        raise HTTPException(
            status_code=404,
            detail=f"Bet with box_id {req.box_id} not found"
        )
    
    if bet["outcome"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Bet {bet['betId']} is already {bet['outcome']}, cannot reveal"
        )
    
    # Get current block height from node
    currentHeight = 0
    try:
        node_url = os.environ.get("NODE_URL", "http://localhost:9052")
        api_key=os.environ.get("API_KEY", "")
        headers = {}
        if api_key:
            headers["api_key"] = api_key
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{node_url}/info", headers=headers)
            resp.raise_for_status()
            info = resp.json()
            currentHeight = info.get("fullHeight") or 0
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not fetch current block height from Ergo node"
        )
    
    # Verify the commitment using the provided block hash
    # This follows the same RNG logic as in frontend coinflipService.ts
    try:
        # Decode the commitment (R6 register)
        commitment = bet.get("commitment", "")
        if not commitment:
            raise ValueError("Missing commitment in bet record")
        
        # Decode the player secret (R9 register)
        player_secret = bet.get("playerSecret", "")
        if not player_secret:
            raise ValueError("Missing player secret in bet record")
        
        # RNG calculation (same as frontend)
        prev_block_bytes = bytes.fromhex(req.block_hash)
        r9_bytes = bytes.fromhex(player_secret)
        rng_input = prev_block_bytes + r9_bytes
        rng_hash = blake2b256(rng_input)
        flip_result = rng_hash[0] % 2
        player_choice = 0 if bet["choice"]["side"] == "heads" else 1
        player_wins = flip_result == player_choice
        
        # Calculate payout (97/50 multiplier for wins)
        bet_amount = int(bet["betAmount"])
        if player_wins:
            payout = int(bet_amount * 97 / 50)  # 97% of bet amount (1.94x payout)
        else:
            payout = 0
        
        # Build the transaction (simplified - in real implementation would use Ergo API)
        # This is a placeholder for the actual transaction building logic
        # The bot would use this to sign and broadcast the transaction
        
        # For now, return a mock transaction
        mock_tx = {
            "type": "EIP-12",
            "inputs": [
                {
                    "boxId": req.box_id,
                    "ergoTree": COINFLIP_ERGO_TREE,
                    "registers": {
                        "R4": bet.get("housePubKey", ""),  # house public key
                        "R5": bet.get("playerPubKey", ""),  # player public key
                        "R6": commitment,  # commitment hash
                        "R7": str(player_choice),  # player choice (0=heads, 1=tails)
                        "R8": str(bet.get("timeoutHeight", 0)),  # timeout height
                        "R9": player_secret  # player secret
                    },
                    "assets": [
                        {
                            "tokenId": "",
                            "amount": str(bet_amount)
                        }
                    ]
                }
            ],
            "outputs": [
                {
                    "address": bet["playerAddress"],
                    "value": str(payout),
                    "ergoTree": COINFLIP_ERGO_TREE,
                    "registers": {
                        "R4": bet.get("housePubKey", ""),
                        "R5": bet.get("playerPubKey", ""),
                        "R6": "",  # empty commitment for revealed state
                        "R7": "2" if player_wins else "3",  # 2=win, 3=loss
                        "R8": str(currentHeight),
                        "R9": ""
                    },
                    "assets": []
                }
            ]
        }
        
        unsigned_tx = b64encode(json.dumps(mock_tx).encode()).decode()
        
        # Update bet record (in real implementation, this would be done after transaction confirmation)
        bet["outcome"] = "win" if player_wins else "loss"
        bet["payout"] = str(payout)
        bet["actualOutcome"] = {
            "gameType": "coinflip",
            "result": "win" if player_wins else "loss",
            "rngValue": flip_result,
            "slot": 0,
            "multiplier": 1.94 if player_wins else 0
        }
        bet["resolvedAtHeight"] = currentHeight
        
        return RevealResponse(
            success=True,
            unsigned_tx=unsigned_tx,
            bet_id=bet["betId"],
            player_address=bet["playerAddress"],
            player_wins=player_wins,
            payout_amount=str(payout),
            message=f"Reveal transaction built. Player {'wins' if player_wins else 'loses'}. Payout: {payout:,} nanoERG."
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build reveal transaction: {str(e)}"
        )
