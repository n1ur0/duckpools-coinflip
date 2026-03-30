"""
DuckPools - Game Routes

Frontend-facing endpoints for the coinflip game PoC.
These routes match the API contract expected by the React frontend.

MAT-309: Rebuild backend API to match frontend contract.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import asyncio
import json
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
# coinflip_v2_final.es — Phase 2 production contract
# Compiled 2026-03-30 against node v6.0.3 (Lithos testnet, treeVersion=1)
# Values MUST match smart-contracts/coinflip_deployed.json
#
# NOTE: The ergoTree hex is not available from Lithos /script/p2sAddress.
# The P2S address is sufficient for all operations. The bankroll monitoring
# uses the ergoTree hash (SHA256 of ergoTree bytes) for byErgoTree scans.
# We load the deployed address from coinflip_deployed.json at startup.
import json as _json
from pathlib import Path as _Path

_deployed_path = _Path(__file__).parent.parent / "smart-contracts" / "coinflip_deployed.json"
try:
    with open(_deployed_path) as _f:
        _deployed = _json.load(_f)
    COINFLIP_P2S_ADDRESS = _deployed["p2sAddress"]
except Exception:
    # Fallback: use the known v2_final testnet address
    COINFLIP_P2S_ADDRESS = "3QHN2BNDtWXVmBbwuyZNijhcAd92Ww9kD7j8PbrqVfjJsyabJ134mEuwJykbET5jsbebLtWfGMtSJUubgMdK5gfF6ve6WqM6gBBxQzZo58BoQDRbFf3qqvpNhiStgVFibfu55u7d31u6igiaWuEqyMQEEDCYxFgoMYK8VHDuP3hjXCUDdbyAfiEwYmAeHH2QKFrYUQV5bNWafbvhRgSZnDFc3bXwohrmP4rnNaMxrNJ9TC7r9QWm3yNFrrQj6CphdciEcYKh27H6UoeF9yPZjHyqGRZWMJsZGWZSwibxgebZW8Hqp6CLRrabSYPEwrKjtmXBdXtmb63x"

# ergoTree hex is empty in deployed JSON (Lithos limitation).
# Backend uses P2S address for all operations. SDK builds txs from address.
COINFLIP_ERGO_TREE = ""  # Not needed — P2S address is sufficient for all ops

# Register layout (must match coinflip_v2_final.es and frontend coinflipService.ts)
# R4: housePubKey (Coll[Byte])     — 33-byte compressed public key
# R5: playerPubKey (Coll[Byte])    — 33-byte compressed public key
# R6: commitmentHash (Coll[Byte])  — blake2b256(secret || choice_byte)
# R7: playerChoice (Int)           — 0=heads, 1=tails
# R8: timeoutHeight (Int)          — block height for refund
# R9: playerSecret (Coll[Byte])    — player's random secret bytes (8 bytes)
#
# Derived: rngBlockHeight = timeoutHeight - 30 (REVEAL_WINDOW constant)
# Reveal window: blocks [rngBlockHeight, timeoutHeight]
# House edge: 3% (player wins 1.94x = betAmount * 97 / 50)
# Refund fee: 2% (player gets 0.98x = betAmount - betAmount/50)


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


class PlaceBetResponse(BaseModel):
    success: bool = True
    txId: str = ""
    betId: str = ""
    boxId: str = ""  # Expected box ID (estimated from unsigned tx)
    message: str = ""
    contractAddress: str = COINFLIP_P2S_ADDRESS
    timeoutDelta: int = 100  # blocks
    timeoutHeight: int = 0  # Computed timeout height
    unsignedTx: str = ""  # Base64-encoded unsigned EIP-12 transaction for wallet signing
    registers: Optional[dict] = None  # Register values for verification


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
    """Place a coinflip bet — creates PendingBetBox on-chain.

    Flow:
    1. Validate all inputs (address, amount, choice, commitment)
    2. Verify commitment = blake2b256(secret || choice) if secret provided
    3. Fetch current height from node, compute timeoutHeight
    4. Build unsigned EIP-12 tx with PendingBetBox output (R4-R9 registers)
    5. Record bet in off-chain store (atomic under lock to prevent replay)
    6. Return unsigned tx for frontend to sign via Nautilus wallet

    The PendingBetBox output uses coinflip_v2_final.es contract:
      ergoTree: COINFLIP_P2S_ADDRESS
      R4: housePubKey (Coll[Byte])
      R5: playerPubKey (Coll[Byte])
      R6: commitmentHash (Coll[Byte])
      R7: playerChoice (Int)
      R8: timeoutHeight (Int)
      R9: playerSecret (Coll[Byte])
    """
    from base64 import b64encode
    from vlq_serializer import VLQSerializer

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
    
    # Fetch current height from node to compute timeoutHeight
    try:
        current_height = await _fetch_node_height()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not fetch current block height from Ergo node"
        )

    # Compute timeoutHeight: current + delta (default 100 blocks)
    timeout_height = req.timeoutHeight if req.timeoutHeight > 0 else current_height + DEFAULT_TIMEOUT_DELTA
    side = "heads" if req.choice == 0 else "tails"

    # Build register values for the PendingBetBox using VLQ serializer
    serializer = VLQSerializer()

    # R4: housePubKey (Coll[Byte]) — 33-byte compressed public key
    r4_serialized = serializer.serialize(req.housePubKey, ErgoType.COLL_BYTE).value if req.housePubKey else ""
    # R5: playerPubKey (Coll[Byte]) — 33-byte compressed public key
    r5_serialized = serializer.serialize(req.playerPubKey, ErgoType.COLL_BYTE).value if req.playerPubKey else ""
    # R6: commitmentHash (Coll[Byte]) — 32 bytes blake2b256
    r6_serialized = serializer.serialize(req.commitment, ErgoType.COLL_BYTE).value
    # R7: playerChoice (Int) — 0 or 1
    r7_serialized = serializer.serialize(req.choice, ErgoType.INT).value
    # R8: timeoutHeight (Int)
    r8_serialized = serializer.serialize(timeout_height, ErgoType.INT).value
    # R9: playerSecret (Coll[Byte]) — 8 or 32 random bytes
    r9_serialized = serializer.serialize(req.playerSecret, ErgoType.COLL_BYTE).value if req.playerSecret else ""

    registers = {
        "R4": r4_serialized,
        "R5": r5_serialized,
        "R6": r6_serialized,
        "R7": r7_serialized,
        "R8": r8_serialized,
        "R9": r9_serialized,
    }

    # Build unsigned EIP-12 transaction
    # The player funds the PendingBetBox from their wallet.
    # OUTPUTS(0) = PendingBetBox with contract ergoTree + bet amount + registers
    # The frontend/wallet will add the change output and input boxes.
    unsigned_tx = {
        "inputs": [],  # Player's wallet will fill these in
        "dataInputs": [],
        "outputs": [{
            "ergoTree": COINFLIP_P2S_ADDRESS,  # Contract address (P2S)
            "value": str(bet_amount),
            "assets": [],
            "additionalRegisters": registers,
            "creationHeight": current_height,
        }],
    }

    unsigned_tx_b64 = b64encode(
        json.dumps(unsigned_tx, separators=(",", ":")).encode()
    ).decode()

    bet = {
        "betId": req.betId,
        "txId": "",  # Will be filled when frontend broadcasts the signed tx
        "boxId": "",  # Will be filled when tx is confirmed on-chain
        "playerAddress": req.address,
        "gameType": "coinflip",
        "choice": {"gameType": "coinflip", "side": side},
        "betAmount": req.amount,
        "outcome": "pending",
        "actualOutcome": None,
        "payout": "0",
        "payoutMultiplier": 0.97,
        "timestamp": now,
        "blockHeight": current_height,
        "timeoutHeight": timeout_height,
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

    return PlaceBetResponse(
        success=True,
        betId=req.betId,
        message="Bet placed. Sign the unsigned transaction via Nautilus wallet and broadcast to create PendingBetBox on-chain.",
        timeoutHeight=timeout_height,
        unsignedTx=unsigned_tx_b64,
        registers={
            "R4": f"housePubKey ({len(req.housePubKey) // 2} bytes)" if req.housePubKey else "housePubKey (MISSING)",
            "R5": f"playerPubKey ({len(req.playerPubKey) // 2} bytes)" if req.playerPubKey else "playerPubKey (MISSING)",
            "R6": f"commitmentHash ({len(req.commitment) // 2} bytes)",
            "R7": f"playerChoice ({req.choice})",
            "R8": f"timeoutHeight ({timeout_height})",
            "R9": f"playerSecret ({len(req.playerSecret) // 2 if req.playerSecret else 0} bytes)",
        },
    )


# ─── Bet Confirmation Endpoint ────────────────────────────────────

class ConfirmBetRequest(BaseModel):
    txId: str
    boxId: str = ""  # On-chain box ID (may not be known immediately)


@router.post("/bets/{bet_id}/confirm")
async def confirm_bet(bet_id: str, req: ConfirmBetRequest):
    """
    Confirm a bet was placed on-chain after frontend signs and broadcasts.

    Called by the frontend after Nautilus wallet signs and broadcasts the
    unsigned transaction returned by /place-bet. Updates the off-chain
    record with the txId and boxId for reveal/refund tracking.
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
            detail=f"Bet {bet_id} is already {bet['outcome']}, cannot confirm"
        )

    bet["txId"] = req.txId
    if req.boxId:
        bet["boxId"] = req.boxId

    return {
        "success": True,
        "betId": bet_id,
        "txId": req.txId,
        "boxId": req.boxId,
        "message": f"Bet {bet_id} confirmed on-chain. PendingBetBox tracked for reveal.",
    }


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


