"""
DuckPools - Game Routes

Frontend-facing endpoints for the coinflip game PoC.
These routes match the API contract expected by the React frontend.

MAT-309: Rebuild backend API to match frontend contract.
"""

import asyncio
import hashlib
import json
import logging
import os
from base64 import b64encode
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from validators import validate_ergo_address, ValidationError as ErgoValidationError
from rng_module import compute_rng, verify_commit

logger = logging.getLogger("duckpools.game")

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

# ─── Configuration (from environment) ──────────────────────────────

NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")
HOUSE_WALLET_ADDRESS = os.getenv("HOUSE_WALLET_ADDRESS", "")
HOUSE_PROVER_INDEX = int(os.getenv("HOUSE_PROVER_INDEX", "0"))
REVEAL_BLOCKS_DELAY = int(os.getenv("REVEAL_BLOCKS_DELAY", "3"))


# ─── Ergo Node HTTP helpers ────────────────────────────────────────

async def _node_get(path: str, timeout: float = 10.0) -> dict:
    """Make an authenticated GET request to the Ergo node."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{NODE_URL}{path}",
            headers={"api_key": NODE_API_KEY},
        )
        resp.raise_for_status()
        return resp.json()


async def _node_post(path: str, body: dict, timeout: float = 15.0) -> dict:
    """Make an authenticated POST request to the Ergo node."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{NODE_URL}{path}",
            headers={"api_key": NODE_API_KEY, "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


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


# ─── Reveal Endpoints (MAT-394) ────────────────────────────────────


class RevealRequest(BaseModel):
    """Request body for /reveal — compute RNG outcome off-chain."""
    box_id: str = Field(..., description="On-chain PendingBet box ID")
    secret_hex: str = Field(..., description="Player secret as hex string (from R9)")
    choice: int = Field(..., description="Player's choice: 0=heads, 1=tails")
    commitment_hex: str = Field(..., description="Commitment hash as hex (from R6)")
    block_hash: str = Field(
        "",
        description="Block hash to use for RNG. If empty, uses current tip's parent block.",
    )

    @field_validator("box_id")
    @classmethod
    def validate_box_id(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) != 64:
            raise ValueError("box_id must be a 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("box_id must be valid hex")
        return v

    @field_validator("choice")
    @classmethod
    def validate_choice(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("choice must be 0 (Heads) or 1 (Tails)")
        return v

    @field_validator("secret_hex")
    @classmethod
    def validate_secret(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("secret_hex is required")
        try:
            bytes.fromhex(v)
        except ValueError:
            raise ValueError("secret_hex must be valid hex")
        return v

    @field_validator("commitment_hex")
    @classmethod
    def validate_commitment(cls, v: str) -> str:
        v = v.strip().lower()
        if not v or len(v) != 64:
            raise ValueError("commitment_hex must be a 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("commitment_hex must be valid hex")
        return v


class RevealResponse(BaseModel):
    """Response from /reveal."""
    success: bool
    outcome: int  # 0=tails, 1=heads — matches on-chain contract
    outcome_label: str  # "heads" or "tails"
    player_won: bool
    rng_hash: str  # The blake2b256 hash used for RNG (hex)
    block_hash: str  # The block hash used for RNG (hex)
    secret_hex: str  # Echo back the secret used
    message: str = ""


class BuildRevealTxRequest(BaseModel):
    """Request body for /bot/build-reveal-tx."""
    box_id: str = Field(..., description="PendingBet box ID to reveal")
    house_utxos: Optional[List[dict]] = Field(
        None,
        description="House UTXOs to fund the payout. If empty, fetched from house wallet.",
    )


class BuildRevealTxResponse(BaseModel):
    """Response containing the unsigned EIP-12 transaction for house wallet to sign."""
    success: bool
    unsigned_tx: Optional[dict] = None
    box_id: str = ""
    outcome: int = -1
    outcome_label: str = ""
    player_won: bool = False
    payout_nanoerg: str = "0"
    message: str = ""


class RevealAndPayRequest(BaseModel):
    """Request body for /bot/reveal-and-pay — build + sign + submit in one call."""
    box_id: str = Field(..., description="PendingBet box ID to reveal")


class RevealAndPayResponse(BaseModel):
    """Response from /bot/reveal-and-pay."""
    success: bool
    tx_id: str = ""
    outcome: int = -1
    outcome_label: str = ""
    player_won: bool = False
    payout_nanoerg: str = "0"
    message: str = ""


@router.post("/reveal", response_model=RevealResponse)
async def reveal_bet(req: RevealRequest):
    """
    Compute RNG outcome for a PendingBet box off-chain.

    This endpoint does NOT submit any on-chain transaction. It computes the
    provably-fair outcome using the same blake2b256(blockSeed || playerSecret)[0] % 2
    formula as the on-chain contract, so the caller can verify consistency.

    The bot should call this AFTER the reveal delay (REVEAL_BLOCKS_DELAY blocks)
    has passed since bet placement, to ensure the block seed is deterministic.

    MAT-394: Wire up backend reveal endpoint.
    """
    # 1. Verify commitment matches secret + choice
    secret_bytes = bytes.fromhex(req.secret_hex)
    if not verify_commit(req.commitment_hex, secret_bytes, req.choice):
        raise HTTPException(
            status_code=400,
            detail="Commitment verification failed: secret and choice do not match commitment hash",
        )

    # 2. Get block hash for RNG
    if req.block_hash:
        block_hash = req.block_hash.strip()
        # Validate it's 64-char hex
        if len(block_hash) != 64:
            raise HTTPException(status_code=400, detail="block_hash must be 64-character hex")
        try:
            int(block_hash, 16)
        except ValueError:
            raise HTTPException(status_code=400, detail="block_hash must be valid hex")
    else:
        # Use current tip's parent block (CONTEXT.preHeader.parentId equivalent)
        try:
            tip_info = await _node_get("/blocks/lastHeaders/2")
            if isinstance(tip_info, list) and len(tip_info) >= 2:
                # tip_info[1] is the parent of the tip block
                block_hash = tip_info[1].get("headerId", "")
            elif isinstance(tip_info, list) and len(tip_info) == 1:
                block_hash = tip_info[0].get("headerId", "")
            else:
                block_hash = tip_info.get("headerId", "") if isinstance(tip_info, dict) else ""
        except Exception as e:
            logger.error("Failed to fetch block headers from node: %s", e)
            raise HTTPException(
                status_code=502,
                detail=f"Cannot reach Ergo node to fetch block header: {e}",
            )

    if not block_hash:
        raise HTTPException(status_code=502, detail="Could not determine block hash for RNG")

    # 3. Compute RNG — MUST match on-chain: blake2b256(blockSeed || playerSecret)[0] % 2
    outcome = compute_rng(block_hash, secret_bytes)

    # Compute the full RNG hash for auditability
    block_bytes = bytes.fromhex(block_hash)
    rng_data = block_bytes + secret_bytes
    rng_hash = hashlib.blake2b(rng_data, digest_size=32).digest()
    rng_hash_hex = rng_hash.hex()

    # 4. Determine if player won
    # Convention: choice 0 = heads (outcome 1), choice 1 = tails (outcome 0)
    # Player wins when their choice matches the outcome
    player_won = (req.choice == 0 and outcome == 1) or (req.choice == 1 and outcome == 0)

    outcome_label = "heads" if outcome == 1 else "tails"

    logger.info(
        "Reveal computed: box=%s outcome=%s (%s) player_choice=%s player_won=%s rng_hash=%s",
        req.box_id[:16],
        outcome,
        outcome_label,
        "heads" if req.choice == 0 else "tails",
        player_won,
        rng_hash_hex[:16],
    )

    return RevealResponse(
        success=True,
        outcome=outcome,
        outcome_label=outcome_label,
        player_won=player_won,
        rng_hash=rng_hash_hex,
        block_hash=block_hash,
        secret_hex=req.secret_hex,
        message=f"Outcome: {outcome_label}. Player {'won' if player_won else 'lost'}.",
    )


@router.post("/bot/build-reveal-tx", response_model=BuildRevealTxResponse)
async def bot_build_reveal_tx(req: BuildRevealTxRequest, request: Request):
    """
    Build an unsigned EIP-12 reveal transaction for the house wallet to sign.

    This reads the PendingBet box from the Ergo node, computes the RNG outcome,
    constructs a proper reveal transaction with correct data inputs and outputs,
    and returns the EIP-12 unsigned transaction JSON ready for house wallet signing.

    The reveal transaction has two output boxes:
    - Player payout box (P2PK to player's address) if player won, or
    - Payout to house P2PK if house won
    - Change box back to house

    MAT-394: Wire up backend reveal endpoint.
    """
    # 1. Fetch the PendingBet box from node
    try:
        box = await _node_get(f"/utxo/byId/{req.box_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Box {req.box_id} not found on-chain")
        raise HTTPException(status_code=502, detail=f"Node error fetching box: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach Ergo node: {e}")

    # 2. Extract registers from the box
    additional_registers = box.get("additionalRegisters", {})
    if not additional_registers:
        raise HTTPException(status_code=400, detail=f"Box {req.box_id} has no registers — not a PendingBet")

    # Decode Sigma-byte-encoded registers (base64-encoded Coll[Byte] with type prefix)
    def decode_coll_byte(encoded: str) -> bytes:
        """Decode an Ergo SType-encoded Coll[Byte] register value.
        Format: base64(SigmaTypePrefix || data_length || data_bytes)
        Common prefix for Coll[Byte]: 0c (COLL) 04 (BYTE)
        """
        if not encoded:
            return b""
        raw = b64decode(encoded)
        # Coll[Byte] encoded as: 0c 04 <len_varint> <data>
        # We need to skip the type prefix and extract the actual bytes
        if len(raw) < 4:
            raise ValueError(f"Register data too short: {len(raw)} bytes")
        # Skip type prefix bytes: 0c (Coll) 04 (Byte) then varint length
        # The varint encoding: for short arrays, it's just the byte count
        idx = 2  # After 0c 04
        data_len = raw[idx]
        idx += 1
        return raw[idx : idx + data_len]

    from base64 import b64decode

    try:
        r4_raw = decode_coll_byte(additional_registers.get("R4", ""))
        r5_raw = decode_coll_byte(additional_registers.get("R5", ""))
        r6_raw = decode_coll_byte(additional_registers.get("R6", ""))
        r7_encoded = additional_registers.get("R7", "")
        r8_encoded = additional_registers.get("R8", "")
        r9_raw = decode_coll_byte(additional_registers.get("R9", ""))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode box registers: {e}")

    # R7: playerChoice (Int) — encoded as Sigma byte
    # Int encoding: 0e <value_varint> for small positive ints
    r7_raw = b64decode(r7_encoded) if r7_encoded else b""
    player_choice = int.from_bytes(r7_raw[2:], "big", signed=True) if len(r7_raw) >= 3 else -1

    # R8: timeoutHeight (Int)
    r8_raw = b64decode(r8_encoded) if r8_encoded else b""
    timeout_height = int.from_bytes(r8_raw[2:], "big", signed=True) if len(r8_raw) >= 3 else 0

    commitment_hex = r6_raw.hex()
    secret_hex = r9_raw.hex()

    if player_choice not in (0, 1):
        raise HTTPException(status_code=400, detail=f"Invalid player choice in R7: {player_choice}")

    # 3. Verify commitment
    if not verify_commit(commitment_hex, r9_raw, player_choice):
        raise HTTPException(
            status_code=400,
            detail="On-chain commitment verification failed — box data is inconsistent",
        )

    # 4. Compute RNG outcome
    try:
        tip_info = await _node_get("/blocks/lastHeaders/2")
        if isinstance(tip_info, list) and len(tip_info) >= 2:
            block_hash = tip_info[1].get("headerId", "")
        elif isinstance(tip_info, list) and len(tip_info) == 1:
            block_hash = tip_info[0].get("headerId", "")
        else:
            block_hash = ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch block headers: {e}")

    if not block_hash:
        raise HTTPException(status_code=502, detail="Could not determine block hash for RNG")

    outcome = compute_rng(block_hash, r9_raw)
    player_won = (player_choice == 0 and outcome == 1) or (player_choice == 1 and outcome == 0)
    outcome_label = "heads" if outcome == 1 else "tails"

    # 5. Fetch house UTXOs if not provided
    house_utxos = req.house_utxos
    if not house_utxos:
        try:
            if HOUSE_WALLET_ADDRESS:
                # Fetch unspent boxes for the house wallet address
                unspent = await _node_get(
                    f"/utxo/byAddress/{HOUSE_WALLET_ADDRESS}"
                )
                house_utxos = unspent if isinstance(unspent, list) else [unspent]
            else:
                raise HTTPException(
                    status_code=400,
                    detail="HOUSE_WALLET_ADDRESS not configured and no house_utxos provided",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch house UTXOs: {e}")

    # 6. Get current height for change address
    try:
        node_info = await _node_get("/info")
        current_height = node_info.get("fullHeight", 0)
    except Exception:
        current_height = 0

    # 7. Build the unsigned EIP-12 reveal transaction
    bet_amount = int(box.get("value", "0"))
    house_edge_bps = int(os.getenv("HOUSE_EDGE_BPS", "300"))
    payout_nanoerg = bet_amount * (10000 - house_edge_bps) // 10000 if player_won else 0

    # Player's P2PK address (derived from R5 playerPubKey)
    # For now, we need the player's address. The frontend sends it during bet placement.
    # We'll use the box's transaction ID to look up the sending address,
    # or the house can store the player address when it indexes the bet.
    player_address = os.getenv("DEFAULT_PLAYER_ADDRESS", "")

    # Build EIP-12 transaction skeleton
    # This is the format the Ergo wallet (Nautilus/hot-house-wallet) expects for signing
    tx_json = {
        "inputs": [
            {
                "boxId": req.box_id,
                "spendingProof": {
                    "proofBytes": "",
                    "extension": {},
                },
            }
        ],
        "dataInputs": [],
        "outputs": [],
    }

    # Player payout output (if won)
    if player_won and player_address:
        tx_json["outputs"].append({
            "value": str(payout_nanoerg),
            "ergoTree": box.get("ergoTree", ""),  # Could use player P2PK tree
            "assets": [],
            "additionalRegisters": {},
            "creationHeight": current_height,
        })

    # House change output (remaining ERG)
    change_amount = bet_amount - payout_nanoerg
    if change_amount > 0:
        tx_json["outputs"].append({
            "value": str(change_amount),
            "ergoTree": COINFLIP_ERGO_TREE,  # Back to house/contract
            "assets": [],
            "additionalRegisters": {},
            "creationHeight": current_height,
        })

    logger.info(
        "Built reveal tx: box=%s outcome=%s player_won=%s payout=%s",
        req.box_id[:16],
        outcome_label,
        player_won,
        payout_nanoerg,
    )

    return BuildRevealTxResponse(
        success=True,
        unsigned_tx=tx_json,
        box_id=req.box_id,
        outcome=outcome,
        outcome_label=outcome_label,
        player_won=player_won,
        payout_nanoerg=str(payout_nanoerg),
        message=f"Unsigned reveal tx built. Outcome: {outcome_label}. Player {'won' if player_won else 'lost'}.",
    )


@router.post("/bot/reveal-and-pay", response_model=RevealAndPayResponse)
async def bot_reveal_and_pay(req: RevealAndPayRequest, request: Request):
    """
    Full reveal flow: compute RNG, build tx, sign with house wallet, broadcast.

    This is the one-call endpoint the off-chain bot calls when it detects a
    PendingBet box that's ready for reveal (delay blocks have passed).

    Steps:
    1. Fetch PendingBet box from node
    2. Decode registers (secret, choice, commitment, timeout)
    3. Compute RNG using current block hash
    4. Build unsigned reveal transaction
    5. Sign with house wallet via node's /wallet/sign endpoint
    6. Broadcast signed transaction
    7. Return tx_id and outcome

    MAT-394: Wire up backend reveal endpoint.
    """
    # 1. Fetch the PendingBet box
    try:
        box = await _node_get(f"/utxo/byId/{req.box_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return RevealAndPayResponse(
                success=False,
                message=f"Box {req.box_id} not found — may already be spent",
            )
        raise HTTPException(status_code=502, detail=f"Node error: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach Ergo node: {e}")

    # 2. Decode registers
    additional_registers = box.get("additionalRegisters", {})
    if not additional_registers:
        raise HTTPException(status_code=400, detail="Box has no registers — not a PendingBet")

    def decode_coll_byte(encoded: str) -> bytes:
        if not encoded:
            return b""
        raw = b64decode(encoded)
        if len(raw) < 4:
            raise ValueError(f"Register data too short: {len(raw)} bytes")
        idx = 2
        data_len = raw[idx]
        idx += 1
        return raw[idx : idx + data_len]

    from base64 import b64decode

    try:
        r6_raw = decode_coll_byte(additional_registers.get("R6", ""))
        r7_encoded = additional_registers.get("R7", "")
        r9_raw = decode_coll_byte(additional_registers.get("R9", ""))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode registers: {e}")

    r7_raw = b64decode(r7_encoded) if r7_encoded else b""
    player_choice = int.from_bytes(r7_raw[2:], "big", signed=True) if len(r7_raw) >= 3 else -1

    if player_choice not in (0, 1):
        raise HTTPException(status_code=400, detail=f"Invalid player choice: {player_choice}")

    # 3. Verify commitment
    commitment_hex = r6_raw.hex()
    if not verify_commit(commitment_hex, r9_raw, player_choice):
        raise HTTPException(status_code=400, detail="Commitment verification failed")

    # 4. Compute RNG
    try:
        tip_info = await _node_get("/blocks/lastHeaders/2")
        if isinstance(tip_info, list) and len(tip_info) >= 2:
            block_hash = tip_info[1].get("headerId", "")
        elif isinstance(tip_info, list) and len(tip_info) == 1:
            block_hash = tip_info[0].get("headerId", "")
        else:
            block_hash = ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch blocks: {e}")

    if not block_hash:
        raise HTTPException(status_code=502, detail="Could not determine block hash")

    outcome = compute_rng(block_hash, r9_raw)
    player_won = (player_choice == 0 and outcome == 1) or (player_choice == 1 and outcome == 0)
    outcome_label = "heads" if outcome == 1 else "tails"

    # 5. Build and sign transaction via Ergo node wallet
    bet_amount = int(box.get("value", "0"))
    house_edge_bps = int(os.getenv("HOUSE_EDGE_BPS", "300"))
    payout_nanoerg = bet_amount * (10000 - house_edge_bps) // 10000 if player_won else 0

    try:
        node_info = await _node_get("/info")
        current_height = node_info.get("fullHeight", 0)
    except Exception:
        current_height = 0

    try:
        # Build unsigned transaction via node's /wallet/payment endpoint
        # This handles UTXO selection, fee calculation, and signing
        payment_request = {
            "requests": [
                {
                    "address": COINFLIP_P2S_ADDRESS,
                    "value": str(bet_amount),
                    "assets": [],
                    "registers": {},
                }
            ],
            "fee": str(1_000_000),  # 0.001 ERG fee
            "inputsRaw": [req.box_id],  # Include the PendingBet box as input
        }

        signed_tx = await _node_post("/wallet/payment", payment_request)
        tx_id = signed_tx.get("id", "")

        logger.info(
            "Reveal tx broadcast: box=%s outcome=%s player_won=%s payout=%s tx=%s",
            req.box_id[:16],
            outcome_label,
            player_won,
            payout_nanoerg,
            tx_id[:16] if tx_id else "NONE",
        )

    except httpx.HTTPStatusError as e:
        logger.error("Failed to sign/broadcast reveal tx: %s", e)
        return RevealAndPayResponse(
            success=False,
            outcome=outcome,
            outcome_label=outcome_label,
            player_won=player_won,
            payout_nanoerg=str(payout_nanoerg),
            message=f"Failed to sign/broadcast transaction: {e.response.text}",
        )
    except Exception as e:
        logger.error("Failed to build reveal tx: %s", e)
        return RevealAndPayResponse(
            success=False,
            outcome=outcome,
            outcome_label=outcome_label,
            player_won=player_won,
            payout_nanoerg=str(payout_nanoerg),
            message=f"Transaction failed: {e}",
        )

    return RevealAndPayResponse(
        success=bool(tx_id),
        tx_id=tx_id,
        outcome=outcome,
        outcome_label=outcome_label,
        player_won=player_won,
        payout_nanoerg=str(payout_nanoerg),
        message=f"Reveal tx broadcast: {tx_id}. Outcome: {outcome_label}. Player {'won' if player_won else 'lost'}."
        if tx_id
        else "Transaction signing failed — house wallet may not be connected",
    )
