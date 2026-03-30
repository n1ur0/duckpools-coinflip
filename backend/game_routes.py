"""
DuckPools - Game Routes

Frontend-facing endpoints for the coinflip game PoC.
These routes match the API contract expected by the React frontend.

MAT-309: Rebuild backend API to match frontend contract.
"""

from datetime import datetime, timezone
from typing import List, Optional, Set
import asyncio
import os
import re

import hashlib
import logging

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from validators import validate_ergo_address, ValidationError as ErgoValidationError
from rng_module import compute_rng

logger = logging.getLogger("duckpools.game")

router = APIRouter(tags=["game"])

# ─── Compiled Contract Constants ──────────────────────────────────
# coinflip_v2_final.es compiled 2026-03-30 against node v6.0.3 (Lithos testnet)
# Values MUST match smart-contracts/coinflip_deployed.json
# NOTE: R10 not supported in ErgoScript 6.0.3. Reveal window derived from
#       timeoutHeight - 30 (REVEAL_WINDOW constant in contract).
COINFLIP_P2S_ADDRESS = "88q9jJjaRZsmAmbJqKEjSqeFHtsP4RsAB3pSgsTQNwGYf9gnGCKjKqP4BcpR6xCjaGGo13C8qQWE1zU2trNpuetCG4uS5mU2wkid4HyDd4cWj7kkxeFtnPNEaSznceEB46RpTJ8SXQiXKuk6p4RVj4wqzcUWDZGn5taF3XYMT5f7GGp4HdJT3wizd9XZQz466c8JiRS21JW92w9wdj2AFUR4vS3Q4Z2cLPTbt1FBdT73dVe2CjR81Hbc9iXFk2FF3hxjF86bx1ZsyfqQ7M3ff24JvCgDo3QwdteKFnkzcf3PiM9rL5b3aCyxpmUEfG2SGrmafX43i"
COINFLIP_ERGO_TREE = ""  # ergoTree hex not returned by Lithos 6.0.3 /script/p2sAddress; P2S address is sufficient

