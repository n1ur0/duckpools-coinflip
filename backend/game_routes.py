"""
DuckPools - Game Routes

Frontend-facing endpoints for the coinflip game PoC.
These routes match the API contract expected by the React frontend.

MAT-309: Rebuild backend API to match frontend contract.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Query
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
    resolvedAtHeight: Optional[int] = None


class PlaceBetRequest(BaseModel):
    address: str
    amount: str
    choice: int  # 0 = Heads, 1 = Tails
    commitment: str
    betId: str

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
        if amount > 100_000_000_000:
            raise ValueError("maximum bet is 100 ERG (100,000,000,000 nanoERG)")
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
        return v

    @field_validator("betId")
    @classmethod
    def validate_bet_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("betId is required")
        return v.strip()


class PlaceBetResponse(BaseModel):
class PlaceBetResponse(BaseModel):
    success: bool = True
    txId: str = ""
    betId: str = ""
    message: str = ""

class RevealRequest(BaseModel):
    box_id: str
    block_hash: str

    @field_validator('box_id')
    def validate_box_id(cls, v: str) -> str:
        if not v:
            raise ValueError('Box ID cannot be empty')
        return v

    @field_validator('block_hash')
    def validate_block_hash(cls, v: str) -> str:
        if len(v) != 64:  # block hash is 32 bytes = 64 hex chars
            raise ValueError('Block hash must be 64 hex characters')
        return v

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

class RevealResponse(BaseModel):
    unsigned_tx: Dict[str, Any]
    player_wins: bool
    payout_amount: str
    block_hash: str
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


# ─── Database integration ────────────────────────────────────────

from .database import (
    init_db, close_db, create_bet_table, create_pool_stats_table,
    insert_or_update_pool_stats, get_pool_stats, insert_bet, get_bets_by_address,
    update_bet_outcome, get_all_bets, get_bet_count, get_player_win_rate,
    get_player_stats, get_leaderboard, get_total_players, migrate_from_in_memory
)

# Initialize database on startup
import asyncio
asyncio.create_task(init_db())

# Create tables if they don't exist
async def ensure_tables():
    await create_bet_table()
    await create_pool_stats_table()
    # Initialize pool stats if empty
    stats = await get_pool_stats()
    if stats.totalBets == 0:
        await insert_or_update_pool_stats(stats)

asyncio.create_task(ensure_tables())


# ─── Routes ───────────────────────────────────────────────────────

@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard():
    """Leaderboard for Leaderboard.tsx."""
    players = await get_leaderboard()
    total_players = await get_total_players()
    
    return LeaderboardResponse(
        players=players,
        totalPlayers=total_players,
        sortBy="netPnL",
    )


@router.get("/history/{address}", response_model=List[BetRecord])
async def get_history(address: str):
    """Bet history for GameHistory.tsx."""
    bets = await get_bets_by_address(address)
    return bets


@router.get("/player/stats/{address}", response_model=PlayerStats)
async def get_player_stats(address: str):
    """Player stats for StatsDashboard.tsx."""
    stats = await get_player_stats(address)
    
    return PlayerStats(
        address=address,
        totalBets=stats["totalBets"],
        wins=stats["wins"],
        losses=stats["losses"],
        pending=stats["pending"],
        winRate=stats["winRate"],
        totalWagered=stats["totalWagered"],
        totalWon=stats["totalWon"],
        totalLost=stats["totalLost"],
        netPnL=stats["netPnL"],
        biggestWin=stats["biggestWin"],
        currentStreak=stats["currentStreak"],
        longestWinStreak=stats["longestWinStreak"],
        longestLossStreak=stats["longestLossStreak"],
        compPoints=stats["compPoints"],
        compTier=stats["compTier"],
    )


@router.get("/player/comp/{address}", response_model=CompPointsResponse)
async def get_player_comp(address: str):
    """Comp points for CompPoints.tsx."""
    # Get player stats which includes comp points
    stats = await get_player_stats(address)
    comp_points = stats["compPoints"]
    current_tier = stats["compTier"]

    tier_thresholds = {"Bronze": 0, "Silver": 100, "Gold": 1000, "Diamond": 10000}
    tier_order = ["Bronze", "Silver", "Gold", "Diamond"]

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


@router.get("/contract-info")
async def contract_info():
    """Return compiled coinflip contract address and register layout.
    Frontend needs this to build transactions targeting the contract."""
    return {
        "p2sAddress": COINFLIP_P2S_ADDRESS,
        "ergoTree": COINFLIP_ERGO_TREE,
        "registers": {
            "R4": "housePubKey (Coll[Byte])",
            "R5": "playerPubKey (Coll[Byte])",
            "R6": "commitmentHash (Coll[Byte])",
            "R7": "playerChoice (Int)",
            "R8": "timeoutHeight (Int)",
            "R9": "playerSecret (Coll[Byte])",
        },
    }


@router.post("/place-bet", response_model=PlaceBetResponse)
async def place_bet(req: PlaceBetRequest):
    """Place a coinflip bet from BetForm.tsx / CoinFlipGame.tsx."""
    now = datetime.now(timezone.utc).isoformat()

    side = "heads" if req.choice == 0 else "tails"

    bet = BetRecord(
        betId=req.betId,
        txId="",  # Will be filled when tx is actually broadcast
        boxId="",
        playerAddress=req.address,
        gameType="coinflip",
        choice={"gameType": "coinflip", "side": side},
        betAmount=req.amount,
        outcome="pending",
        actualOutcome=None,
        payout="0",
        payoutMultiplier=0.97,
        timestamp=now,
        blockHeight=0,
        resolvedAtHeight=None,
    )
    
    # Insert bet into database
    await insert_bet(bet)

    # Update pool stats
    stats = await get_pool_stats()
    stats.totalBets += 1
    fee = int(req.amount) * 3 // 100  # 3% house edge
    stats.totalFees = str(int(stats.totalFees) + fee)
    await insert_or_update_pool_stats(stats)

    return PlaceBetResponse(
        success=True,
        txId="",  # In PoC, no actual tx broadcast
        betId=req.betId,
        message="Bet placed. Waiting for on-chain confirmation.",
    )


@router.post("/bot/build-reveal-tx", response_model=RevealResponse)
async def build_reveal_tx(req: RevealRequest):
    """Build an unsigned EIP-12 transaction for the house to reveal a coinflip bet.
    
    This endpoint is used by the off-chain bot to build reveal transactions.
    The bot will then sign and submit the transaction to the Ergo network.
    """
    # Initialize Ergo node client
    node = ErgoNodeClient(node_url=NODE_URL, api_key=***

    # Fetch the commit box from the node
    box_resp = await node.utxo_by_box_id(req.box_id)
    commit_box = box_resp[0]
    
    # Extract necessary data from the commit box
    bet_amount = commit_box.value
    player_address = commit_box.address
    
    # Calculate win payout (97/50 multiplier)
    win_payout = (bet_amount * 97) // 50
    
    # Fetch the previous block header for RNG
    prev_block_header = await node.block_header(req.block_hash)
    
    # Get the player's secret and choice from the commit box registers
    registers = commit_box.additional_registers
    r9_encoded = registers.get("R9")
    r7_encoded = registers.get("R7")
    
    if not r9_encoded or not r7_encoded:
        raise HTTPException(
            status_code=400,
            detail="Commit box missing required registers (R9 or R7)"
        )
    
    # Decode the registers (simplified - actual decoding would be more complex)
    # In a real implementation, you'd need to decode the Coll[Byte] and Int formats
    player_secret=***  # This would be decoded properly
    player_choice = int(r7_encoded)  # This would be decoded properly
    
    # Simulate the on-chain RNG to determine outcome
    # Contract: blake2b256(prevBlockHash ++ playerSecret)[0] % 2
    rng_input = prev_block_header + player_secret
    rng_hash = blake2b256(rng_input)
    flip_result = rng_hash[0] % 2
    player_wins = flip_result == player_choice
    
    # Build the transaction
    # This is a simplified version - actual implementation would use Fleet SDK
    unsigned_tx = {
        "inputs": [
            {
                "boxId": req.box_id,
                "value": bet_amount,
                "ergoTree": COINFLIP_ERGO_TREE,
                "creationHeight": commit_box.creation_height,
                "assets": commit_box.assets,
                "additionalRegisters": registers,
                "transactionId": commit_box.transaction_id,
                "index": commit_box.index,
            }
        ],
        "outputs": [
            {
                "value": win_payout if player_wins else bet_amount,
                "address": player_address if player_wins else HOUSE_ADDRESS,
                "creationHeight": node.current_height,
                "assets": commit_box.assets if player_wins else [],
                "additionalRegisters": {},
            }
        ],
        "dataInputs": [],
        "fee": 1000000,  # 1 ERG fee
        "inputsRaw": [],
        "outputsRaw": [],
        "dataInputsRaw": [],
        "version": 4,
    }
    
    return RevealResponse(
        unsigned_tx=unsigned_tx,
        player_wins=player_wins,
        payout_amount=str(win_payout if player_wins else bet_amount),
        block_hash=req.block_hash,
    )

@router.post("/admin/migrate-data")
async def migrate_data():
    """Migrate data from in-memory store to database."""
    # This would be called to migrate existing data
    # In a real implementation, you'd need to get the in-memory data and migrate it
    return {"message": "Data migration endpoint created. Implement migration logic."}
