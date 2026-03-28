"""
DuckPools - Bankroll Auto-Reload API Routes

FastAPI endpoints for auto-reload configuration and monitoring:
- GET  /bankroll/autoreload/config  - Current config
- POST /bankroll/autoreload/config  - Update config
- GET  /bankroll/autoreload/history - Reload event history

MAT-233: Auto-reload mechanism when bankroll drops below threshold
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("duckpools.autoreload_routes")

router = APIRouter(prefix="/bankroll/autoreload", tags=["bankroll-autoreload"])


# ─── Response Models ─────────────────────────────────────────────

class AutoReloadConfigResponse(BaseModel):
    enabled: bool = Field(..., description="Whether auto-reload is active")
    min_erg: float = Field(..., description="Minimum bankroll ERG before reload triggers")
    target_erg: float = Field(..., description="Target bankroll ERG after reload")
    check_interval_sec: int = Field(..., description="Seconds between bankroll checks")
    max_erg_per_reload: float = Field(..., description="Maximum ERG per single reload")
    cooldown_sec: int = Field(..., description="Minimum seconds between reloads")
    reserve_wallet_configured: bool = Field(..., description="Whether a reserve wallet is set")


class AutoReloadConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    min_erg: Optional[float] = Field(None, ge=0, description="Minimum bankroll ERG before reload")
    target_erg: Optional[float] = Field(None, ge=0, description="Target bankroll ERG after reload")
    check_interval_sec: Optional[int] = Field(None, ge=10, le=3600, description="Check interval (seconds)")
    max_erg_per_reload: Optional[float] = Field(None, ge=0, description="Max ERG per reload")
    cooldown_sec: Optional[int] = Field(None, ge=60, le=86400, description="Cooldown between reloads (seconds)")
    reserve_wallet_address: Optional[str] = Field(None, description="Reserve wallet Ergo address")


class ReloadEventResponse(BaseModel):
    timestamp: str
    triggered_by_balance_erg: float
    target_amount_erg: float
    actual_amount_erg: float
    status: str
    tx_id: Optional[str] = None
    error: Optional[str] = None


class ReloadHistoryResponse(BaseModel):
    events: List[ReloadEventResponse]
    count: int


# ─── Endpoints ───────────────────────────────────────────────────

@router.get("/config", response_model=AutoReloadConfigResponse)
async def get_autoreload_config(request: Request):
    """Get current auto-reload configuration."""
    mgr = _get_manager(request)
    if mgr is None:
        return AutoReloadConfigResponse(
            enabled=False,
            min_erg=10.0,
            target_erg=100.0,
            check_interval_sec=60,
            max_erg_per_reload=100.0,
            cooldown_sec=600,
            reserve_wallet_configured=False,
        )
    return AutoReloadConfigResponse(**mgr.get_config())


@router.post("/config", response_model=AutoReloadConfigResponse)
async def update_autoreload_config(request: Request, update: AutoReloadConfigUpdate):
    """Update auto-reload configuration."""
    mgr = _get_manager(request)
    if mgr is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Auto-reload manager not initialized")

    kwargs = {k: v for k, v in update.dict().items() if v is not None}
    if not kwargs:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No fields to update")

    mgr.update_config(**kwargs)
    logger.info("Auto-reload config updated: %s", kwargs)
    return AutoReloadConfigResponse(**mgr.get_config())


@router.get("/history", response_model=ReloadHistoryResponse)
async def get_autoreload_history(
    request: Request,
    limit: int = 50,
):
    """Get recent auto-reload events."""
    mgr = _get_manager(request)
    if mgr is None:
        return ReloadHistoryResponse(events=[], count=0)
    events = mgr.get_history(limit=limit)
    return ReloadHistoryResponse(events=events, count=len(events))


# ─── Helpers ─────────────────────────────────────────────────────

def _get_manager(request: Request):
    """Get the auto-reload manager from app state."""
    return getattr(request.app.state, "autoreload_manager", None)