# Register layout (must match coinflip_v2_final.es and frontend coinflipService.ts)
# R4: housePubKey (Coll[Byte])     — 33-byte compressed public key
# R5: playerPubKey (Coll[Byte])    — 33-byte compressed public key
# R6: commitmentHash (Coll[Byte])  — blake2b256(secret || choice_byte)
# R7: playerChoice (Int)           — 0=heads, 1=tails
# R8: timeoutHeight (Int)          — block height for refund
# R9: playerSecret (Coll[Byte])    — player's random secret bytes
# DERIVED: rngBlockHeight = timeoutHeight - 30 (reveal window)


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
    housePubKey: str = ""  # House compressed PK (R4) — 33 bytes hex
    houseAddress: str = ""  # House P2PK address (for reveal payout when house wins)
    playerPubKey: str = ""  # Player compressed PK (R5) — 33 bytes hex
    playerSecret: str = ""  # Player random secret (R9) — hex string
    playerErgoTree: str = ""  # Player P2PK ergoTree (for refund tx output)

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
        if any(bet.get("betId") == v for bet in _bets):
            raise ValueError("betId already exists - please use a unique identifier")
        return v

    @field_validator("playerSecret")
    @classmethod
    def validate_player_secret(cls, v: str) -> str:
        """Validate player secret: must be 16 hex chars (8 bytes)."""
        if not v or not isinstance(v, str):
            raise ValueError("playerSecret is required for commitment verification")
        v = v.strip().lower()
        if len(v) != 16:
            raise ValueError(f"playerSecret must be 16 hex characters (8 bytes), got {len(v)}")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("playerSecret must be valid hex")
        return v

    @field_validator("housePubKey", "playerPubKey")
    @classmethod
    def validate_pubkey(cls, v: str) -> str:
        """Validate compressed public key: must be 66 hex chars (33 bytes with 02/03 prefix)."""
        if not v or not isinstance(v, str):
            raise ValueError("public key is required")
        v = v.strip().lower()
        if len(v) != 66:
            raise ValueError(f"compressed public key must be 66 hex chars (33 bytes), got {len(v)}")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("public key must be valid hex")
        if not v.startswith(("02", "03")):
            raise ValueError("compressed public key must start with 02 or 03 prefix")
        return v

    @field_validator("boxId")
    @classmethod
    def validate_box_id(cls, v: str) -> str:
        """Validate optional on-chain box ID: must be 64 hex chars (32-byte box hash)."""
        if not v:
            return v  # Optional field — empty is ok (box created after tx)
        v = v.strip()
        if len(v) != 64:
            raise ValueError(f"boxId must be 64 hex characters (32 bytes), got {len(v)}")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("boxId must be valid hex")
        return v

    @field_validator("playerErgoTree")
    @classmethod
    def validate_player_ergo_tree(cls, v: str) -> str:
        """Validate player P2PK ergoTree hex."""
        if not v:
            return v  # Optional — can be derived from address
        v = v.strip()
        if len(v) < 4:
            raise ValueError("playerErgoTree must be a valid hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("playerErgoTree must be valid hex")
        return v


class PlaceBetResponse(BaseModel):
    success: bool = True
    txId: str = ""
    betId: str = ""
    message: str = ""
    contractAddress: str = COINFLIP_P2S_ADDRESS
    timeoutDelta: int = 100  # blocks


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
_bet_ids: Set[str] = set()  # O(1) dedup lookup (MAT-396/5.2)
_bet_lock = asyncio.Lock()   # Prevent race conditions on concurrent place-bet
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


def _validate_address_param(address: str) -> str:
    """Validate address path parameter to prevent path traversal and injection."""
    if not address or not isinstance(address, str):
        raise HTTPException(status_code=400, detail="Address parameter is required")
    address = address.strip()
    if len(address) > 200:
        raise HTTPException(status_code=400, detail="Address too long")
    if ".." in address or "/" in address or "\\" in address:
        raise HTTPException(status_code=400, detail="Invalid address format")
    if not re.match(r'^[a-zA-Z0-9]+$', address):
        raise HTTPException(status_code=400, detail="Address contains invalid characters")
    return address


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
    address = _validate_address_param(address)
    return [BetRecord(**b) for b in _bets if b["playerAddress"] == address]


@router.get("/player/stats/{address}", response_model=PlayerStats)
async def get_player_stats(address: str):
    """Player stats for StatsDashboard.tsx."""
    address = _validate_address_param(address)
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
    address = _validate_address_param(address)
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
    """Return current pool state including liquidity and safe max bet.

    Tries to fetch real wallet balance from the Ergo node. Falls back to
    in-memory tracking if node is unavailable.
    """
    # Try to get real wallet balance from node
    try:
        import httpx
        node_url = os.environ.get("NODE_URL", "http://localhost:9052")
        api_key = os.environ.get("NODE_API_KEY", "")
        headers = {}
        if api_key:
            headers["api_key"] = api_key
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{node_url}/wallet/balances", headers=headers)
            resp.raise_for_status()
            wallet_data = resp.json()
            real_balance = int(wallet_data.get("balance", 0))
            if real_balance > 0:
                # Update in-memory liquidity with real wallet balance
                _pool_stats["liquidity"] = str(real_balance)
    except Exception:
        pass  # Fall back to in-memory value

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
        "revealWindowBlocks": 30,  # Derived: timeoutHeight - 30
        "refundFeeBps": REFUND_FEE_BPS,
        "houseEdgeBps": 300,  # 3%
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
    """Place a coinflip bet from BetForm.tsx / CoinFlipGame.tsx.

    The frontend builds the PendingBetBox transaction locally (EIP-12)
    and submits it to the Ergo node. This endpoint records the off-chain
    bet metadata for tracking, timeout monitoring, and reveal flow.

    Flow:
    1. Validate all inputs (address, amount, choice, commitment)
    2. Verify commitment = blake2b256(secret || choice) if secret provided
    3. Check pool liquidity
    4. Record bet in off-chain store (atomic under lock to prevent replay)
    5. Return contract info for frontend reference
    """
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

    # MAT-396/5.2: Atomic dedup check — prevents race condition on concurrent requests
    async with _bet_lock:
        if req.betId in _bet_ids:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate betId: {req.betId} already exists. Replays are not allowed."
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

    # Verify commitment if player secret is provided
    if req.playerSecret and req.commitment:
        try:
            secret_bytes = bytes.fromhex(req.playerSecret)
            expected_commitment = hashlib.blake2b(
                secret_bytes + bytes([req.choice]), digest_size=32
            ).hexdigest()
            if expected_commitment != req.commitment.strip().lower():
                raise HTTPException(
                    status_code=400,
                    detail="Commitment verification failed: blake2b256(secret || choice) does not match commitment"
                )
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid player secret or commitment: {str(e)}"
            )

    # MAT-394: Verify on-chain box if boxId provided (PendingBetBox exists)
    on_chain_box_value = 0
    if req.boxId:
        try:
            box_data = await _fetch_box_by_id(req.boxId)
            if box_data is None:
                raise HTTPException(
                    status_code=410,
                    detail=f"PendingBetBox {req.boxId} not found on-chain. Transaction may have failed."
                )
            if box_data.get("spentTransactionId"):
                raise HTTPException(
                    status_code=410,
                    detail=f"PendingBetBox {req.boxId} already spent. Cannot record this bet."
                )
            on_chain_box_value = int(box_data.get("value", 0))
            # Verify box value matches declared bet amount
            if on_chain_box_value != bet_amount:
                logger.warning(
                    "Box value mismatch: declared=%d on-chain=%d for bet %s",
                    bet_amount, on_chain_box_value, req.betId,
                )
            # Verify the box is locked to our contract
            box_address = box_data.get("address", "")
            if box_address and box_address != COINFLIP_P2S_ADDRESS:
                logger.warning(
                    "Box %s locked to wrong contract: %s (expected %s)",
                    req.boxId, box_address, COINFLIP_P2S_ADDRESS[:32],
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Failed to verify on-chain box %s: %s (continuing with off-chain record)", req.boxId, e)
    
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
        # On-chain register data (for reveal and refund flows)
        "commitment": req.commitment,
        "housePubKey": req.housePubKey,
        "houseAddress": req.houseAddress,
        "playerPubKey": req.playerPubKey,
        "playerSecret": req.playerSecret,
        "playerErgoTree": req.playerErgoTree,
    }

    # MAT-396/5.2: Atomic append + set registration to prevent race conditions
    async with _bet_lock:
        if req.betId in _bet_ids:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate betId: {req.betId} already exists. Replays are not allowed."
            )
        _bets.append(bet)
        _bet_ids.add(req.betId)

    # Update pool stats
    _pool_stats["totalBets"] += 1

    # Calculate fee
    fee = int(req.amount) * 3 // 100  # 3% house edge
    _pool_stats["totalFees"] = str(int(_pool_stats["totalFees"]) + fee)

    return PlaceBetResponse(
        success=True,
        txId="",  # In PoC, no actual tx broadcast — frontend handles this
        betId=req.betId,
        message="Bet placed. Waiting for on-chain confirmation.",
    )