# ─── Reveal Transaction Builder (MAT-355 / MAT-394) ──────────────────────
# Builds a real EIP-12 transaction via the Ergo node wallet API.
# The house wallet signs and broadcasts the transaction that spends
# the PendingBetBox, verifies the commitment on-chain, and pays
# the winner according to the coinflip_v2_final.es contract.
#
# Contract reveal path (coinflip_v2_final.es):
#   houseProp && commitmentOk &&
#   HEIGHT >= rngBlockHeight && HEIGHT <= timeoutHeight &&
#   if (playerWins) OUTPUTS(0) == playerProp && value >= winPayout
#   else             OUTPUTS(0) == houseProp && value >= betAmount
#
# RNG: blake2b256(CONTEXT.preHeader.parentId || playerSecret)[0] % 2
# The node automatically uses the parent block header for CONTEXT.preHeader.
# We just need to ensure we submit the tx within the reveal window.

REVEAL_WINDOW_BLOCKS = 30  # Must match contract constant


class RevealRequest(BaseModel):
    box_id: str
    """The on-chain PendingBetBox ID to reveal."""

class RevealResponse(BaseModel):
    success: bool = True
    tx_id: str = ""
    bet_id: str = ""
    player_address: str = ""
    player_wins: bool = False
    payout_amount: str = "0"
    house_profit: str = "0"
    rng_value: int = 0
    message: str = ""


