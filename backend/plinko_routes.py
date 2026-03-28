"""
DuckPools - Plinko Game Routes

Backend API endpoints for the Plinko game.
Uses the same commit-reveal RNG architecture as coinflip.

MAT-17: Add Plinko and/or crash game
"""

import hashlib
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import httpx
from typing import Any

logger = logging.getLogger("duckpools.plinko")

# ─── Router ─────────────────────────────────────────────────────

router = APIRouter(prefix="/plinko", tags=["plinko"])

# ─── Configuration ─────────────────────────────────────────────

# Will be set from app state in get_pool_manager
_pool_manager = None


def get_pool_manager():
    """Dependency to get pool manager from app state."""
    global _pool_manager
    return _pool_manager


def set_pool_manager(pool_manager):
    """Set pool manager (called during app initialization)."""
    global _pool_manager
    _pool_manager = pool_manager


# ─── Models ───────────────────────────────────────────────────

class PlaceBetRequest(BaseModel):
    """Request to place a Plinko bet."""
    address: str = Field(..., description="Player's Ergo address")
    amount: str = Field(..., description="Bet amount in nanoERG")
    commitment: str = Field(..., description="Commitment hash (SHA256 of secret)")
    secret: str = Field(..., description="Player's secret (2 bytes, hex)")
    betId: str = Field(..., description="Unique bet ID")
    gameType: str = Field(default="plinko", description="Game type (for consistency)")


class PlaceBetResponse(BaseModel):
    """Response after placing a bet."""
    success: bool
    txId: Optional[str] = None
    error: Optional[str] = None


class PlinkoZoneInfo(BaseModel):
    """Information about a Plinko landing zone."""
    zone: int
    multiplier: float
    probability: float
    adjustedMultiplier: float


class MultipliersResponse(BaseModel):
    """Response with all Plinko multipliers."""
    zones: List[PlinkoZoneInfo]
    houseEdge: float


# ─── Constants ─────────────────────────────────────────────────

PLINKO_ROWS = 12
PLINKO_ZONES = PLINKO_ROWS + 1
HOUSE_EDGE = 0.03

# Multipliers for each landing zone (0-indexed)
# Pyramidal distribution
PLINKO_MULTIPLIERS = [
    1000, 130, 26, 9, 4, 2, 1, 2, 4, 9, 26, 130, 1000
]


# ─── Helpers ─────────────────────────────────────────────────

def get_multiplier(zone: int) -> float:
    """Get raw multiplier for a zone."""
    if zone < 0 or zone >= PLINKO_ZONES:
        raise ValueError(f"Invalid zone: {zone}")
    return PLINKO_MULTIPLIERS[zone]


def get_adjusted_multiplier(zone: int, house_edge: float = HOUSE_EDGE) -> float:
    """Get multiplier with house edge applied."""
    return get_multiplier(zone) * (1 - house_edge)


def get_zone_probability(zone: int) -> float:
    """
    Get probability for a zone (0-100%).
    Based on binomial distribution: C(12, zone) * (0.5)^12
    """
    if zone < 0 or zone >= PLINKO_ZONES:
        raise ValueError(f"Invalid zone: {zone}")

    # Binomial coefficient C(12, zone)
    from math import comb
    combinations = comb(PLINKO_ROWS, zone)
    probability = combinations / (2 ** PLINKO_ROWS)
    return probability * 100


def compute_rng_outcome(block_hash: str, secret_hex: str) -> int:
    """
    Compute Plinko RNG outcome from block hash and player secret.

    1. Compute combined hash = SHA256(block_hash_utf8 || secret_bytes)
    2. Extract first 12 bits from hash
    3. Count set bits = landing zone (0-12)
    """
    # Combine block hash and secret
    block_hash_bytes = block_hash.encode('utf-8')
    secret_bytes = bytes.fromhex(secret_hex)

    combined = block_hash_bytes + secret_bytes
    combined_hash = hashlib.sha256(combined).digest()

    # Extract first 12 bits (1.5 bytes)
    byte1 = combined_hash[0]
    byte2 = combined_hash[1]

    # Count set bits in first 12 bits
    bits = 0
    for i in range(8):
        bits += (byte1 >> i) & 1
    for i in range(4):
        bits += (byte2 >> i) & 1

    return bits


def calculate_payout(bet_amount_nanoerg: int, zone: int, house_edge: float = HOUSE_EDGE) -> int:
    """Calculate payout in nanoERG."""
    multiplier = get_adjusted_multiplier(zone, house_edge)
    return int(bet_amount_nanoerg * multiplier)


# ─── Endpoints ─────────────────────────────────────────────────

