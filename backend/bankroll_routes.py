"""
DuckPools - Bankroll API Routes

FastAPI endpoints for bankroll management:
- GET /bankroll/status       - Real-time bankroll balance, exposure, capacity
- GET /bankroll/history      - Historical balance snapshots
- GET /bankroll/metrics      - Performance metrics (P&L, utilization, sizing)
- GET /bankroll/risk         - Current risk assessment
- GET /bankroll/projection   - Variance projection over N rounds

MAT-184: Design bankroll sizing model and variance analysis
MAT-230: Bankroll monitoring API endpoints
"""

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from bankroll_risk import (
    GameParams,
    RiskMetrics,
    VarianceProjection,
    compute_full_risk_metrics,
    kelly_criterion,
    min_bankroll_for_ror,
    variance_projection,
    DEFAULT_P_HOUSE,
    DEFAULT_PAYOUT_MULTIPLIER,
    DEFAULT_HOUSE_EDGE,
)

logger = logging.getLogger("duckpools.bankroll_routes")

router = APIRouter(prefix="/bankroll", tags=["bankroll"])


# ─── Response Models ───────────────────────────────────────────────

# MAT-230: Bankroll Monitoring Schemas

class BankrollStatusResponse(BaseModel):
    """Real-time bankroll status."""
    balance_nanoerg: int = Field(..., description="Current wallet ERG balance in nanoERG")
    balance_erg: float = Field(..., description="Current wallet ERG balance in ERG")
    exposure_nanoerg: int = Field(default=0, description="Sum of ERG in all pending bet boxes")
    exposure_erg: float = Field(default=0, description="Sum of ERG in all pending bet boxes (ERG)")
    available_capacity_nanoerg: int = Field(default=0, description="balance - exposure")
    available_capacity_erg: float = Field(default=0, description="balance - exposure (ERG)")
    max_single_bet_nanoerg: int = Field(default=0, description="Max allowed single bet (10% of capacity)")
    max_single_bet_erg: float = Field(default=0, description="Max allowed single bet (ERG)")
    pending_bet_count: int = Field(default=0, description="Number of currently pending bets")
    node_height: int = Field(default=0, description="Current blockchain height")


class BankrollSnapshotResponse(BaseModel):
    """Historical bankroll balance snapshot."""
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    balance_nanoerg: int = Field(..., description="Wallet balance at snapshot time")
    balance_erg: float = Field(..., description="Wallet balance at snapshot time (ERG)")
    exposure_nanoerg: int = Field(default=0, description="Pending bet exposure at snapshot time")
    exposure_erg: float = Field(default=0, description="Pending bet exposure (ERG)")
    node_height: int = Field(default=0, description="Blockchain height at snapshot time")


class BankrollHistoryResponse(BaseModel):
    """Paginated historical bankroll balance snapshots."""
    snapshots: List[BankrollSnapshotResponse]
    total: int = Field(default=0, description="Total number of snapshots")
    limit: int = Field(default=50, description="Number of snapshots returned")


class BankrollMetricsResponse(BaseModel):
    """Key bankroll performance metrics."""
    total_pnl_nanoerg: int = Field(default=0, description="Cumulative house P&L in nanoERG")
    total_pnl_erg: float = Field(default=0, description="Cumulative house P&L in ERG")
    total_wagered_nanoerg: int = Field(default=0, description="Total volume wagered")
    total_wagered_erg: float = Field(default=0, description="Total volume wagered (ERG)")
    num_rounds: int = Field(default=0, description="Total number of resolved rounds")
    utilization_ratio: float = Field(default=0.0, description="Current exposure / balance")
    avg_bet_size_nanoerg: int = Field(default=0, description="Average bet size across all rounds")
    avg_bet_size_erg: float = Field(default=0.0, description="Average bet size (ERG)")
    peak_exposure_nanoerg: int = Field(default=0, description="Highest recorded exposure")
    peak_exposure_erg: float = Field(default=0.0, description="Highest recorded exposure (ERG)")
    house_win_rate: float = Field(default=0.0, description="House win rate (0-1)")
    actual_house_edge_bps: float = Field(default=0.0, description="Realized house edge in basis points")


# MAT-184: Risk Models