async def _find_bet_by_box_id(box_id: str) -> Optional[dict]:
    """Find an off-chain bet record by on-chain box ID."""
    for b in _bets:
        if b.get("boxId") == box_id:
            return b
    return None


def _compute_rng_deterministic(block_hash_hex: str, player_secret_hex: str) -> int:
    """
    Compute RNG result matching on-chain contract exactly.

    Contract: blake2b256(CONTEXT.preHeader.parentId || playerSecret)(0) % 2
    - block_hash_hex: the parent block ID (32 bytes, hex)
    - player_secret_hex: R9 register value (raw bytes, hex)

    Returns: 0 (heads) or 1 (tails)
    """
    block_bytes = bytes.fromhex(block_hash_hex)
    secret_bytes = bytes.fromhex(player_secret)
    combined = block_bytes + secret_bytes
    result = hashlib.blake2b(combined, digest_size=32).digest()
    return result[0] % 2


async def _build_and_submit_reveal_tx(
    bet: dict,
    current_height: int,
) -> tuple:
    """
    Build and submit a reveal transaction via the house wallet.

    Uses /wallet/transaction/send which requires the house wallet to be
    unlocked on the Ergo node.

    Returns (tx_id, player_wins, payout_amount, rng_value, error_msg)
    """
    import httpx

    bet_box_id = bet["boxId"]
    bet_amount = int(bet["betAmount"])
    player_secret = bet.get("playerSecret", "")
    house_pub_key = bet.get("housePubKey", "")
    player_pub_key = bet.get("playerPubKey", "")
    timeout_height = bet.get("timeoutHeight", 0)

    if not player_secret:
        return "", False, 0, 0, "Missing playerSecret in bet record"
    if not bet_box_id:
        return "", False, 0, 0, "Missing boxId in bet record"

    # Fetch the parent block header for RNG
    # We use the current height's block (which will be the parent when tx is included)
    node_url = os.environ.get("NODE_URL", "http://localhost:9052")
    api_key = os.environ.get("NODE_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api_key"] = api_key

    async with httpx.AsyncClient(timeout=15) as client:
        # Get block headers at current height (to get parentId for RNG)
        try:
            blocks_resp = await client.get(
                f"{node_url}/blocks/at/{current_height}",
                headers=headers,
            )
            blocks_resp.raise_for_status()
            blocks = blocks_resp.json()
            if not blocks:
                return "", False, 0, 0, f"No block at height {current_height}"
            # Use the header ID of the current block as the seed
            # (this will be the parent block when the tx is included in the next block)
            block_header_id = blocks[0].get("headerId", "")
            if not block_header_id:
                return "", False, 0, 0, "Block header has no headerId"
        except Exception as e:
            return "", False, 0, 0, f"Failed to fetch block header: {e}"

        # Compute RNG
        rng_value = _compute_rng_deterministic(block_header_id, player_secret)
        player_choice = 0 if bet["choice"]["side"] == "heads" else 1
        player_wins = (rng_value == player_choice)

        # Calculate payout per contract
        if player_wins:
            payout = int(bet_amount * 97 // 50)  # 1.94x (3% house edge)
            recipient_address = bet["playerAddress"]
        else:
            payout = bet_amount  # House takes full bet
            recipient_address = os.environ.get("HOUSE_ADDRESS", "")

        # Build transaction request for /wallet/transaction/send
        # The contract requires:
        #   - INPUTS: the PendingBetBox (must have correct registers)
        #   - OUTPUTS(0): winner receives payout at correct proposition
        #
        # We use rawInputs to specify the exact bet box as input,
        # and requests to specify the output.
        tx_request = {
            "requests": [{
                "address": recipient_address,
                "value": str(payout),
                "assets": [],
            }],
            "rawInputs": [bet_box_id],
            "fee": 1000000,  # 0.001 ERG fee
            "dataInputs": [],
        }

        try:
            tx_resp = await client.post(
                f"{node_url}/wallet/transaction/send",
                headers=headers,
                json=tx_request,
            )
            if tx_resp.status_code == 200:
                tx_id = tx_resp.text.strip()
                if tx_id.startswith('"') and tx_id.endswith('"'):
                    tx_id = tx_id[1:-1]
                return tx_id, player_wins, payout, rng_value, ""
            else:
                error_detail = tx_resp.text[:500]
                return "", False, 0, 0, f"Node rejected tx ({tx_resp.status_code}): {error_detail}"
        except Exception as e:
            return "", False, 0, 0, f"Failed to submit reveal tx: {e}"


@router.post("/bot/build-reveal-tx", response_model=RevealResponse)
async def build_reveal_tx(req: RevealRequest):
    """
    Build AND submit a reveal transaction for a pending bet.

    Called by the off-chain bot. This endpoint:
    1. Finds the pending bet by box ID
    2. Fetches current block header from node for RNG seed
    3. Computes RNG: blake2b256(parentBlockId || playerSecret)[0] % 2
    4. Determines winner and calculates payout (97/50 for player win)
    5. Builds and submits the reveal tx via house wallet
    6. Records P&L

    Prerequisites:
    - House wallet must be unlocked on the Ergo node
    - NODE_API_KEY must be configured
    - PendingBetBox must be unspent on-chain
    - Current height must be within reveal window
      [timeoutHeight - 30, timeoutHeight]
    """
    # 1. Find the bet
    bet = await _find_bet_by_box_id(req.box_id)
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

    # 2. Get current block height
    try:
        current_height = await _fetch_node_height()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not fetch current block height from Ergo node"
        )

    # 3. Verify we're within the reveal window
    timeout_h = bet.get("timeoutHeight", 0)
    if timeout_h > 0:
        rng_block_height = timeout_h - REVEAL_WINDOW_BLOCKS
        if current_height < rng_block_height:
            blocks_until = rng_block_height - current_height
            raise HTTPException(
                status_code=400,
                detail=f"Reveal window not open yet. {blocks_until} blocks until reveal "
                       f"(rngBlockHeight={rng_block_height}, current={current_height})"
            )
        if current_height > timeout_h:
            raise HTTPException(
                status_code=400,
                detail=f"Bet has expired (timeoutHeight={timeout_h}, current={current_height}). "
                       f"Player must use refund path."
            )

    # 4. Verify the box is still unspent on-chain
    box_data = await _fetch_box_by_id(req.box_id)
    if box_data is None:
        raise HTTPException(
            status_code=410,
            detail=f"PendingBetBox {req.box_id} no longer exists on-chain"
        )
    if box_data.get("spentTransactionId"):
        raise HTTPException(
            status_code=410,
            detail=f"PendingBetBox {req.box_id} already spent"
        )

    # 5. Build and submit the reveal transaction
    tx_id, player_wins, payout, rng_value, error_msg = await _build_and_submit_reveal_tx(
        bet, current_height
    )

    if error_msg:
        raise HTTPException(
            status_code=500,
            detail=f"Reveal transaction failed: {error_msg}"
        )

    # 6. Update off-chain bet record
    bet_amount = int(bet["betAmount"])
    outcome_str = "win" if player_wins else "loss"
    bet["outcome"] = outcome_str
    bet["payout"] = str(payout)
    bet["txId"] = tx_id
    bet["actualOutcome"] = {
        "gameType": "coinflip",
        "result": outcome_str,
        "rngValue": rng_value,
        "slot": 0,
        "multiplier": 1.94 if player_wins else 0,
    }
    bet["resolvedAtHeight"] = current_height

    # 7. Update pool stats
    if player_wins:
        _pool_stats["playerWins"] += 1
        current_liquidity = int(_pool_stats["liquidity"])
        _pool_stats["liquidity"] = str(current_liquidity - payout)
    else:
        _pool_stats["houseWins"] += 1

    # 8. Record P&L
    house_fee = int(bet_amount * 3 // 100) if player_wins else bet_amount
    house_profit = (bet_amount - payout) if player_wins else bet_amount
    try:
        from services.bankroll_pnl import record_round as record_pnl
        record_pnl(
            bet_id=bet["betId"],
            player_address=bet["playerAddress"],
            bet_amount_nanoerg=bet_amount,
            outcome=outcome_str,
            house_payout_nanoerg=payout,
            house_fee_nanoerg=house_fee,
            bet_timestamp=bet.get("timestamp"),
        )
    except Exception as pnl_err:
        logger.warning("Failed to record P&L for bet %s: %s", bet["betId"], pnl_err)

    result_text = (
        f"Player {'WINS' if player_wins else 'LOSES'}. "
        f"RNG={rng_value}, Payout={payout:,} nanoERG. "
        f"TxId={tx_id}"
    )

    return RevealResponse(
        success=True,
        tx_id=tx_id,
        bet_id=bet["betId"],
        player_address=bet["playerAddress"],
        player_wins=player_wins,
        payout_amount=str(payout),
        house_profit=str(house_profit),
        rng_value=rng_value,
        message=result_text,
    )


# ─── Auto-Reveal-and-Pay Endpoint (DEPRECATED — use /bot/build-reveal-tx) ─
# Kept for backward compatibility with existing off-chain bot integrations.
# Now delegates to build_reveal_tx internally.


class RevealAndPayResponse(BaseModel):
    success: bool = True
    tx_id: str = ""
    bet_id: str = ""
    player_address: str = ""
    player_wins: bool = False
    payout_amount: str = "0"
    message: str = ""


@router.post("/bot/reveal-and-pay", response_model=RevealAndPayResponse)
async def reveal_and_pay(req: RevealRequest):
    """
    Build AND auto-submit a reveal transaction via the house node wallet.

    DEPRECATED: Use /bot/build-reveal-tx instead (same functionality).
    This endpoint is kept for backward compatibility.

    Prerequisites:
    - House wallet must be unlocked on the Ergo node
    - NODE_API_KEY must be configured
    - The PendingBetBox must be unspent on-chain
    """
    # Delegate to the improved build_reveal_tx endpoint
    result = await build_reveal_tx(req)

    return RevealAndPayResponse(
        success=result.success,
        tx_id=result.tx_id,
        bet_id=result.bet_id,
        player_address=result.player_address,
        player_wins=result.player_wins,
        payout_amount=result.payout_amount,
        message=result.message,
    )