# ─── Timeout & Refund Endpoints ─────────────────────────────────

# Timeout configuration (matches frontend TIMEOUT_DELTA = 100)
DEFAULT_TIMEOUT_DELTA = 100  # blocks
REVEAL_WINDOW_BLOCKS = 30  # blocks (must match coinflip_v2_final.es REVEAL_WINDOW)
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
        try:
            currentHeight = await _fetch_node_height()
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
        try:
            currentHeight = await _fetch_node_height()
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

    # MAT-231: Record P&L for refunded round
    try:
        from services.bankroll_pnl import record_round as record_pnl
        record_pnl(
            bet_id=bet_id,
            player_address=bet["playerAddress"],
            bet_amount_nanoerg=bet_amount,
            outcome="refunded",
            house_payout_nanoerg=refund,
            house_fee_nanoerg=fee,
            bet_timestamp=bet.get("timestamp"),
        )
    except Exception as pnl_err:
        logger.warning("Failed to record P&L for refund bet %s: %s", bet_id, pnl_err)

    return {
        "success": True,
        "betId": bet_id,
        "refundAmount": str(refund),
        "refundFee": str(fee),
        "message": f"Refund recorded. {refund/1e9:.4f} ERG returned to player (2% fee: {fee/1e9:.6f} ERG).",
    }