class RiskMetricsResponse(BaseModel):
    """Full risk assessment response."""
    # Core metrics
    kelly_fraction: float = Field(..., description="Optimal Kelly fraction of bankroll per bet")
    kelly_fraction_quarter: float = Field(..., description="1/4 Kelly (conservative recommendation)")
    risk_of_ruin: float = Field(..., description="Current probability of bankroll depletion")
    safety_ratio: float = Field(..., description="bankroll / min_recommended_bankroll (1% RoR)")
    bankroll_units: float = Field(..., description="Bankroll expressed in max-bet units")

    # Bankroll sizing
    min_bankroll_1pct_nanoerg: float = Field(..., description="Minimum bankroll for <1% RoR")
    min_bankroll_1pct_erg: str = Field(..., description="Minimum bankroll for <1% RoR (ERG)")
    min_bankroll_0_1pct_nanoerg: float = Field(..., description="Minimum bankroll for <0.1% RoR")
    min_bankroll_0_1pct_erg: str = Field(..., description="Minimum bankroll for <0.1% RoR (ERG)")

    # Bet sizing recommendations
    max_bet_kelly_nanoerg: float = Field(..., description="Max single bet at full Kelly")
    max_bet_kelly_erg: str = Field(..., description="Max single bet at full Kelly (ERG)")
    max_bet_quarter_kelly_nanoerg: float = Field(..., description="Max single bet at 1/4 Kelly")
    max_bet_quarter_kelly_erg: str = Field(..., description="Max single bet at 1/4 Kelly (ERG)")

    # Statistical properties
    expected_value_per_bet: float = Field(..., description="House EV per unit bet (3%)")
    variance_per_bet: float = Field(..., description="Variance per unit bet")
    stddev_per_bet: float = Field(..., description="Std dev per unit bet")
    n_bets_for_reliability: float = Field(..., description="Bets until EV > 1 stddev")

    # Current state
    current_bankroll_nanoerg: int = Field(..., description="Current bankroll")
    current_bankroll_erg: str = Field(..., description="Current bankroll (ERG)")
    assumed_max_bet_nanoerg: int = Field(..., description="Max bet used for calculations")


class ProjectionResponse(BaseModel):
    """Variance projection over N rounds."""
    n_rounds: int
    avg_bet_nanoerg: int
    avg_bet_erg: str
    expected_profit_nanoerg: float
    expected_profit_erg: str
    stddev_nanoerg: float
    stddev_erg: str
    profit_1sigma_low_nanoerg: float
    profit_1sigma_high_nanoerg: float
    profit_2sigma_low_nanoerg: float
    profit_2sigma_high_nanoerg: float
    worst_case_3sigma_nanoerg: float
    worst_case_3sigma_erg: str
    prob_profitable: float


# ─── Helpers ───────────────────────────────────────────────────────

def _nano_to_erg_str(nanoerg) -> str:
    """Format nanoERG to human-readable ERG string."""
    if nanoerg == float('inf'):
        return "inf"
    return f"{nanoerg / 1e9:.4f}"


def _get_monitor_service():
    """Get or create the BankrollMonitorService singleton."""
    from services.bankroll_monitor import get_bankroll_monitor_service
    return get_bankroll_monitor_service()


# ─── MAT-230: Monitoring Endpoints ─────────────────────────────────

@router.get("/status", response_model=BankrollStatusResponse)
async def get_bankroll_status():
    """
    Get real-time bankroll status.

    Returns current wallet ERG balance, exposure from pending bets,
    available capacity, and maximum allowed single bet size.

    The house wallet balance comes from the Ergo node /wallet/balances.
    Exposure is computed by summing ERG values in all PendingBet boxes
    found via the coinflip NFT token ID.
    """
    try:
        monitor = _get_monitor_service()
        status = await monitor.get_status()
        return BankrollStatusResponse(**status)
    except Exception as e:
        logger.error("Failed to get bankroll status: %s", e)
        raise HTTPException(status_code=502, detail=f"Node query failed: {str(e)}")


@router.get("/history", response_model=BankrollHistoryResponse)
async def get_bankroll_history(
    limit: int = Query(50, ge=1, le=500, description="Number of snapshots (1-500)"),
    offset: int = Query(0, ge=0, description="Skip N snapshots for pagination"),
):
    """
    Get historical bankroll balance snapshots.

    Snapshots are taken periodically (every ~5 minutes) and on
    significant events. Returns most recent first.
    """
    monitor = _get_monitor_service()
    history = await monitor.get_history(limit=limit, offset=offset)
    return BankrollHistoryResponse(**history)


