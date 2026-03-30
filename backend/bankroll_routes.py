"""
DuckPools - Bankroll P&L Routes

API endpoints for house P&L tracking and analytics.

MAT-231: P&L tracking per game round

Endpoints:
  GET /bankroll/pnl/summary     - Aggregated P&L stats
  GET /bankroll/pnl/rounds      - Paginated individual round P&L
  GET /bankroll/pnl/period      - P&L by time period (hour/day/week)
  GET /bankroll/pnl/player/{address} - Player-specific P&L
  POST /bankroll/pnl/record     - Manually record a round (for testing/migration)
"""

import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.bankroll_pnl import (
    get_period_pnl,
    get_player_pnl,
    get_rounds,
    get_summary,
    init_db,
    record_round,
)

logger = logging.getLogger("duckpools.bankroll")

router = APIRouter(prefix="/bankroll", tags=["bankroll"])

# Initialize P&L database on module import
init_db()


# ─── Request/Response Models ──────────────────────────────────────


class PnlSummaryResponse(BaseModel):
    total_rounds: int = 0
    wins: int = 0
    losses: int = 0
    refunds: int = 0
    win_rate_pct: float = 0.0
    total_wagered_nanoerg: int = 0
    total_wagered_erg: str = "0"
    total_payout_nanoerg: int = 0
    total_payout_erg: str = "0"
    total_fees_nanoerg: int = 0
    total_fees_erg: str = "0"
    net_pnl_nanoerg: int = 0
    net_pnl_erg: str = "0"
    avg_house_edge_realized_pct: float = 0.0
    biggest_round_win_nanoerg: int = 0
    biggest_round_win_erg: str = "0"
    biggest_round_loss_nanoerg: int = 0
    biggest_round_loss_erg: str = "0"


class PnlRoundItem(BaseModel):
    bet_id: str
    timestamp: str
    resolved_at: str
    player_address: str
    bet_amount_nanoerg: int
    bet_amount_erg: str
    outcome: str
    house_payout_nanoerg: int
    house_payout_erg: str
    house_fee_nanoerg: int
    house_fee_erg: str
    net_pnl_nanoerg: int
    net_pnl_erg: str
    game_type: str


class PnlRoundsResponse(BaseModel):
    rounds: list
    total: int
    limit: int
    offset: int


class PnlPeriodItem(BaseModel):
    period_start: str
    rounds: int
    house_wins: int
    player_wins: int
    refunds: int
    total_wagered_nanoerg: int
    total_wagered_erg: str
    total_payout_nanoerg: int
    total_payout_erg: str
    total_fees_nanoerg: int
    total_fees_erg: str
    net_pnl_nanoerg: int
    net_pnl_erg: str


class PlayerPnlResponse(BaseModel):
    player_address: str
    total_rounds: int
    wins: int
    losses: int
    refunds: int
    total_wagered_nanoerg: int
    total_wagered_erg: str
    total_won_nanoerg: int
    total_won_erg: str
    net_player_pnl_nanoerg: int
    net_player_pnl_erg: str


class RecordRoundRequest(BaseModel):
    bet_id: str
    player_address: str
    bet_amount_nanoerg: int
    outcome: str  # 'win', 'loss', 'refunded'
    house_payout_nanoerg: int = 0
    house_fee_nanoerg: int = 0
    bet_timestamp: Optional[str] = None
    game_type: str = "coinflip"


# ─── Routes ───────────────────────────────────────────────────────


@router.get("/pnl/summary", response_model=PnlSummaryResponse)
async def pnl_summary(
    since: Optional[str] = Query(None, description="ISO 8601 start time"),
    until: Optional[str] = Query(None, description="ISO 8601 end time"),
    game_type: Optional[str] = Query(None, description="Filter by game type"),
):
    """
    Get aggregated house P&L summary.

    Query params:
      - since: Start of time range (ISO 8601, e.g. '2026-03-30T00:00:00Z')
      - until: End of time range
      - game_type: Filter by game type (default: all)
    """
    data = get_summary(since=since, until=until, game_type=game_type)

    return PnlSummaryResponse(
        total_rounds=data["total_rounds"],
        wins=data["wins"],
        losses=data["losses"],
        refunds=data["refunds"],
        win_rate_pct=data["win_rate_pct"],
        total_wagered_nanoerg=data["total_wagered_nanoerg"],
        total_wagered_erg=f"{data['total_wagered_nanoerg'] / 1e9:.9f}",
        total_payout_nanoerg=data["total_payout_nanoerg"],
        total_payout_erg=f"{data['total_payout_nanoerg'] / 1e9:.9f}",
        total_fees_nanoerg=data["total_fees_nanoerg"],
        total_fees_erg=f"{data['total_fees_nanoerg'] / 1e9:.9f}",
        net_pnl_nanoerg=data["net_pnl_nanoerg"],
        net_pnl_erg=f"{data['net_pnl_nanoerg'] / 1e9:.9f}",
        avg_house_edge_realized_pct=data["avg_house_edge_realized_pct"],
        biggest_round_win_nanoerg=data["biggest_round_win_nanoerg"],
        biggest_round_win_erg=f"{data['biggest_round_win_nanoerg'] / 1e9:.9f}",
        biggest_round_loss_nanoerg=data["biggest_round_loss_nanoerg"],
        biggest_round_loss_erg=f"{data['biggest_round_loss_nanoerg'] / 1e9:.9f}",
    )