# ─── Refund Transaction Builder (MAT-28) ─────────────────────────────────────────
# Builds an unsigned EIP-12 transaction for the player to sign and broadcast
# via their wallet (Nautilus). The transaction spends the PendingBetBox via
# the REFUND spending path: HEIGHT >= timeoutHeight && playerProp && OUTPUTS(0) >= refundAmount.

class RefundTxRequest(BaseModel):
    bet_id: str
    """The off-chain bet identifier (betId)."""

class RefundTxResponse(BaseModel):
    success: bool = True
    unsigned_tx: str = ""
    bet_id: str = ""
    player_address: str = ""
    box_id: str = ""
    refund_amount: str = "0"
    refund_fee: str = "0"
    timeout_height: int = 0
    current_height: int = 0
    is_expired: bool = False
    message: str = ""


async def _fetch_node_height() -> int:
    """Fetch current block height from Ergo node."""
    import httpx
    node_url = os.environ.get("NODE_URL", "http://localhost:9052")
    api_key = os.environ.get("NODE_API_KEY", "")
    headers = {}
    if api_key:
        headers["api_key"] = api_key
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(f"{node_url}/info", headers=headers)
        resp.raise_for_status()
        info = resp.json()
        return info.get("fullHeight") or 0


async def _fetch_box_by_id(box_id: str) -> dict:
    """Fetch a UTXO box by its ID from the Ergo node."""
    import httpx
    node_url = os.environ.get("NODE_URL", "http://localhost:9052")
    api_key = os.environ.get("NODE_API_KEY", "")
    headers = {}
    if api_key:
        headers["api_key"] = api_key
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{node_url}/blockchain/box/{box_id}",
            headers=headers,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