@router.get("/multipliers", response_model=MultipliersResponse)
async def get_multipliers(house_edge: float = HOUSE_EDGE):
    """
    Get all Plinko multipliers and probabilities.
    Useful for displaying the Plinko board.
    """
    zones = []
    for zone in range(PLINKO_ZONES):
        zones.append(PlinkoZoneInfo(
            zone=zone,
            multiplier=get_multiplier(zone),
            probability=get_zone_probability(zone),
            adjustedMultiplier=get_adjusted_multiplier(zone, house_edge)
        ))

    return MultipliersResponse(
        zones=zones,
        houseEdge=house_edge
    )


@router.post("/place-bet", response_model=PlaceBetResponse)
async def place_bet(
    request: PlaceBetRequest,
    pool_manager=Depends(get_pool_manager)
):
    """
    Place a Plinko bet.

    This endpoint:
    1. Validates the bet amount against pool liquidity
    2. Constructs the Ergo transaction with the commitment
    3. Submits the transaction to the node
    4. Returns the transaction ID
    """
    try:
        # Validate secret length (should be 2 bytes = 4 hex chars)
        if len(request.secret) != 4:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid secret length: {len(request.secret)} chars (expected 4 for 2 bytes)"
            )

        # Validate commitment format (should be 64 hex chars for SHA256)
        if len(request.commitment) != 64:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid commitment length: {len(request.commitment)} chars (expected 64 for SHA256)"
            )

        # Validate bet amount
        try:
            bet_amount = int(request.amount)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bet amount: must be integer")

        if bet_amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid bet amount: must be positive")

        # Check pool liquidity if pool manager is available
        if pool_manager:
            state = await pool_manager.get_pool_state(force_refresh=False)
            min_bet = 1e8  # 0.1 ERG in nanoERG

            if bet_amount < min_bet:
                raise HTTPException(
                    status_code=400,
                    detail=f"Bet amount too small: minimum {min_bet / 1e9} ERG"
                )

            if bet_amount > state.bankroll:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient pool liquidity: {state.bankroll / 1e9:.4f} ERG available"
                )

        # TODO: Construct actual Ergo transaction with commitment
        # For now, return a mock transaction ID
        # In production, this would:
        # 1. Build the transaction with:
        #    - Input from player wallet
        #    - Output to pending bet box with:
        #      - R4: player address as Coll[Byte]
        #      - R5: commitment hash as Coll[Byte]
        #      - R6: bet amount as Long
        #      - R7: player secret as Long
        #      - R8: bet ID as Coll[Byte]
        # 2. Sign with player's wallet (via frontend)
        # 3. Submit to node

        # Mock TX ID for testing
        mock_tx_id = "abcd1234567890abcd1234567890abcd1234567890abcd1234567890abcd1234"

        logger.info(
            f"Plinko bet placed: betId={request.betId}, "
            f"address={request.address}, amount={bet_amount / 1e9} ERG, "
            f"commitment={request.commitment[:16]}..., secret={request.secret}"
        )

        return PlaceBetResponse(
            success=True,
            txId=mock_tx_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error placing Plinko bet")
        return PlaceBetResponse(
            success=False,
            error=str(e)
        )


@router.get("/verify-commitment")
async def verify_commitment(commitment: str, secret: str) -> Dict[str, Any]:
    """
    Verify a commitment against a secret.

    Useful for testing and debugging.
    """
    try:
        # Validate inputs
        if len(secret) != 4:
            raise HTTPException(status_code=400, detail="Invalid secret length")

        if len(commitment) != 64:
            raise HTTPException(status_code=400, detail="Invalid commitment length")

        # Compute commitment from secret
        secret_bytes = bytes.fromhex(secret)
        computed_commitment = hashlib.sha256(secret_bytes).hexdigest()

        is_valid = computed_commitment.lower() == commitment.lower()

        return {
            "valid": is_valid,
            "expected": computed_commitment,
            "provided": commitment,
            "secret": secret
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/compute-outcome")
async def compute_outcome(block_hash: str, secret: str) -> Dict[str, Any]:
    """
    Compute Plinko outcome from block hash and secret.

    Useful for testing and debugging.
    """
    try:
        zone = compute_rng_outcome(block_hash, secret)
        multiplier = get_multiplier(zone)
        adjusted_multiplier = get_adjusted_multiplier(zone)
        probability = get_zone_probability(zone)

        return {
            "zone": zone,
            "multiplier": multiplier,
            "adjustedMultiplier": adjusted_multiplier,
            "probability": probability,
            "blockHash": block_hash,
            "secret": secret
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for Plinko game endpoints."""
    return {
        "status": "ok",
        "game": "plinko",
        "rows": PLINKO_ROWS,
        "zones": PLINKO_ZONES,
        "houseEdge": HOUSE_EDGE
    }
