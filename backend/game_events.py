"""
DuckPools - Game Event Types and Broadcast Helpers

Defines event models for the bet lifecycle and provides convenience functions
to broadcast events through the WebSocket manager.

Event types mirror the bet state machine:
  bet_placed -> bet_revealed -> bet_settled
                      \-> bet_refunded (timeout)

MAT-30: Real-time game history with WebSocket updates
"""

import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("duckpools.events")


# ─── Event Types ───────────────────────────────────────────────────

class BetEventType(str, Enum):
    """Bet lifecycle event types."""
    BET_PLACED = "bet_placed"
    BET_REVEALED = "bet_revealed"
    BET_SETTLED = "bet_settled"
    BET_REFUNDED = "bet_refunded"
    BET_TIMEOUT_WARNING = "bet_timeout_warning"
    POOL_STATE_UPDATE = "pool_state_update"


class BetEvent(BaseModel):
    """
    A bet lifecycle event pushed over WebSocket.

    Every event includes:
    - type: the event kind
    - timestamp: epoch seconds
    - bet_id: unique bet identifier (sha256 hash)
    - player_address: the player's Ergo address
    - payload: event-specific data
    """
    type: BetEventType
    timestamp: float = Field(default_factory=time.time)
    bet_id: Optional[str] = None
    player_address: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class BetPlacedPayload(BaseModel):
    """Payload for bet_placed events."""
    bet_id: str
    player_address: str
    amount_nanoerg: int
    amount_erg: str
    choice: Optional[str] = None  # "heads" or "tails" for coinflip, None for plinko
    game_type: str = "coinflip"  # "coinflip", "plinko", "dice"
    commitment_hash: Optional[str] = None
    plinko_rows: Optional[int] = None  # Number of peg rows for plinko


class BetRevealedPayload(BaseModel):
    """Payload for bet_revealed events."""
    bet_id: str
    player_address: str
    block_hash: Optional[str] = None
    server_secret: Optional[str] = None
    rng_result: Optional[str] = None  # "heads" or "tails" for coinflip, zone number for plinko
    plinko_zone: Optional[int] = None  # Landing zone for plinko (0-12)
    plinko_path: Optional[List[str]] = None  # Path of left/right for plinko animation


class BetSettledPayload(BaseModel):
    """Payload for bet_settled events."""
    bet_id: str
    player_address: str
    outcome: str  # "win" or "lose"
    payout_nanoerg: int
    payout_erg: str
    player_choice: Optional[str] = None  # For coinflip/dice
    rng_result: str
    game_type: str = "coinflip"  # "coinflip", "plinko", "dice"
    house_edge_bps: int = 300
    plinko_zone: Optional[int] = None  # Landing zone for plinko
    plinko_multiplier: Optional[float] = None  # Multiplier used for plinko


class BetRefundedPayload(BaseModel):
    """Payload for bet_refunded events."""
    bet_id: str
    player_address: str
    refund_nanoerg: int
    refund_erg: str
    reason: str = "timeout"


class PoolStatePayload(BaseModel):
    """Payload for pool_state_update events (broadcast to all)."""
    bankroll_nanoerg: int
    bankroll_erg: str
    total_bets: int
    tvl_erg: str


# ─── Broadcast Helpers ────────────────────────────────────────────

def make_bet_placed_event(
    bet_id: str,
    player_address: str,
    amount_nanoerg: int,
    choice: str,
    commitment_hash: Optional[str] = None,
) -> dict:
    """Build a bet_placed event dict ready for WebSocket broadcast."""
    return BetEvent(
        type=BetEventType.BET_PLACED,
        bet_id=bet_id,
        player_address=player_address,
        payload=BetPlacedPayload(
            bet_id=bet_id,
            player_address=player_address,
            amount_nanoerg=amount_nanoerg,
            amount_erg=f"{amount_nanoerg / 1e9:.9f}",
            choice=choice,
            commitment_hash=commitment_hash,
        ).model_dump(),
    ).model_dump()


def make_bet_revealed_event(
    bet_id: str,
    player_address: str,
    rng_result: str,
    block_hash: Optional[str] = None,
) -> dict:
    """Build a bet_revealed event dict ready for WebSocket broadcast."""
    return BetEvent(
        type=BetEventType.BET_REVEALED,
        bet_id=bet_id,
        player_address=player_address,
        payload=BetRevealedPayload(
            bet_id=bet_id,
            player_address=player_address,
            block_hash=block_hash,
            rng_result=rng_result,
        ).model_dump(),
    ).model_dump()