@router.post("/bets/{bet_id}/build-refund-tx", response_model=RefundTxResponse)
async def build_refund_tx(bet_id: str):
    """
    Build an unsigned refund transaction for an expired bet (MAT-28).

    The player calls this endpoint to get an EIP-12 unsigned transaction
    that spends their PendingBetBox via the contract's REFUND spending path.
    The transaction returns 98% of the bet amount to the player (2% fee).

    Prerequisites:
    - Bet must be in 'pending' state
    - Current block height must be >= timeoutHeight (R8 register)
    - The PendingBetBox must still be unspent on-chain

    Flow:
    1. Look up bet record by betId
    2. Fetch current height from node
    3. Verify bet is expired (HEIGHT >= timeoutHeight)
    4. Fetch the on-chain box to get its value and registers
    5. Build unsigned EIP-12 tx with player as OUTPUTS(0) >= refundAmount
    6. Return base64-encoded unsigned tx for wallet signing

    The player then signs this via Nautilus wallet and broadcasts it.
    """
    from base64 import b64encode
    import json

    # 1. Find the bet
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

    # 2. Fetch current height
    try:
        current_height = await _fetch_node_height()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not fetch current block height from Ergo node"
        )

    # 3. Get timeout height
    timeout_h = bet.get("timeoutHeight", 0)
    if timeout_h <= 0:
        timeout_h = current_height + DEFAULT_TIMEOUT_DELTA

    is_expired = current_height >= timeout_h

    if not is_expired:
        blocks_remaining = timeout_h - current_height
        raise HTTPException(
            status_code=400,
            detail=f"Bet {bet_id} is not yet expired. "
                   f"{blocks_remaining} blocks remaining (expires at height {timeout_h}, "
                   f"current height {current_height})"
        )

    # 4. Fetch on-chain box (if we have a boxId)
    box_id = bet.get("boxId", "")
    box_value = int(bet["betAmount"])  # fallback to off-chain record
    box_registers = {}

    if box_id:
        try:
            box_data = await _fetch_box_by_id(box_id)
            if box_data is None:
                raise HTTPException(
                    status_code=410,
                    detail=f"PendingBetBox {box_id} no longer exists on-chain. "
                           f"It may have been spent (reveal or refund already processed)."
                )
            # Verify box is still unspent (spentStatus)
            if box_data.get("spentTransactionId"):
                raise HTTPException(
                    status_code=410,
                    detail=f"PendingBetBox {box_id} has already been spent. "
                           f"Cannot build refund transaction."
                )
            box_value = int(box_data.get("value", box_value))
            # Extract registers from the box
            if "additionalRegisters" in box_data:
                box_registers = box_data["additionalRegisters"]
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Failed to fetch box %s from node: %s (using off-chain values)", box_id, e)

    # 5. Calculate refund (98% of bet, 2% fee — matching contract)
    refund_amount = box_value - box_value // 50
    refund_fee = box_value // 50

    # 6. Build unsigned EIP-12 transaction
    # The REFUND spending path requires:
    #   - HEIGHT >= timeoutHeight (checked above)
    #   - playerProp (player must sign)
    #   - OUTPUTS(0).propositionBytes == playerProp.propBytes
    #   - OUTPUTS(0).value >= refundAmount
    #
    # We build a minimal tx: 1 input (the bet box) + 1 output (player receives refund)
    unsigned_tx_data = {
        "inputs": [
            {
                "boxId": box_id,
                "spendingProof": {
                    "proofBytes": "",
                    "extension": {},
                },
            }
        ],
        "dataInputs": [],
        "outputs": [
            {
                "value": str(refund_amount),
                "ergoTree": bet.get("playerErgoTree", ""),  # Player's P2PK tree (from wallet)
                "assets": [],
                "additionalRegisters": {},
                "creationHeight": current_height,
            }
        ],
    }

    unsigned_tx_b64 = b64encode(json.dumps(unsigned_tx_data).encode()).decode()

    return RefundTxResponse(
        success=True,
        unsigned_tx=unsigned_tx_b64,
        bet_id=bet_id,
        player_address=bet["playerAddress"],
        box_id=box_id,
        refund_amount=str(refund_amount),
        refund_fee=str(refund_fee),
        timeout_height=timeout_h,
        current_height=current_height,
        is_expired=True,
        message=(
            f"Refund transaction built. {refund_amount/1e9:.4f} ERG to player "
            f"(2% fee: {refund_fee/1e9:.6f} ERG). Sign via wallet and broadcast."
        ),
    )


@router.get("/bets/pending-with-timeout")
async def get_pending_bets_with_timeout(currentHeight: int = 0):
    """
    List all pending bets with their timeout status.
    
    Useful for monitoring which bets are approaching expiry.
    The off-chain bot should use this to prioritize reveal processing.
    """
    if currentHeight == 0:
        try:
            currentHeight = await _fetch_node_height()
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


# ─── Reveal Transaction Builder (MAT-394) ────────────────────────────────────────
# Builds REAL EIP-12 compatible reveal transactions using ergo_tx_builder.py
# which calls the Ergo node /wallet/transaction/send with rawInputs.
#
# The reveal spending path in coinflip_v2_final.es requires:
#   houseProp && commitmentOk && HEIGHT in [rngBlockHeight, timeoutHeight]
#   && OUTPUTS(0) to winner with correct amount

class RevealRequest(BaseModel):
    box_id: str
    block_hash: str  # block header ID used as RNG seed (CONTEXT.preHeader.parentId)


