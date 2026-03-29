"""
DuckPools - Bot Routes (Internal API)

Endpoints for the off-chain bot to interact with the backend.
These routes are NOT exposed to the frontend — they are internal-only.

Routes:
  GET  /api/bot/pending-bets       — List unspent commit boxes at the contract
  POST /api/bot/build-reveal-tx    — Build unsigned EIP-12 reveal transaction
  POST /api/bot/reveal-and-broadcast — Build, sign, and broadcast reveal tx

MAT-355: Implement reveal flow
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from reveal_service import (
    build_reveal_tx,
    get_pending_bets,
    sign_and_broadcast_tx,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot", tags=["bot"])


# ─── Request/Response Models ────────────────────────────────────────


class BuildRevealRequest(BaseModel):
    """Request to build a reveal transaction."""

    box_id: str = Field(..., description="Commit box ID to reveal")
    house_change_address: Optional[str] = Field(
        None, description="House change address (defaults to HOUSE_ADDRESS env)"
    )


class PendingBetResponse(BaseModel):
    """A pending bet box at the contract."""

    box_id: str
    value: str  # nanoERG as string
    creation_height: int
    player_choice: int  # 0=heads, 1=tails
    timeout_height: int
    player_address: str = ""


class BuildRevealResponse(BaseModel):
    """Response with the unsigned reveal transaction."""

    success: bool = True
    unsigned_tx: Dict[str, Any]
    player_wins: bool
    payout_amount: str  # nanoERG
    block_hash: str
    player_address: str = ""
    bet_amount: str
    player_choice: int
    rng_hash: str
    message: str = ""


class RevealAndBroadcastRequest(BaseModel):
    """Request to build, sign, and broadcast a reveal transaction."""

    box_id: str = Field(..., description="Commit box ID to reveal")
    house_change_address: Optional[str] = Field(
        None, description="House change address (defaults to HOUSE_ADDRESS env)"
    )


class RevealAndBroadcastResponse(BaseModel):
    """Response after broadcasting a reveal transaction."""

    success: bool = True
    tx_id: str = ""
    player_wins: bool = False
    payout_amount: str = ""
    message: str = ""


# ─── Routes ─────────────────────────────────────────────────────────


@router.get("/pending-bets", response_model=List[PendingBetResponse])
async def list_pending_bets():
    """
    List all unspent commit boxes at the coinflip contract.

    The off-chain bot polls this endpoint to find bets that need revealing.
    Boxes that have passed their timeout height are excluded (player should refund).
    """
    try:
        boxes = await get_pending_bets()
    except Exception as e:
        logger.error("fetch_pending_bets_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch pending bets from node: {e}")

    result = []
    for box in boxes:
        try:
            # Derive player address from public key
            from reveal_service import _pubkey_to_address
            player_addr = _pubkey_to_address(box.player_pub_key)
        except Exception:
            player_addr = ""

        result.append(
            PendingBetResponse(
                box_id=box.box_id,
                value=str(box.value),
                creation_height=box.creation_height,
                player_choice=box.player_choice,
                timeout_height=box.timeout_height,
                player_address=player_addr,
            )
        )

    return result


@router.post("/build-reveal-tx", response_model=BuildRevealResponse)
async def build_reveal(req: BuildRevealRequest):
    """
    Build an unsigned EIP-12 reveal transaction for a commit box.

    The off-chain bot calls this endpoint to construct the transaction,
    then signs it with the house wallet and broadcasts.

    Steps performed:
    1. Fetch commit box from node
    2. Decode registers (R4-R9)
    3. Fetch previous block header for RNG seed
    4. Compute blake2b256(prevBlockHash ++ playerSecret)[0] % 2
    5. Build unsigned EIP-12 transaction JSON

    The returned unsigned_tx can be signed via:
      POST /wallet/transaction/sign  {"unsignedTx": <unsigned_tx>}
    """
    try:
        result = await build_reveal_tx(
            box_id=req.box_id,
            house_change_address=req.house_change_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("build_reveal_tx_failed", box_id=req.box_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to build reveal tx: {e}")

    choice_str = "heads" if result.player_choice == 0 else "tails"
    outcome_str = "player wins" if result.player_wins else "house wins"

    return BuildRevealResponse(
        success=True,
        unsigned_tx=result.unsigned_tx,
        player_wins=result.player_wins,
        payout_amount=str(result.payout_amount),
        block_hash=result.block_hash,
        player_address=result.player_address,
        bet_amount=str(result.bet_amount),
        player_choice=result.player_choice,
        rng_hash=result.rng_hash,
        message=f"Reveal tx built: {choice_str} bet, {outcome_str}, payout {result.payout_amount / 1e9:.6f} ERG",
    )


@router.post("/reveal-and-broadcast", response_model=RevealAndBroadcastResponse)
async def reveal_and_broadcast(req: RevealAndBroadcastRequest):
    """
    Build, sign with house wallet, and broadcast a reveal transaction.

    This is the full end-to-end reveal flow in a single call.
    The node wallet must be unlocked for signing.

    Steps:
    1. Build unsigned reveal transaction
    2. Sign with node wallet (POST /wallet/transaction/sign)
    3. Broadcast signed transaction (POST /transactions)
    """
    try:
        result = await build_reveal_tx(
            box_id=req.box_id,
            house_change_address=req.house_change_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("build_reveal_tx_failed", box_id=req.box_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to build reveal tx: {e}")

    try:
        broadcast_result = await sign_and_broadcast_tx(result.unsigned_tx)
    except Exception as e:
        logger.error("sign_broadcast_failed", box_id=req.box_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to sign/broadcast tx: {e}")

    tx_id = broadcast_result.get("txId", "")
    if not tx_id:
        raise HTTPException(status_code=502, detail="Transaction broadcast returned no txId")

    choice_str = "heads" if result.player_choice == 0 else "tails"
    outcome_str = "player wins" if result.player_wins else "house wins"

    return RevealAndBroadcastResponse(
        success=True,
        tx_id=tx_id,
        player_wins=result.player_wins,
        payout_amount=str(result.payout_amount),
        message=f"Reveal broadcast: txId={tx_id}, {choice_str} bet, {outcome_str}, payout {result.payout_amount / 1e9:.6f} ERG",
    )