@router.get("/metrics", response_model=BankrollMetricsResponse)
async def get_bankroll_metrics():
    """
    Get key bankroll performance metrics.

    Combines real-time utilization data with historical P&L statistics.
    Includes cumulative P&L, utilization ratio, average bet size,
    peak exposure, house win rate, and realized house edge.
    """
    try:
        monitor = _get_monitor_service()
        metrics = await monitor.get_metrics()
        return BankrollMetricsResponse(**metrics)
    except Exception as e:
        logger.error("Failed to get bankroll metrics: %s", e)
        raise HTTPException(status_code=502, detail=f"Metrics computation failed: {str(e)}")


# ─── MAT-184: Risk Endpoints ──────────────────────────────────────


def _get_pool_bankroll(request: Request) -> int:
    """
    Try to get current bankroll from pool manager.
    Falls back to 0 if pool manager unavailable.
    """
    try:
        mgr = getattr(request.app.state, "pool_manager", None)
        if mgr is not None:
            state = None
            # Try sync approach
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're inside an async context, but this is a sync helper
                    # Return 0 and let the async endpoint handle it
                    return 0
                state = loop.run_until_complete(mgr.get_pool_state())
            except RuntimeError:
                pass

            if state is not None and hasattr(state, 'bankroll'):
                return int(state.bankroll)
    except Exception as e:
        logger.debug("Could not read pool bankroll: %s", e)

    return 0


# ─── Endpoints ─────────────────────────────────────────────────────

@router.get("/risk", response_model=RiskMetricsResponse)
async def get_risk_metrics(
    request: Request,
    bankroll_nanoerg: Optional[int] = Query(
        None,
        description="Override current bankroll (nanoERG). If omitted, reads from pool state.",
    ),
    max_bet_nanoerg: Optional[int] = Query(
        None,
        description="Max single bet size (nanoERG). Default: 1 ERG.",
    ),
):
    """
    Get comprehensive bankroll risk assessment.

    Returns Kelly criterion values, risk-of-ruin probability,
    minimum bankroll recommendations, and variance statistics.
    """
    # Determine current bankroll
    if bankroll_nanoerg is not None:
        bankroll = bankroll_nanoerg
    else:
        # Try pool manager
        mgr = getattr(request.app.state, "pool_manager", None)
        bankroll = 0
        if mgr is not None:
            try:
                state = await mgr.get_pool_state(force_refresh=False)
                bankroll = int(state.bankroll)
            except Exception as e:
                logger.warning("Failed to get pool state for risk calc: %s", e)

    if bankroll <= 0:
        bankroll = 0

    # Determine max bet
    if max_bet_nanoerg is None:
        max_bet = 1_000_000_000  # Default 1 ERG
    else:
        max_bet = max(1, max_bet_nanoerg)  # Prevent division by zero

    # Compute metrics
    params = GameParams()
    metrics = compute_full_risk_metrics(bankroll, max_bet, params=params)

    return RiskMetricsResponse(
        kelly_fraction=metrics.kelly_fraction,
        kelly_fraction_quarter=metrics.kelly_fraction_quarter,
        risk_of_ruin=metrics.risk_of_ruin,
        safety_ratio=metrics.safety_ratio,
        bankroll_units=metrics.bankroll_units,
        min_bankroll_1pct_nanoerg=metrics.min_bankroll_1pct,
        min_bankroll_1pct_erg=_nano_to_erg_str(metrics.min_bankroll_1pct),
        min_bankroll_0_1pct_nanoerg=metrics.min_bankroll_0_1pct,
        min_bankroll_0_1pct_erg=_nano_to_erg_str(metrics.min_bankroll_0_1pct),
        max_bet_kelly_nanoerg=metrics.max_bet_kelly,
        max_bet_kelly_erg=_nano_to_erg_str(metrics.max_bet_kelly),
        max_bet_quarter_kelly_nanoerg=metrics.max_bet_quarter_kelly,
        max_bet_quarter_kelly_erg=_nano_to_erg_str(metrics.max_bet_quarter_kelly),
        expected_value_per_bet=metrics.expected_value_per_bet,
        variance_per_bet=metrics.variance_per_bet,
        stddev_per_bet=metrics.stddev_per_bet,
        n_bets_for_reliability=metrics.n_bets_for_1sigma,
        current_bankroll_nanoerg=bankroll,
        current_bankroll_erg=_nano_to_erg_str(bankroll),
        assumed_max_bet_nanoerg=max_bet,
    )


