"""
DuckPools - Bankroll Monitoring API Routes

FastAPI endpoints for bankroll state, transactions, alerts, and risk:
- GET /bankroll/state        - Current bankroll state (TVL, balance, LP pool)
- GET /bankroll/transactions - Paginated transaction history
- GET /bankroll/alerts       - Active risk alerts
- GET /bankroll/risk         - Kelly criterion + risk of ruin from latest projection
- GET /bankroll/projection   - Latest percentile projection (VaR, drawdown bounds)
- GET /bankroll/autoreload   - Auto-reload configuration and recent events

RISK-2.1: Bankroll routes registered in api_server.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_

from app.db import AsyncSessionLocal
from app.models.bankroll import (
    BankrollState,
    BankrollTransaction,
    BankrollAlert,
    AutoReloadEvent,
    RiskProjection,
    TransactionType,
    AlertSeverity,
)

router = APIRouter(prefix="/bankroll", tags=["bankroll"])


# -- Response Schemas ------------------------------------------------

class BankrollStateResponse(BaseModel):
    current_balance: str
    total_tv: str
    house_liquidity: str
    lp_pool_balance: str
    max_payout_capacity: str
    house_edge_percentage: str
    risk_of_ruin: Optional[str] = None
    kelly_fraction: Optional[str] = None
    auto_reload_enabled: bool
    min_balance_threshold: str
    last_reload_at: Optional[str] = None
    updated_at: str


class TransactionItem(BaseModel):
    id: str
    tx_type: str
    amount: str
    balance_before: str
    balance_after: str
    tx_hash: Optional[str] = None
    bet_id: Optional[str] = None
    game_type: Optional[str] = None
    lp_address: Optional[str] = None
    description: Optional[str] = None
    created_at: str


class TransactionListResponse(BaseModel):
    transactions: list[TransactionItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class AlertItem(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    message: str
    balance_at_alert: Optional[str] = None
    threshold_value: Optional[str] = None
    resolved: bool
    created_at: str


class AlertListResponse(BaseModel):
    alerts: list[AlertItem]
    unresolved_count: int


class RiskMetricsResponse(BaseModel):
    current_balance: str
    house_edge: str
    expected_value: str
    variance: str
    standard_deviation: str
    kelly_fraction: str
    kelly_optimal_bet: str
    risk_of_ruin: str
    bankroll_multiple: str
    num_bets_sampled: int
    time_window_hours: int
    calculated_at: str


class ProjectionResponse(BaseModel):
    current_balance: str
    p1_balance: str
    p5_balance: str
    p25_balance: str
    p50_balance: str
    p75_balance: str
    p95_balance: str
    p99_balance: str
    num_bets_sampled: int
    time_window_hours: int
    calculated_at: str


class AutoReloadEventItem(BaseModel):
    id: int
    success: bool
    reload_amount: str
    balance_before: str
    balance_after: str
    trigger_reason: str
    error_message: Optional[str] = None
    created_at: str


class AutoReloadStatusResponse(BaseModel):
    enabled: bool
    min_balance_threshold: str
    reload_amount: str
    reload_cooldown_minutes: int
    last_reload_at: Optional[str] = None
    current_balance: str
    recent_events: list[AutoReloadEventItem]


# -- Helpers ---------------------------------------------------------

def _d(val) -> str:
    """Convert Decimal to string, or '0' if None."""
    return str(val) if val is not None else "0"


def _dt(val: Optional[datetime]) -> Optional[str]:
    return val.isoformat() if val else None


def _dt_req(val: datetime) -> str:
    return val.isoformat()


# -- Endpoints -------------------------------------------------------

@router.get("/state", response_model=BankrollStateResponse)
async def get_bankroll_state():
    """Current bankroll state: TVL, LP pool, house edge, risk metrics."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BankrollState).order_by(BankrollState.id.desc()).limit(1)
        )
        state = result.scalar_one_or_none()

    if not state:
        now = datetime.now(timezone.utc).isoformat()
        return BankrollStateResponse(
            current_balance="0", total_tv="0", house_liquidity="0",
            lp_pool_balance="0", max_payout_capacity="0",
            house_edge_percentage="3.00", auto_reload_enabled=True,
            min_balance_threshold="100", updated_at=now,
        )

    return BankrollStateResponse(
        current_balance=_d(state.current_balance),
        total_tv=_d(state.total_tv),
        house_liquidity=_d(state.house_liquidity),
        lp_pool_balance=_d(state.lp_pool_balance),
        max_payout_capacity=_d(state.max_payout_capacity),
        house_edge_percentage=_d(state.house_edge_percentage),
        risk_of_ruin=_d(state.risk_of_ruin),
        kelly_fraction=_d(state.kelly_fraction),
        auto_reload_enabled=state.auto_reload_enabled,
        min_balance_threshold=_d(state.min_balance_threshold),
        last_reload_at=_dt(state.last_reload_at),
        updated_at=_dt_req(state.updated_at),
    )