def make_bet_settled_event(
    bet_id: str,
    player_address: str,
    outcome: str,
    payout_nanoerg: int,
    player_choice: str,
    rng_result: str,
    house_edge_bps: int = 300,
) -> dict:
    """Build a bet_settled event dict ready for WebSocket broadcast."""
    return BetEvent(
        type=BetEventType.BET_SETTLED,
        bet_id=bet_id,
        player_address=player_address,
        payload=BetSettledPayload(
            bet_id=bet_id,
            player_address=player_address,
            outcome=outcome,
            payout_nanoerg=payout_nanoerg,
            payout_erg=f"{payout_nanoerg / 1e9:.9f}",
            player_choice=player_choice,
            rng_result=rng_result,
            house_edge_bps=house_edge_bps,
        ).model_dump(),
    ).model_dump()


def make_bet_refunded_event(
    bet_id: str,
    player_address: str,
    refund_nanoerg: int,
    reason: str = "timeout",
) -> dict:
    """Build a bet_refunded event dict ready for WebSocket broadcast."""
    return BetEvent(
        type=BetEventType.BET_REFUNDED,
        bet_id=bet_id,
        player_address=player_address,
        payload=BetRefundedPayload(
            bet_id=bet_id,
            player_address=player_address,
            refund_nanoerg=refund_nanoerg,
            refund_erg=f"{refund_nanoerg / 1e9:.9f}",
            reason=reason,
        ).model_dump(),
    ).model_dump()


def make_plinko_bet_placed_event(
    bet_id: str,
    player_address: str,
    amount_nanoerg: int,
    commitment_hash: str,
    rows: int = 12,
) -> dict:
    """Build a bet_placed event for Plinko."""
    return BetEvent(
        type=BetEventType.BET_PLACED,
        bet_id=bet_id,
        player_address=player_address,
        payload=BetPlacedPayload(
            bet_id=bet_id,
            player_address=player_address,
            amount_nanoerg=amount_nanoerg,
            amount_erg=f"{amount_nanoerg / 1e9:.9f}",
            game_type="plinko",
            commitment_hash=commitment_hash,
            plinko_rows=rows,
        ).model_dump(),
    ).model_dump()


def make_plinko_bet_revealed_event(
    bet_id: str,
    player_address: str,
    block_hash: str,
    zone: int,
    path: List[str],
) -> dict:
    """Build a bet_revealed event for Plinko."""
    return BetEvent(
        type=BetEventType.BET_REVEALED,
        bet_id=bet_id,
        player_address=player_address,
        payload=BetRevealedPayload(
            bet_id=bet_id,
            player_address=player_address,
            block_hash=block_hash,
            rng_result=str(zone),
            plinko_zone=zone,
            plinko_path=path,
        ).model_dump(),
    ).model_dump()


def make_plinko_bet_settled_event(
    bet_id: str,
    player_address: str,
    outcome: str,
    payout_nanoerg: int,
    zone: int,
    multiplier: float,
    house_edge_bps: int = 300,
) -> dict:
    """Build a bet_settled event for Plinko."""
    return BetEvent(
        type=BetEventType.BET_SETTLED,
        bet_id=bet_id,
        player_address=player_address,
        payload=BetSettledPayload(
            bet_id=bet_id,
            player_address=player_address,
            outcome=outcome,
            payout_nanoerg=payout_nanoerg,
            payout_erg=f"{payout_nanoerg / 1e9:.9f}",
            player_choice=None,
            rng_result=str(zone),
            game_type="plinko",
            house_edge_bps=house_edge_bps,
            plinko_zone=zone,
            plinko_multiplier=multiplier,
        ).model_dump(),
    ).model_dump()


def make_pool_update_event(
    bankroll_nanoerg: int,
    total_bets: int,
    tvl_nanoerg: int,
) -> dict:
    """Build a pool_state_update event dict (broadcasts to ALL clients)."""
    return BetEvent(
        type=BetEventType.POOL_STATE_UPDATE,
        payload=PoolStatePayload(
            bankroll_nanoerg=bankroll_nanoerg,
            bankroll_erg=f"{bankroll_nanoerg / 1e9:.9f}",
            total_bets=total_bets,
            tvl_erg=f"{tvl_nanoerg / 1e9:.9f}",
        ).model_dump(),
    ).model_dump()


# ─── Broadcast Convenience ────────────────────────────────────────

async def broadcast_bet_event(
    ws_manager,
    event: dict,
    player_address: Optional[str] = None,
    global_broadcast: bool = False,
) -> int:
    """
    Broadcast a bet event through the WebSocket manager.

    Args:
        ws_manager: The ConnectionManager instance.
        event: The event dict to send.
        player_address: If set, send only to subscribers of this address.
        global_broadcast: If True, send to ALL connected clients.

    Returns:
        Number of clients that received the event.
    """
    if global_broadcast:
        return await ws_manager.broadcast_global(event)
    elif player_address:
        return await ws_manager.broadcast_to_address(player_address, event)
    else:
        logger.warning("broadcast_bet_event called without address or global flag")
        return 0
