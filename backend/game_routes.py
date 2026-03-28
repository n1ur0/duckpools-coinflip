"""
DuckPools - Game Routes

Frontend-facing endpoints for the coinflip game PoC.
These routes match the API contract expected by the React frontend.

MAT-309: Rebuild backend API to match frontend contract.
"""

from datetime import datetime, timezone
from typing import List, Optional, Literal
import re
import uuid as uuid_module

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from validators import validate_ergo_address, ValidationError

router = APIRouter(tags=["game"])


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
    resolvedAtHeight: Optional[int] = None


class PlaceBetRequest(BaseModel):
    address: str = Field(..., min_length=1, description="Player Ergo address (P2PK or P2S)")
    amount: str = Field(..., min_length=1, description="Bet amount in nanoERG (must be positive)")
    choice: Literal[0, 1] = Field(..., description="0 = Heads, 1 = Tails")
    commitment: str = Field(..., min_length=64, max_length=64, description="64-char hex hash (blake2b256(secret||choice))")
    betId: str = Field(..., min_length=36, max_length=36, description="UUID v4 format")

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate Ergo address format using validators.py."""
        try:
            return validate_ergo_address(v)
        except ValidationError as e:
            raise ValueError(f"Invalid Ergo address: {e}")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        """Validate amount is a positive integer within pool limits."""
        # Must be numeric
        if not v.isdigit():
            raise ValueError("Amount must be a positive integer (nanoERG)")

        amount_int = int(v)

        # Must be > 0
        if amount_int <= 0:
            raise ValueError("Amount must be greater than 0")

        # Must be >= minimum box value (0.001 ERG = 1,000,000 nanoERG)
        MIN_BOX_VALUE = 1_000_000
        if amount_int < MIN_BOX_VALUE:
            raise ValueError(f"Amount must be at least {MIN_BOX_VALUE:,} nanoERG (0.001 ERG)")

        # Check against pool liquidity (50,000 ERG = 50,000,000,000,000 nanoERG)
        MAX_POOL_LIQUIDITY = 50_000_000_000_000
        if amount_int > MAX_POOL_LIQUIDITY:
            raise ValueError(f"Amount exceeds pool liquidity ({MAX_POOL_LIQUIDITY:,} nanoERG)")

        return v

    @field_validator("commitment")
    @classmethod
    def validate_commitment(cls, v: str) -> str:
        """Validate commitment is a 64-character hex string (256-bit hash)."""
        v = v.strip().lower()
        if not re.match(r"^[0-9a-f]{64}$", v):
            raise ValueError("Commitment must be a 64-character hex string (256-bit hash)")
        return v

    @field_validator("betId")
    @classmethod
    def validate_bet_id(cls, v: str) -> str:
        """Validate betId is a valid UUID v4 format."""
        try:
            uuid_module.UUID(v, version=4)
        except ValueError:
            raise ValueError("betId must be a valid UUID v4 format")
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


@router.post("/place-bet", response_model=PlaceBetResponse)
async def place_bet(req: PlaceBetRequest):
    """Place a coinflip bet from BetForm.tsx / CoinFlipGame.tsx."""
    now = datetime.now(timezone.utc).isoformat()

    side = "heads" if req.choice == 0 else "tails"

    bet = {
        "betId": req.betId,
        "txId": "",  # Will be filled when tx is actually broadcast
        "boxId": "",
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