@router.get("/transactions", response_model=TransactionListResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tx_type: Optional[str] = Query(None),
    game_type: Optional[str] = Query(None),
):
    """Paginated bankroll transaction history with optional filters."""
    async with AsyncSessionLocal() as session:
        conditions = []
        if tx_type:
            try:
                conditions.append(BankrollTransaction.tx_type == TransactionType(tx_type))
            except ValueError:
                raise HTTPException(400, f"Invalid tx_type: {tx_type}")
        if game_type:
            conditions.append(BankrollTransaction.game_type == game_type)

        # Total count
        count_q = select(func.count(BankrollTransaction.id))
        for c in conditions:
            count_q = count_q.where(c)
        total_count = (await session.execute(count_q)).scalar() or 0

        # Paginated data
        data_q = (
            select(BankrollTransaction)
            .order_by(BankrollTransaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        for c in conditions:
            data_q = data_q.where(c)
        txns = (await session.execute(data_q)).scalars().all()

    total_pages = max(1, (total_count + page_size - 1) // page_size)

    return TransactionListResponse(
        transactions=[
            TransactionItem(
                id=t.id, tx_type=t.tx_type.value, amount=_d(t.amount),
                balance_before=_d(t.balance_before), balance_after=_d(t.balance_after),
                tx_hash=t.tx_hash, bet_id=t.bet_id, game_type=t.game_type,
                lp_address=t.lp_address, description=t.description,
                created_at=_dt_req(t.created_at),
            )
            for t in txns
        ],
        total_count=total_count, page=page,
        page_size=page_size, total_pages=total_pages,
    )


@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    severity: Optional[str] = Query(None),
    unresolved_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    """Bankroll risk alerts (low balance, unusual loss, auto-reload)."""
    async with AsyncSessionLocal() as session:
        conditions = []
        if severity:
            try:
                conditions.append(BankrollAlert.severity == AlertSeverity(severity))
            except ValueError:
                raise HTTPException(400, f"Invalid severity: {severity}")
        if unresolved_only:
            conditions.append(BankrollAlert.resolved == False)  # noqa: E712

        q = select(BankrollAlert).order_by(BankrollAlert.created_at.desc()).limit(limit)
        for c in conditions:
            q = q.where(c)
        alerts = (await session.execute(q)).scalars().all()

        unresolved_count = (
            await session.execute(
                select(func.count(BankrollAlert.id)).where(BankrollAlert.resolved == False)  # noqa: E712
            )
        ).scalar() or 0

    return AlertListResponse(
        alerts=[
            AlertItem(
                id=a.id, alert_type=a.alert_type.value, severity=a.severity.value,
                title=a.title, message=a.message,
                balance_at_alert=_d(a.balance_at_alert),
                threshold_value=_d(a.threshold_value),
                resolved=a.resolved, created_at=_dt_req(a.created_at),
            )
            for a in alerts
        ],
        unresolved_count=unresolved_count,
    )


@router.get("/risk", response_model=RiskMetricsResponse)
async def get_risk_metrics():
    """Latest risk projection: Kelly criterion, risk of ruin, variance."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RiskProjection).order_by(RiskProjection.created_at.desc()).limit(1)
        )
        proj = result.scalar_one_or_none()

    if not proj:
        raise HTTPException(404, "No risk projection calculated yet")

    return RiskMetricsResponse(
        current_balance=_d(proj.current_balance),
        house_edge=_d(proj.house_edge),
        expected_value=_d(proj.expected_value),
        variance=_d(proj.variance),
        standard_deviation=_d(proj.standard_deviation),
        kelly_fraction=_d(proj.kelly_fraction),
        kelly_optimal_bet=_d(proj.kelly_optimal_bet),
        risk_of_ruin=_d(proj.risk_of_ruin),
        bankroll_multiple=_d(proj.bankroll_multiple),
        num_bets_sampled=proj.num_bets_sampled,
        time_window_hours=proj.time_window_hours,
        calculated_at=_dt_req(proj.created_at),
    )


@router.get("/projection", response_model=ProjectionResponse)
async def get_projection():
    """Latest percentile projection: VaR bounds and drawdown estimates."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RiskProjection).order_by(RiskProjection.created_at.desc()).limit(1)
        )
        proj = result.scalar_one_or_none()

    if not proj:
        raise HTTPException(404, "No risk projection calculated yet")

    return ProjectionResponse(
        current_balance=_d(proj.current_balance),
        p1_balance=_d(proj.p1_balance), p5_balance=_d(proj.p5_balance),
        p25_balance=_d(proj.p25_balance), p50_balance=_d(proj.p50_balance),
        p75_balance=_d(proj.p75_balance), p95_balance=_d(proj.p95_balance),
        p99_balance=_d(proj.p99_balance),
        num_bets_sampled=proj.num_bets_sampled,
        time_window_hours=proj.time_window_hours,
        calculated_at=_dt_req(proj.created_at),
    )


@router.get("/autoreload", response_model=AutoReloadStatusResponse)
async def get_autoreload_status():
    """Auto-reload configuration and recent reload events."""
    async with AsyncSessionLocal() as session:
        state = (
            await session.execute(
                select(BankrollState).order_by(BankrollState.id.desc()).limit(1)
            )
        ).scalar_one_or_none()

        events = (
            await session.execute(
                select(AutoReloadEvent).order_by(AutoReloadEvent.created_at.desc()).limit(10)
            )
        ).scalars().all()

    if not state:
        raise HTTPException(404, "Bankroll state not initialized")

    return AutoReloadStatusResponse(
        enabled=state.auto_reload_enabled,
        min_balance_threshold=_d(state.min_balance_threshold),
        reload_amount=_d(state.reload_amount),
        reload_cooldown_minutes=state.reload_cooldown_minutes,
        last_reload_at=_dt(state.last_reload_at),
        current_balance=_d(state.current_balance),
        recent_events=[
            AutoReloadEventItem(
                id=e.id, success=e.success, reload_amount=_d(e.reload_amount),
                balance_before=_d(e.balance_before_reload),
                balance_after=_d(e.balance_after_reload),
                trigger_reason=e.trigger_reason,
                error_message=e.error_message,
                created_at=_dt_req(e.created_at),
            )
            for e in events
        ],
    )