@router.get("/projection", response_model=ProjectionResponse)
async def get_variance_projection(
    n_rounds: int = Query(
        1000,
        ge=1,
        le=10_000_000,
        description="Number of bet rounds to project over",
    ),
    avg_bet_nanoerg: Optional[int] = Query(
        None,
        description="Average bet size (nanoERG). Default: 1 ERG.",
    ),
):
    """
    Get variance projection over N bet rounds.

    Shows expected profit, standard deviation ranges,
    worst-case scenarios, and probability of profitability.
    """
    avg_bet = avg_bet_nanoerg if avg_bet_nanoerg else 1_000_000_000

    params = GameParams()
    proj = variance_projection(n_rounds, avg_bet, params)

    return ProjectionResponse(
        n_rounds=proj.n_rounds,
        avg_bet_nanoerg=avg_bet,
        avg_bet_erg=_nano_to_erg_str(avg_bet),
        expected_profit_nanoerg=proj.expected_profit,
        expected_profit_erg=_nano_to_erg_str(proj.expected_profit),
        stddev_nanoerg=proj.stddev,
        stddev_erg=_nano_to_erg_str(proj.stddev),
        profit_1sigma_low_nanoerg=proj.profit_1sigma_range[0],
        profit_1sigma_high_nanoerg=proj.profit_1sigma_range[1],
        profit_2sigma_low_nanoerg=proj.profit_2sigma_range[0],
        profit_2sigma_high_nanoerg=proj.profit_2sigma_range[1],
        worst_case_3sigma_nanoerg=proj.worst_case_3sigma,
        worst_case_3sigma_erg=_nano_to_erg_str(proj.worst_case_3sigma),
        prob_profitable=proj.prob_profitable,
    )


# ─── MAT-192: Dashboard & P&L Endpoints ─────────────────────────


class DashboardAlert(BaseModel):
    severity: str = Field(..., description="Alert severity: critical, warning, info")
    code: str = Field(..., description="Machine-readable alert code")
    message: str = Field(..., description="Human-readable alert description")


class DashboardResponse(BaseModel):
    """Comprehensive bankroll dashboard in one call."""
    balance_nanoerg: int
    balance_erg: float
    exposure_nanoerg: int
    exposure_erg: float
    available_capacity_erg: float
    max_single_bet_erg: float
    pending_bet_count: int
    node_height: int
    total_pnl_erg: float
    total_wagered_erg: float
    total_rounds: int
    utilization_ratio: float
    avg_bet_erg: float
    house_win_rate: float
    actual_house_edge_bps: float
    kelly_fraction: float
    kelly_fraction_quarter: float
    risk_of_ruin: float
    safety_ratio: float
    bankroll_units: float
    min_bankroll_1pct_erg: float
    n_bets_for_reliability: float
    autoreload: dict = Field(default_factory=dict)
    alerts: List[DashboardAlert] = Field(default_factory=list)


class PnLRecordResponse(BaseModel):
    bet_id: str
    player_address: str
    bet_amount_nanoerg: int
    bet_amount_erg: float
    outcome: str
    house_payout_nanoerg: int
    house_profit_nanoerg: int
    house_profit_erg: float
    timestamp: str
    block_height: int


class PnLHistoryResponse(BaseModel):
    records: List[PnLRecordResponse]
    total_profit_nanoerg: int
    total_profit_erg: float
    total_wagered_nanoerg: int
    total_wagered_erg: float
    count: int
    house_edge_actual_bps: float


@router.get("/dashboard", response_model=DashboardResponse)
async def get_bankroll_dashboard(request: Request):
    """
    Get comprehensive bankroll dashboard in one call.

    Combines real-time status, P&L metrics, risk assessment,
    auto-reload configuration, and operational alerts.
    This is the primary endpoint for operators monitoring the protocol.
    """
    try:
        from services.bankroll_manager import BankrollManager
        manager = BankrollManager(request.app)
        data = await manager.get_dashboard()
        return DashboardResponse(**data)
    except Exception as e:
        logger.error("Failed to get dashboard: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Dashboard computation failed: {str(e)}")


@router.get("/pnl", response_model=PnLHistoryResponse)
async def get_bankroll_pnl(
    request: Request,
    from_ts: Optional[str] = Query(None, description="Start timestamp (ISO 8601, inclusive)"),
    to_ts: Optional[str] = Query(None, description="End timestamp (ISO 8601, inclusive)"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
):
    """
    Get P&L history for the house bankroll.

    Optionally filter by time range. Returns per-round records
    with aggregate totals and realized house edge.
    """
    monitor = _get_monitor_service()
    data = monitor.get_pnl_history(from_ts=from_ts, to_ts=to_ts, limit=limit)
    return PnLHistoryResponse(**data)