class RevealResponse(BaseModel):
    success: bool = True
    unsigned_tx: str = ""
    tx_id: str = ""          # Populated when tx is submitted on-chain
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
    3. Determine win/loss based on RNG (blake2b256(blockHash || secret)[0] % 2)
    4. Calculate the 97/50 payout (matching on-chain contract exactly)
    5. Build and return an unsigned EIP-12 transaction

    The unsigned tx can be signed externally or submitted via /bot/reveal-and-pay.
    
    Parameters:
    - box_id: The on-chain box ID of the pending bet
    - block_hash: Block header ID for RNG seed (hex, 64 chars)
    
    Returns:
    - unsigned_tx: Base64 encoded unsigned transaction (EIP-12)
    - bet_id: The bet identifier
    - player_wins: True if player won, False if house won
    - payout_amount: Amount to pay the player (betAmount * 97 / 50 for wins)
    """
    from ergo_tx_builder import (
        compute_rng,
        compute_win_payout,
        verify_commitment,
        build_unsigned_reveal_tx,
        get_node_height,
        fetch_unspent_box,
    )

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
    try:
        current_height = await get_node_height()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not fetch current block height from Ergo node"
        )

    # Verify timeout not expired (reveal must happen before timeoutHeight)
    timeout_h = bet.get("timeoutHeight", 0)
    if timeout_h > 0 and current_height >= timeout_h:
        raise HTTPException(
            status_code=400,
            detail=f"Bet {bet['betId']} has expired (height {current_height} >= timeout {timeout_h}). "
                   f"Player must use refund path."
        )

    # Verify reveal window: must be >= rngBlockHeight (timeoutHeight - 30)
    rng_block_height = timeout_h - REVEAL_WINDOW_BLOCKS if timeout_h > 0 else 0
    if rng_block_height > 0 and current_height < rng_block_height:
        raise HTTPException(
            status_code=400,
            detail=f"Reveal window not yet open: current {current_height} < rngHeight {rng_block_height}. "
                   f"House must wait until height {rng_block_height} to prevent block-grinding."
        )

    # Fetch on-chain box to verify it's still unspent
    box_data = await fetch_unspent_box(req.box_id)
    if box_data is None:
        raise HTTPException(
            status_code=410,
            detail=f"PendingBetBox {req.box_id} not found or already spent"
        )
    if box_data.get("spentTransactionId"):
        raise HTTPException(
            status_code=410,
            detail=f"PendingBetBox {req.box_id} has already been spent"
        )

    # Get register data
    commitment = bet.get("commitment", "")
    player_secret_hex = bet.get("playerSecret", "")
    if not commitment:
        raise HTTPException(status_code=400, detail="Missing commitment in bet record")
    if not player_secret_hex:
        raise HTTPException(status_code=400, detail="Missing player secret in bet record")

    # Compute RNG: blake2b256(blockHash_raw_bytes || playerSecret_raw_bytes)[0] % 2
    flip_result = compute_rng(req.block_hash, player_secret_hex)
    player_choice = 0 if bet["choice"]["side"] == "heads" else 1
    player_wins = flip_result == player_choice

    # Calculate payout using contract math: betAmount * 97 / 50 (integer division)
    bet_amount = int(bet["betAmount"])
    if player_wins:
        payout = compute_win_payout(bet_amount)
    else:
        payout = bet_amount  # House takes full bet

    # Build unsigned EIP-12 transaction
    # Player address from R5, house address from bet record
    player_addr = bet.get("playerAddress", "")
    house_addr = bet.get("houseAddress", "")  # House P2PK address for payout when house wins

    try:
        unsigned_tx_b64 = await build_unsigned_reveal_tx(
            bet_box_id=req.box_id,
            bet_amount=box_data.get("value", bet_amount),
            player_address=player_addr,
            house_address=house_addr,
            player_wins=player_wins,
            current_height=current_height,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build reveal transaction: {str(e)}"
        )

    # Update bet record (optimistic — actual confirmation happens after tx submission)
    bet["outcome"] = "win" if player_wins else "loss"
    bet["payout"] = str(payout)
    bet["actualOutcome"] = {
        "gameType": "coinflip",
        "result": "win" if player_wins else "loss",
        "rngValue": flip_result,
        "slot": 0,
        "multiplier": 1.94 if player_wins else 0,
    }
    bet["resolvedAtHeight"] = current_height

    # Record P&L
    try:
        from services.bankroll_pnl import record_round as record_pnl
        house_fee = int(bet_amount * 3 // 100) if player_wins else 0
        record_pnl(
            bet_id=bet["betId"],
            player_address=bet["playerAddress"],
            bet_amount_nanoerg=bet_amount,
            outcome="win" if player_wins else "loss",
            house_payout_nanoerg=payout,
            house_fee_nanoerg=house_fee,
            bet_timestamp=bet.get("timestamp"),
        )
    except Exception as pnl_err:
        logger.warning("Failed to record P&L for bet %s: %s", bet["betId"], pnl_err)

    # Update pool stats
    if player_wins:
        _pool_stats["playerWins"] += 1
        current_liquidity = int(_pool_stats["liquidity"])
        _pool_stats["liquidity"] = str(current_liquidity - payout)
    else:
        _pool_stats["houseWins"] += 1

    return RevealResponse(
        success=True,
        unsigned_tx=unsigned_tx_b64,
        bet_id=bet["betId"],
        player_address=player_addr,
        player_wins=player_wins,
        payout_amount=str(payout),
        message=f"Reveal tx built. Player {'wins' if player_wins else 'loses'}. "
                f"Payout: {payout:,} nanoERG ({payout/1e9:.4f} ERG). "
                f"RNG: blake2b256({req.block_hash[:16]}... || secret)[0] % 2 = {flip_result}"
    )


# ─── Auto-Reveal-and-Pay Endpoint (for off-chain bot) ──────────────────────


class RevealAndPayResponse(BaseModel):
    success: bool = True
    txId: str = ""
    bet_id: str = ""
    player_address: str = ""
    player_wins: bool = False
    payout_amount: str = "0"
    message: str = ""


@router.post("/bot/reveal-and-pay", response_model=RevealAndPayResponse)
async def reveal_and_pay(req: RevealRequest):
    """
    Build AND auto-submit a reveal transaction via the house node wallet.

    This endpoint is called by the off-chain bot. It:
    1. Finds the pending bet by box ID (or bet ID fallback)
    2. Verifies the bet is still pending and not expired
    3. Computes RNG using the provided block hash
    4. Builds a reveal transaction via ergo_tx_builder
    5. Signs and broadcasts via the Ergo node /wallet/transaction/send
    6. Updates off-chain bet record and P&L

    Prerequisites:
    - House wallet must be unlocked on the Ergo node
    - NODE_API_KEY must be configured
    - The PendingBetBox must be unspent on-chain
    """
    from ergo_tx_builder import (
        compute_rng,
        compute_win_payout,
        build_and_send_reveal_tx,
        get_node_height,
        fetch_unspent_box,
    )

    # 1. Find the bet by box ID or bet ID
    bet = None
    for b in _bets:
        if b.get("boxId") == req.box_id:
            bet = b
            break
        # Fallback: box_id may be passed as betId (when no on-chain box yet)
        if b.get("betId") == req.box_id:
            bet = b
            break

    if not bet:
        raise HTTPException(
            status_code=404,
            detail=f"Bet with box_id or bet_id {req.box_id} not found"
        )

    if bet["outcome"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Bet {bet['betId']} is already {bet['outcome']}, cannot reveal"
        )

    # 2. Get current block height
    try:
        current_height = await get_node_height()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not fetch current block height from Ergo node"
        )

    # Verify timeout window
    timeout_h = bet.get("timeoutHeight", 0)
    if timeout_h > 0 and current_height >= timeout_h:
        raise HTTPException(
            status_code=400,
            detail=f"Bet {bet['betId']} has expired at height {timeout_h}. "
                   f"Player must use refund path."
        )
    rng_block_height = timeout_h - REVEAL_WINDOW_BLOCKS if timeout_h > 0 else 0
    if rng_block_height > 0 and current_height < rng_block_height:
        raise HTTPException(
            status_code=400,
            detail=f"Reveal window not yet open (current {current_height} < rngHeight {rng_block_height})"
        )

    # 3. Verify on-chain box exists and is unspent
    box_id = bet.get("boxId", "")
    if box_id:
        box_data = await fetch_unspent_box(box_id)
        if box_data is None:
            raise HTTPException(
                status_code=410,
                detail=f"PendingBetBox {box_id} not found or already spent"
            )
        if box_data.get("spentTransactionId"):
            raise HTTPException(
                status_code=410,
                detail=f"PendingBetBox {box_id} has already been spent"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Bet has no on-chain boxId — cannot build reveal transaction"
        )

    # 4. Compute RNG
    player_secret_hex = bet.get("playerSecret", "")
    if not player_secret_hex:
        raise HTTPException(
            status_code=400,
            detail="Missing player secret in bet record — cannot compute RNG"
        )

    flip_result = compute_rng(req.block_hash, player_secret_hex)
    player_choice = 0 if bet["choice"]["side"] == "heads" else 1
    player_wins = flip_result == player_choice

    bet_amount = int(bet["betAmount"])

    # 5. Build and submit transaction via node wallet
    player_addr = bet.get("playerAddress", "")
    house_addr = bet.get("houseAddress", "")  # House P2PK address for payout when house wins

    tx_result = await build_and_send_reveal_tx(
        bet_box_id=box_id,
        bet_amount=box_data.get("value", bet_amount),
        player_address=player_addr,
        house_address=house_addr,
        player_wins=player_wins,
        current_height=current_height,
    )

    tx_id = tx_result.get("txId", "")
    if not tx_id:
        # Transaction failed to submit — don't update bet record
        return RevealAndPayResponse(
            success=False,
            txId="",
            bet_id=bet["betId"],
            player_address=player_addr,
            player_wins=player_wins,
            payout_amount="0",
            message=f"Reveal tx submission failed: {tx_result.get('message', 'unknown error')}",
        )

    # 6. Update bet record (only after successful on-chain submission)
    if player_wins:
        payout = compute_win_payout(bet_amount)
    else:
        payout = bet_amount

    bet["outcome"] = "win" if player_wins else "loss"
    bet["payout"] = str(payout)
    bet["txId"] = tx_id
    bet["actualOutcome"] = {
        "gameType": "coinflip",
        "result": "win" if player_wins else "loss",
        "rngValue": flip_result,
        "slot": 0,
        "multiplier": 1.94 if player_wins else 0,
    }
    bet["resolvedAtHeight"] = current_height

    # Update pool stats
    if player_wins:
        _pool_stats["playerWins"] += 1
        current_liquidity = int(_pool_stats["liquidity"])
        _pool_stats["liquidity"] = str(current_liquidity - payout)
    else:
        _pool_stats["houseWins"] += 1

    # Record P&L
    try:
        from services.bankroll_pnl import record_round as record_pnl
        house_fee = int(bet_amount * 3 // 100) if player_wins else 0
        record_pnl(
            bet_id=bet["betId"],
            player_address=bet["playerAddress"],
            bet_amount_nanoerg=bet_amount,
            outcome="win" if player_wins else "loss",
            house_payout_nanoerg=payout,
            house_fee_nanoerg=house_fee,
            bet_timestamp=bet.get("timestamp"),
        )
    except Exception as pnl_err:
        logger.warning("Failed to record P&L for bet %s: %s", bet["betId"], pnl_err)

    result_text = f"Player {'wins' if player_wins else 'loses'}. Payout: {payout:,} nanoERG. TxId: {tx_id}"

    return RevealAndPayResponse(
        success=True,
        txId=tx_id,
        bet_id=bet["betId"],
        player_address=player_addr,
        player_wins=player_wins,
        payout_amount=str(payout),
        message=result_text,
    )