@router.get("/pnl/rounds", response_model=PnlRoundsResponse)
async def pnl_rounds(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    player_address: Optional[str] = Query(None, description="Filter by player address"),
    outcome: Optional[str] = Query(None, description="Filter by outcome: win, loss, refunded"),
    since: Optional[str] = Query(None, description="ISO 8601 start time"),
    until: Optional[str] = Query(None, description="ISO 8601 end time"),
):
    """
    Get paginated list of individual round P&L records.

    Query params:
      - limit: Page size (1-500, default 50)
      - offset: Pagination offset
      - player_address: Filter by player
      - outcome: Filter by outcome
      - since/until: Time range filter
    """
    if outcome and outcome not in ("win", "loss", "refunded"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome: {outcome}. Must be 'win', 'loss', or 'refunded'"
        )

    rounds, total = get_rounds(
        limit=limit,
        offset=offset,
        player_address=player_address,
        outcome=outcome,
        since=since,
        until=until,
    )

    return PnlRoundsResponse(
        rounds=rounds,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/pnl/period")
async def pnl_period(
    period: str = Query("day", description="Aggregation period: 'hour', 'day', or 'week'"),
):
    """
    Get P&L aggregated by time period.

    Query params:
      - period: 'hour', 'day', or 'week' (default: 'day')

    Returns up to 100 periods, most recent first.
    """
    if period not in ("hour", "day", "week"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period: {period}. Must be 'hour', 'day', or 'week'"
        )

    results = get_period_pnl(period=period)
    return {"periods": results, "period_type": period}


@router.get("/pnl/player/{address}", response_model=PlayerPnlResponse)
async def player_pnl(address: str):
    """
    Get P&L summary for a specific player (player-centric view).
    """
    data = get_player_pnl(address)

    return PlayerPnlResponse(**data)


@router.post("/pnl/record")
async def pnl_record(req: RecordRoundRequest):
    """
    Manually record a resolved round's P&L.

    Useful for testing and migrating historical data.
    In production, this is called internally when bets are resolved.
    """
    if req.outcome not in ("win", "loss", "refunded"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome: {req.outcome}. Must be 'win', 'loss', or 'refunded'"
        )

    if req.bet_amount_nanoerg <= 0:
        raise HTTPException(
            status_code=400,
            detail="bet_amount_nanoerg must be positive"
        )

    recorded = record_round(
        bet_id=req.bet_id,
        player_address=req.player_address,
        bet_amount_nanoerg=req.bet_amount_nanoerg,
        outcome=req.outcome,
        house_payout_nanoerg=req.house_payout_nanoerg,
        house_fee_nanoerg=req.house_fee_nanoerg,
        bet_timestamp=req.bet_timestamp,
        game_type=req.game_type,
    )

    if not recorded:
        raise HTTPException(
            status_code=409,
            detail=f"Bet {req.bet_id} already recorded"
        )

    return {
        "success": True,
        "bet_id": req.bet_id,
        "message": f"P&L round recorded: {req.outcome}",
    }


# ─── Health Check ─────────────────────────────────────────────────


@router.get("/pnl/health")
async def pnl_health():
    """Check P&L tracking service health."""
    try:
        summary = get_summary()
        return {
            "status": "healthy",
            "total_rounds": summary["total_rounds"],
            "net_pnl_nanoerg": summary["net_pnl_nanoerg"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"P&L service unhealthy: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════
# MAT-230: Bankroll Monitoring API
# ═══════════════════════════════════════════════════════════════════════
#
# Endpoints for real-time bankroll state monitoring.
# Queries the Ergo node for wallet balances and on-chain boxes.
#
# GET /bankroll/status   - Live balance, exposure, capacity
# GET /bankroll/history  - Balance snapshots over time
# GET /bankroll/metrics  - Utilization, sizing, key stats
# ─────────────────────────────────────────────────────────────────────

# Ergo node config
_NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
_NODE_API_KEY = os.getenv("NODE_API_KEY", "")

# Safety factor: max single bet = 10% of available capacity
_SAFETY_FACTOR = Decimal("0.10")

# Snapshot storage (in-memory for PoC; production would use DB)
_balance_snapshots: list = []
_MAX_SNAPSHOTS = 1000  # Keep last 1000 snapshots


def _node_headers() -> dict:
    """Build headers for Ergo node API calls."""
    headers = {"Content-Type": "application/json"}
    if _NODE_API_KEY:
        headers["api_key"] = _NODE_API_KEY
    return headers


async def _query_node(endpoint: str, timeout: float = 10) -> dict:
    """Generic async query to the Ergo node."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{_NODE_URL}{endpoint}",
            headers=_node_headers(),
        )
        resp.raise_for_status()
        return resp.json()


# ─── Response Models ──────────────────────────────────────────────────


class BankrollStatusResponse(BaseModel):
    """Live bankroll state."""
    wallet_balance_nanoerg: int = 0
    wallet_balance_erg: str = "0"
    pending_exposure_nanoerg: int = 0
    pending_exposure_erg: str = "0"
    available_capacity_nanoerg: int = 0
    available_capacity_erg: str = "0"
    utilization_pct: float = 0.0
    max_single_bet_nanoerg: int = 0
    max_single_bet_erg: str = "0"
    pending_bet_count: int = 0
    node_height: int = 0
    timestamp: str = ""


class BalanceSnapshot(BaseModel):
    timestamp: str
    wallet_balance_nanoerg: int
    wallet_balance_erg: str
    pending_exposure_nanoerg: int
    available_capacity_nanoerg: int
    pending_bet_count: int


class BankrollHistoryResponse(BaseModel):
    snapshots: list
    total: int
    period_hours: int = 24


class BankrollMetricsResponse(BaseModel):
    total_rounds: int
    wins: int
    losses: int
    refunds: int
    win_rate_pct: float
    utilization_pct: float
    avg_bet_size_nanoerg: int = 0
    avg_bet_size_erg: str = "0"
    peak_exposure_nanoerg: int = 0
    peak_exposure_erg: str = "0"
    total_fees_nanoerg: int = 0
    total_fees_erg: str = "0"
    net_pnl_nanoerg: int = 0
    net_pnl_erg: str = "0"
    roi_pct: float = 0.0
    max_single_bet_nanoerg: int = 0
    max_single_bet_erg: str = "0"
    node_height: int = 0


# ─── Helper: compute pending exposure from on-chain boxes ────────────
# Queries the Ergo node for unspent boxes matching the coinflip contract
# ergoTree. This gives real-time on-chain exposure without relying on
# in-memory state. Matches the pattern used by DeFi Architect Sr in
# pool_manager.py (byErgoTree scan).
#
# The coinflip ergoTree is defined in game_routes.py (COINFLIP_ERGO_TREE).
# We import it to stay in sync with the deployed contract.

# Cache the ergoTree hash to avoid recomputing on every call
_ergo_tree_hash: Optional[str] = None


def _get_ergo_tree_hash() -> str:
    """
    Get the ergoTree hash for scanning PendingBet boxes.

    Since COINFLIP_ERGO_TREE is empty (Lithos limitation), we use
    the byErgoTree scan with the P2S address-derived hash, or fall
    back to the in-memory store.
    """
    global _ergo_tree_hash
    if _ergo_tree_hash is not None:
        return _ergo_tree_hash
    # Cannot compute ergoTree hash from P2S address alone.
    # Mark as empty to trigger fallback to in-memory store.
    _ergo_tree_hash = ""
    logger.warning("ergoTree hex not available from Lithos — bankroll exposure will use in-memory fallback")
    return _ergo_tree_hash


async def _get_pending_exposure() -> tuple:
    """
    Get pending bet exposure by scanning on-chain unspent boxes.

    Queries /blockchain/box/unspent/byErgoTree/{hash} on the Ergo node
    to find all PendingBet boxes, then sums their ERG values.

    Returns (exposure_nanoerg, pending_count).
    Falls back to in-memory store if node query fails.
    """
    ergo_hash = _get_ergo_tree_hash()
    if not ergo_hash:
        logger.warning("No ergoTree hash available, falling back to in-memory")
        return await _get_pending_exposure_fallback()

    try:
        boxes = await _query_node(f"/blockchain/box/unspent/byErgoTree/{ergo_hash}")
        if not boxes:
            return 0, 0

        exposure = 0
        count = 0
        for box in boxes:
            box_value = int(box.get("value", 0))
            exposure += box_value
            count += 1

        logger.debug("On-chain exposure scan: %d PendingBet boxes, %s nanoERG", count, exposure)
        return exposure, count
    except Exception as e:
        logger.warning("On-chain exposure query failed: %s, falling back to in-memory", e)
        return await _get_pending_exposure_fallback()


async def _get_pending_exposure_fallback() -> tuple:
    """Fallback: read pending bets from in-memory store."""
    try:
        from game_routes import _bets
        pending_bets = [b for b in _bets if b["outcome"] == "pending"]
        exposure = sum(int(b.get("betAmount", "0")) for b in pending_bets)
        return exposure, len(pending_bets)
    except ImportError:
        return 0, 0


def _record_snapshot(
    balance_nanoerg: int,
    exposure_nanoerg: int,
    pending_count: int,
):
    """Record a balance snapshot for history tracking."""
    now = datetime.now(timezone.utc).isoformat()
    _balance_snapshots.append({
        "timestamp": now,
        "wallet_balance_nanoerg": balance_nanoerg,
        "wallet_balance_erg": f"{Decimal(balance_nanoerg) / Decimal('1e9'):.9f}",
        "pending_exposure_nanoerg": exposure_nanoerg,
        "available_capacity_nanoerg": max(0, balance_nanoerg - exposure_nanoerg),
        "pending_bet_count": pending_count,
    })
    # Trim to max size (FIFO)
    while len(_balance_snapshots) > _MAX_SNAPSHOTS:
        _balance_snapshots.pop(0)


# ─── Routes ───────────────────────────────────────────────────────────


@router.get("/status", response_model=BankrollStatusResponse)
async def bankroll_status():
    """
    Live bankroll status (MAT-230).

    Returns:
    - wallet_balance: ERG in house wallet (from node /wallet/balances)
    - pending_exposure: Sum of ERG locked in pending bets
    - available_capacity: balance - exposure
    - max_single_bet: 10% of available capacity (safety factor)
    - utilization_pct: exposure / balance * 100
    - pending_bet_count: Number of unresolved bets
    - node_height: Current block height
    """
    # 1. Fetch wallet balance from node
    try:
        wallet_data = await _query_node("/wallet/balances")
        balance_nanoerg = int(wallet_data.get("balance", 0))
    except Exception as e:
        logger.warning("Failed to fetch wallet balance: %s", e)
        balance_nanoerg = 0

    # 2. Fetch node height
    try:
        info = await _query_node("/info")
        node_height = info.get("fullHeight", 0) or 0
    except Exception:
        node_height = 0

    # 3. Get pending exposure
    exposure_nanoerg, pending_count = await _get_pending_exposure()

    # 4. Calculate derived metrics
    capacity_nanoerg = max(0, balance_nanoerg - exposure_nanoerg)
    max_bet_nanoerg = int(Decimal(capacity_nanoerg) * _SAFETY_FACTOR)
    utilization_pct = (
        float(Decimal(exposure_nanoerg) / Decimal(balance_nanoerg) * 100)
        if balance_nanoerg > 0
        else 0.0
    )

    # 5. Record snapshot for history
    _record_snapshot(balance_nanoerg, exposure_nanoerg, pending_count)

    return BankrollStatusResponse(
        wallet_balance_nanoerg=balance_nanoerg,
        wallet_balance_erg=f"{Decimal(balance_nanoerg) / Decimal('1e9'):.9f}",
        pending_exposure_nanoerg=exposure_nanoerg,
        pending_exposure_erg=f"{Decimal(exposure_nanoerg) / Decimal('1e9'):.9f}",
        available_capacity_nanoerg=capacity_nanoerg,
        available_capacity_erg=f"{Decimal(capacity_nanoerg) / Decimal('1e9'):.9f}",
        utilization_pct=round(utilization_pct, 2),
        max_single_bet_nanoerg=max_bet_nanoerg,
        max_single_bet_erg=f"{Decimal(max_bet_nanoerg) / Decimal('1e9'):.9f}",
        pending_bet_count=pending_count,
        node_height=node_height,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/history", response_model=BankrollHistoryResponse)
async def bankroll_history(
    hours: int = Query(24, ge=1, le=168, description="Lookback period in hours (1-168)"),
    limit: int = Query(100, ge=1, le=500, description="Max snapshots to return"),
):
    """
    Historical bankroll balance snapshots (MAT-230).

    Returns time-series of balance snapshots within the lookback period.
    Snapshots are recorded each time /bankroll/status is called.

    Query params:
    - hours: Lookback window (default 24h, max 168h = 7 days)
    - limit: Max number of snapshots (default 100)
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    # Filter snapshots within the time window
    filtered = []
    for snap in _balance_snapshots:
        try:
            snap_time = datetime.fromisoformat(snap["timestamp"])
            if snap_time >= cutoff:
                filtered.append(snap)
        except (ValueError, TypeError):
            continue

    # Most recent first
    filtered.reverse()
    filtered = filtered[:limit]

    return BankrollHistoryResponse(
        snapshots=filtered,
        total=len(filtered),
        period_hours=hours,
    )


@router.get("/metrics", response_model=BankrollMetricsResponse)
async def bankroll_metrics():
    """
    Bankroll performance metrics (MAT-230).

    Combines live node data with P&L aggregation for a comprehensive
    view of bankroll health.

    Returns:
    - Round statistics (total, wins, losses, refunds, win rate)
    - Utilization (current exposure vs capacity)
    - Sizing (avg bet, max bet, peak exposure)
    - Financials (total fees, net P&L, ROI)
    """
    # 1. Fetch wallet balance and node height
    try:
        wallet_data = await _query_node("/wallet/balances")
        balance_nanoerg = int(wallet_data.get("balance", 0))
    except Exception:
        balance_nanoerg = 0

    try:
        info = await _query_node("/info")
        node_height = info.get("fullHeight", 0) or 0
    except Exception:
        node_height = 0

    # 2. Get pending exposure
    exposure_nanoerg, pending_count = await _get_pending_exposure()

    # 3. Get P&L summary
    try:
        pnl = get_summary()
        total_rounds = pnl["total_rounds"]
        wins = pnl["wins"]
        losses = pnl["losses"]
        refunds = pnl["refunds"]
        total_wagered = pnl["total_wagered_nanoerg"]
        total_fees = pnl["total_fees_nanoerg"]
        net_pnl = pnl["net_pnl_nanoerg"]
        biggest_loss = pnl["biggest_round_loss_nanoerg"]
    except Exception as e:
        logger.warning("Failed to get P&L summary: %s", e)
        total_rounds = wins = losses = refunds = 0
        total_wagered = total_fees = net_pnl = biggest_loss = 0

    # 4. Calculate derived metrics
    resolved_rounds = wins + losses + refunds
    win_rate_pct = (wins / resolved_rounds * 100) if resolved_rounds > 0 else 0.0
    avg_bet_size = total_wagered // resolved_rounds if resolved_rounds > 0 else 0

    capacity_nanoerg = max(0, balance_nanoerg - exposure_nanoerg)
    utilization_pct = (
        float(Decimal(exposure_nanoerg) / Decimal(balance_nanoerg) * 100)
        if balance_nanoerg > 0
        else 0.0
    )
    max_bet_nanoerg = int(Decimal(capacity_nanoerg) * _SAFETY_FACTOR)

    # Peak exposure from snapshots
    peak_exposure = exposure_nanoerg
    for snap in _balance_snapshots:
        snap_exp = snap.get("pending_exposure_nanoerg", 0)
        if snap_exp > peak_exposure:
            peak_exposure = snap_exp

    # ROI: net P&L as percentage of total wagered
    roi_pct = (
        float(Decimal(net_pnl) / Decimal(total_wagered) * 100)
        if total_wagered > 0
        else 0.0
    )

    return BankrollMetricsResponse(
        total_rounds=resolved_rounds,
        wins=wins,
        losses=losses,
        refunds=refunds,
        win_rate_pct=round(win_rate_pct, 2),
        utilization_pct=round(utilization_pct, 2),
        avg_bet_size_nanoerg=avg_bet_size,
        avg_bet_size_erg=f"{Decimal(avg_bet_size) / Decimal('1e9'):.9f}",
        peak_exposure_nanoerg=peak_exposure,
        peak_exposure_erg=f"{Decimal(peak_exposure) / Decimal('1e9'):.9f}",
        total_fees_nanoerg=total_fees,
        total_fees_erg=f"{Decimal(total_fees) / Decimal('1e9'):.9f}",
        net_pnl_nanoerg=net_pnl,
        net_pnl_erg=f"{Decimal(net_pnl) / Decimal('1e9'):.9f}",
        roi_pct=round(roi_pct, 4),
        max_single_bet_nanoerg=max_bet_nanoerg,
        max_single_bet_erg=f"{Decimal(max_bet_nanoerg) / Decimal('1e9'):.9f}",
        node_height=node_height,
    )
