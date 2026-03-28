"""
DuckPools - Unified Bankroll Manager

Facade that combines bankroll monitoring, risk calculations, auto-reload,
and P&L tracking into a single cohesive service.

MAT-192: Integrate bankroll management system
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("duckpools.bankroll_manager")


class BankrollManager:
    """
    Unified facade for all bankroll operations.
    
    Wires together:
    - BankrollMonitorService (status, snapshots, P&L)
    - bankroll_risk (Kelly, RoR, variance projections)
    - BankrollAutoReload (auto-topup when low)
    
    Usage in FastAPI:
        manager = BankrollManager(app)
        status = await manager.get_dashboard()
    """

    def __init__(self, app):
        """
        Initialize from FastAPI app state.
        
        Args:
            app: FastAPI application instance (reads app.state.*)
        """
        from services.bankroll_monitor import get_bankroll_monitor_service
        from bankroll_risk import (
            GameParams,
            compute_full_risk_metrics,
            variance_projection,
            DEFAULT_HOUSE_EDGE,
        )

        self._app = app
        self._monitor = get_bankroll_monitor_service()
        self._risk_params = GameParams()
        self._compute_risk = compute_full_risk_metrics
        self._variance_proj = variance_projection

    async def get_dashboard(self) -> dict:
        """
        Get a comprehensive bankroll dashboard in one call.
        
        Combines status, risk metrics, P&L, and auto-reload state.
        This is the primary endpoint operators use to monitor the protocol.
        """
        # Fetch real-time status
        status = await self._monitor.get_status()
        
        # Fetch P&L metrics
        pnl = await self._monitor.get_metrics()
        
        # Compute risk metrics
        balance = status["balance_nanoerg"]
        max_bet = status["max_single_bet_nanoerg"]
        if max_bet <= 0:
            max_bet = 1_000_000_000  # Default 1 ERG for risk calc
        
        risk = self._compute_risk(balance, max_bet, params=self._risk_params)
        
        # Auto-reload state
        autoreload = {}
        autoreload_mgr = getattr(self._app.state, "autoreload_manager", None)
        if autoreload_mgr is not None:
            autoreload = autoreload_mgr.get_config()
        
        return {
            # Status
            "balance_nanoerg": status["balance_nanoerg"],
            "balance_erg": status["balance_erg"],
            "exposure_nanoerg": status["exposure_nanoerg"],
            "exposure_erg": status["exposure_erg"],
            "available_capacity_erg": status["available_capacity_erg"],
            "max_single_bet_erg": status["max_single_bet_erg"],
            "pending_bet_count": status["pending_bet_count"],
            "node_height": status["node_height"],
            
            # P&L
            "total_pnl_erg": pnl["total_pnl_erg"],
            "total_wagered_erg": pnl["total_wagered_erg"],
            "total_rounds": pnl["num_rounds"],
            "utilization_ratio": pnl["utilization_ratio"],
            "avg_bet_erg": pnl["avg_bet_size_erg"],
            "house_win_rate": pnl["house_win_rate"],
            "actual_house_edge_bps": pnl["actual_house_edge_bps"],
            
            # Risk
            "kelly_fraction": risk.kelly_fraction,
            "kelly_fraction_quarter": risk.kelly_fraction_quarter,
            "risk_of_ruin": risk.risk_of_ruin,
            "safety_ratio": risk.safety_ratio,
            "bankroll_units": risk.bankroll_units,
            "min_bankroll_1pct_erg": risk.min_bankroll_1pct / 1e9,
            "n_bets_for_reliability": risk.n_bets_for_1sigma,
            
            # Auto-reload
            "autoreload": autoreload,
            
            # Health indicators
            "alerts": self._generate_alerts(status, risk, pnl),
        }

    def _generate_alerts(self, status: dict, risk, pnl: dict) -> list:
        """
        Generate operational alerts based on current state.
        
        Returns list of alert dicts with severity and message.
        """
        alerts = []
        balance = status["balance_nanoerg"]
        exposure = status["exposure_nanoerg"]
        
        # Solvency alert: exposure > 80% of balance
        if balance > 0 and exposure / balance > 0.8:
            alerts.append({
                "severity": "critical",
                "code": "HIGH_EXPOSURE",
                "message": f"Exposure ({exposure/1e9:.2f} ERG) is {exposure/balance*100:.0f}% of balance. "
                           f"Consider reducing max bet or adding liquidity.",
            })
        
        # Low bankroll alert
        if balance < 10_000_000_000:  # < 10 ERG
            alerts.append({
                "severity": "critical",
                "code": "LOW_BANKROLL",
                "message": f"Bankroll ({balance/1e9:.2f} ERG) is critically low. "
                           f"Min recommended for 1% RoR: {risk.min_bankroll_1pct/1e9:.2f} ERG.",
            })
        elif balance < 100_000_000_000:  # < 100 ERG
            alerts.append({
                "severity": "warning",
                "code": "MODERATE_BANKROLL",
                "message": f"Bankroll ({balance/1e9:.2f} ERG) below 100 ERG threshold.",
            })
        
        # Safety ratio alert
        if risk.safety_ratio < 1.0:
            alerts.append({
                "severity": "critical",
                "code": "INSUFFICIENT_BANKROLL",
                "message": f"Safety ratio {risk.safety_ratio:.2f}x -- bankroll below minimum for 1% RoR. "
                           f"Protocol is at significant risk of depletion.",
            })
        elif risk.safety_ratio < 3.0:
            alerts.append({
                "severity": "warning",
                "code": "LOW_SAFETY_RATIO",
                "message": f"Safety ratio {risk.safety_ratio:.2f}x -- recommend maintaining 3x+ for comfort.",
            })
        
        # House edge divergence alert
        expected_edge_bps = 300  # 3%
        if pnl["num_rounds"] > 50:  # Only alert after enough rounds
            actual_edge = pnl["actual_house_edge_bps"]
            if actual_edge < expected_edge_bps * 0.5:
                alerts.append({
                    "severity": "warning",
                    "code": "LOW_REALIZED_EDGE",
                    "message": f"Realized house edge ({actual_edge:.0f} bps) is below 50% of expected "
                               f"({expected_edge_bps} bps) over {pnl['num_rounds']} rounds. "
                               f"May be statistical variance or a bug.",
                })
        
        return alerts

    def record_bet_pnl(
        self,
        bet_id: str,
        player_address: str,
        bet_amount_nanoerg: int,
        outcome: str,
        house_payout_nanoerg: int,
        block_height: int = 0,
    ) -> None:
        """
        Record P&L for a resolved bet. Call from bet resolution flow.
        
        Delegates to BankrollMonitorService.record_pnl().
        """
        self._monitor.record_pnl(
            bet_id=bet_id,
            player_address=player_address,
            bet_amount_nanoerg=bet_amount_nanoerg,
            outcome=outcome,
            house_payout_nanoerg=house_payout_nanoerg,
            block_height=block_height,
        )
