"""
Dice Game Routes - Placeholder for testing

This is a placeholder implementation for dice game routes.
Used only for security testing purposes.
"""

from fastapi import APIRouter, Query
from typing import Optional, Dict, Any

router = APIRouter(tags=["dice"])


@router.get("/api/dice/health")
async def dice_health():
    """Health check endpoint for dice game."""
    return {"status": "ok", "game": "dice"}


@router.post("/api/dice/bet")
async def create_bet(
    amount: int = Query(..., description="Bet amount in nanoergs"),
    player_address: str = Query(..., description="Player's Ergo address"),
    outcome: Optional[str] = Query(None, description="Expected outcome")
):
    """Create a new dice bet (placeholder)."""
    return {
        "bet_id": "placeholder_bet_id",
        "status": "created",
        "amount": amount,
        "player_address": player_address,
        "outcome": outcome
    }


@router.get("/api/dice/state")
async def dice_state():
    """Get current dice game state (placeholder)."""
    return {
        "game_active": True,
        "min_bet": 1000000,
        "max_bet": 1000000000,
        "house_edge_bps": 300
    }