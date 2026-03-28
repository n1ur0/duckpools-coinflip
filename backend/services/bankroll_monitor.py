"""
DuckPools - Bankroll Monitor Service

Real-time bankroll monitoring that polls the Ergo node for wallet balance
and tracks pending bet exposure. Provides status, history, and P&L metrics.

MAT-230: Bankroll monitoring service
MAT-205: P&L tracking per game round
"""

import asyncio
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("duckpools.bankroll_monitor")


# ─── Configuration ───────────────────────────────────────────────

NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", os.getenv("API_KEY", "hello"))


# ─── Snapshot ────────────────────────────────────────────────────

@dataclass
class BankrollSnapshot:
    """Point-in-time bankroll state."""
    timestamp: str
    balance_nanoerg: int
    exposure_nanoerg: int
    node_height: int


# ─── P&L Record ──────────────────────────────────────────────────

@dataclass
class PnLRecord:
    """Per-round P&L record from the house perspective."""
    bet_id: str
    player_address: str
    bet_amount_nanoerg: int
    outcome: str  # "win" (player won) or "loss" (player lost)
    house_payout_nanoerg: int  # what house paid to player (0 on player loss)
    house_profit_nanoerg: int  # positive = house made money
    timestamp: str
    block_height: int = 0


# ─── Monitor Service ─────────────────────────────────────────────

class BankrollMonitorService:
    """
    Monitors the house bankroll by polling the Ergo node wallet balance
    and tracking pending bet exposure from game history.
    
    Thread-safe. Designed to be a singleton created once in the FastAPI lifespan.
    """

    def __init__(self, snapshot_history_size: int = 288):
        """
        Args:
            snapshot_history_size: Max snapshots to keep (288 = 24h at 5min intervals)
        """
        self._lock = threading.RLock()
        self._snapshots: Deque[BankrollSnapshot] = deque(maxlen=snapshot_history_size)
        self._pnl_records: List[PnLRecord] = []
        self._peak_exposure_nanoerg: int = 0
        self._last_node_height: int = 0
        self._http_client = None  # Lazy init
        self._snapshot_interval_sec = 300  # 5 minutes

    # ─── Public API (called by route handlers) ──────────────────

    async def get_status(self) -> dict:
        """
        Get real-time bankroll status.
        
        Returns dict matching BankrollStatusResponse schema.
        """
        balance, exposure, height = await self._fetch_bankroll_and_exposure()

        available = max(0, balance - exposure)
        max_bet = available // 10  # 10% of available capacity

        return {
            "balance_nanoerg": balance,
            "balance_erg": balance / 1e9,
            "exposure_nanoerg": exposure,
            "exposure_erg": exposure / 1e9,
            "available_capacity_nanoerg": available,
            "available_capacity_erg": available / 1e9,
            "max_single_bet_nanoerg": max_bet,
            "max_single_bet_erg": max_bet / 1e9,
            "pending_bet_count": self._count_pending_bets_from_pnl(),
            "node_height": height,
        }

    async def get_history(self, limit: int = 50, offset: int = 0) -> dict:
        """
        Get historical bankroll balance snapshots.
        
        Returns dict matching BankrollHistoryResponse schema.
        """
        with self._lock:
            all_snapshots = list(reversed(self._snapshots))
        
        page = all_snapshots[offset : offset + limit]
        
        return {
            "snapshots": [
                {
                    "timestamp": s.timestamp,
                    "balance_nanoerg": s.balance_nanoerg,
                    "balance_erg": s.balance_nanoerg / 1e9,
                    "exposure_nanoerg": s.exposure_nanoerg,
                    "exposure_erg": s.exposure_nanoerg / 1e9,
                    "node_height": s.node_height,
                }
                for s in page
            ],
            "total": len(all_snapshots),
            "limit": limit,
        }

    async def get_metrics(self) -> dict:
        """
        Get key bankroll performance metrics including P&L.
        
        Returns dict matching BankrollMetricsResponse schema.
        """
        balance, exposure, height = await self._fetch_bankroll_and_exposure()

        with self._lock:
            pnl_records = list(self._pnl_records)
            peak_exposure = self._peak_exposure_nanoerg

        # Aggregate P&L from records
        total_pnl = 0
        total_wagered = 0
        total_payouts = 0
        num_rounds = len(pnl_records)
        house_wins = 0
        total_bet_sizes = 0

        for r in pnl_records:
            total_pnl += r.house_profit_nanoerg
            total_wagered += r.bet_amount_nanoerg
            if r.outcome == "win":  # player won
                total_payouts += r.house_payout_nanoerg
            else:
                house_wins += 1
            total_bet_sizes += r.bet_amount_nanoerg

        avg_bet = total_bet_sizes // num_rounds if num_rounds > 0 else 0
        utilization = exposure / balance if balance > 0 else 0.0
        house_win_rate = house_wins / num_rounds if num_rounds > 0 else 0.0
        
        # Actual house edge in basis points
        actual_edge_bps = (total_pnl / total_wagered * 10000) if total_wagered > 0 else 0.0

        return {
            "total_pnl_nanoerg": total_pnl,
            "total_pnl_erg": total_pnl / 1e9,
            "total_wagered_nanoerg": total_wagered,
            "total_wagered_erg": total_wagered / 1e9,
            "num_rounds": num_rounds,
            "utilization_ratio": round(utilization, 6),
            "avg_bet_size_nanoerg": avg_bet,
            "avg_bet_size_erg": avg_bet / 1e9,
            "peak_exposure_nanoerg": peak_exposure,
            "peak_exposure_erg": peak_exposure / 1e9,
            "house_win_rate": round(house_win_rate, 4),
            "actual_house_edge_bps": round(actual_edge_bps, 2),
        }

    def record_pnl(
        self,
        bet_id: str,
        player_address: str,
        bet_amount_nanoerg: int,
        outcome: str,
        house_payout_nanoerg: int,
        block_height: int = 0,
    ) -> None:
        """
        Record a P&L entry for a resolved bet.
        
        Call this from the bet resolution flow (bot endpoint).
        
        Args:
            bet_id: Unique bet identifier
            player_address: Player's Ergo address
            bet_amount_nanoerg: Amount wagered
            outcome: "win" (player won) or "loss" (player lost)
            house_payout_nanoerg: Amount house paid to player (0 on loss)
            block_height: Block height when resolved
        """
        # House profit: if player lost, house keeps the bet.
        # If player won, house profit = bet - payout.
        if outcome == "win":
            house_profit = bet_amount_nanoerg - house_payout_nanoerg
        elif outcome == "loss":
            house_profit = bet_amount_nanoerg  # house keeps entire bet
        elif outcome == "refunded":
            house_profit = 0
        else:
            logger.warning("record_pnl: unknown outcome '%s' for bet %s", outcome, bet_id)
            house_profit = 0

        record = PnLRecord(
            bet_id=bet_id,
            player_address=player_address,
            bet_amount_nanoerg=bet_amount_nanoerg,
            outcome=outcome,
            house_payout_nanoerg=house_payout_nanoerg,
            house_profit_nanoerg=house_profit,
            timestamp=datetime.now(timezone.utc).isoformat(),
            block_height=block_height,
        )

        with self._lock:
            self._pnl_records.append(record)
            # Update peak exposure (use latest exposure as proxy)
            # Peak is tracked in _take_snapshot when we have real exposure data

        logger.info(
            "P&L recorded: bet=%s outcome=%s house_profit=%s nanoERG (%.4f ERG)",
            bet_id[:12] + "...",
            outcome,
            house_profit,
            house_profit / 1e9,
        )

    def get_pnl_history(
        self,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        limit: int = 100,
    ) -> dict:
        """
        Query P&L records with optional time range filtering.
        
        Args:
            from_ts: ISO timestamp start (inclusive)
            to_ts: ISO timestamp end (inclusive)
            limit: Max records to return
        
        Returns:
            Dict with records, totals, and filters applied.
        """
        with self._lock:
            records = list(self._pnl_records)

        # Filter by time range
        if from_ts:
            records = [r for r in records if r.timestamp >= from_ts]
        if to_ts:
            records = [r for r in records if r.timestamp <= to_ts]

        # Most recent first
        records = list(reversed(records[-limit:]))

        # Compute aggregates for filtered range
        total_profit = sum(r.house_profit_nanoerg for r in records)
        total_wagered = sum(r.bet_amount_nanoerg for r in records)

        return {
            "records": [
                {
                    "bet_id": r.bet_id,
                    "player_address": r.player_address,
                    "bet_amount_nanoerg": r.bet_amount_nanoerg,
                    "bet_amount_erg": r.bet_amount_nanoerg / 1e9,
                    "outcome": r.outcome,
                    "house_payout_nanoerg": r.house_payout_nanoerg,
                    "house_profit_nanoerg": r.house_profit_nanoerg,
                    "house_profit_erg": r.house_profit_nanoerg / 1e9,
                    "timestamp": r.timestamp,
                    "block_height": r.block_height,
                }
                for r in records
            ],
            "total_profit_nanoerg": total_profit,
            "total_profit_erg": total_profit / 1e9,
            "total_wagered_nanoerg": total_wagered,
            "total_wagered_erg": total_wagered / 1e9,
            "count": len(records),
            "house_edge_actual_bps": round(
                (total_profit / total_wagered * 10000) if total_wagered > 0 else 0.0, 2
            ),
        }

    # ─── Background Tasks ──────────────────────────────────────

    async def take_snapshot(self) -> Optional[BankrollSnapshot]:
        """
        Take a bankroll snapshot and store it. Call periodically from a background task.
        """
        try:
            balance, exposure, height = await self._fetch_bankroll_and_exposure()
            
            snapshot = BankrollSnapshot(
                timestamp=datetime.now(timezone.utc).isoformat(),
                balance_nanoerg=balance,
                exposure_nanoerg=exposure,
                node_height=height,
            )

            with self._lock:
                self._snapshots.append(snapshot)
                if exposure > self._peak_exposure_nanoerg:
                    self._peak_exposure_nanoerg = exposure
                self._last_node_height = height

            logger.debug(
                "Snapshot: balance=%.4f ERG, exposure=%.4f ERG, height=%d",
                balance / 1e9, exposure / 1e9, height,
            )
            return snapshot

        except Exception as e:
            logger.error("Failed to take snapshot: %s", e, exc_info=True)
            return None

    # ─── Internal ───────────────────────────────────────────────

    async def _fetch_bankroll_and_exposure(self) -> Tuple[int, int, int]:
        """
        Fetch current wallet balance (bankroll) and pending bet exposure.
        
        Returns:
            (balance_nanoerg, exposure_nanoerg, node_height)
        """
        import httpx

        balance = 0
        exposure = 0
        height = 0

        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"api_key": NODE_API_KEY, "Content-Type": "application/json"}

            # Fetch wallet balance
            try:
                resp = await client.get(f"{NODE_URL}/wallet/balances", headers=headers)
                resp.raise_for_status()
                data = resp.json()
                balance = int(data.get("balance", 0))
            except Exception as e:
                logger.warning("Failed to fetch wallet balance: %s", e)

            # Fetch node height
            try:
                resp = await client.get(f"{NODE_URL}/info", headers=headers)
                resp.raise_for_status()
                info = resp.json()
                height = info.get("fullHeight", 0)
            except Exception as e:
                logger.warning("Failed to fetch node info: %s", e)

            # Exposure: sum of pending bet amounts from P&L records
            # (In a production system this would query the blockchain for
            # unspent PendingBet boxes by NFT token ID)
            with self._lock:
                exposure = sum(
                    r.bet_amount_nanoerg
                    for r in self._pnl_records
                    if r.outcome == "pending"  # pending bets still locked
                ) if hasattr(self, '_pending_exposure') else 0

        return balance, exposure, height

    def _count_pending_bets_from_pnl(self) -> int:
        """Count bets that are still pending (have locked funds)."""
        # In-memory PnL records only track resolved bets.
        # Pending count comes from game history service if available.
        return 0  # Will be wired to game_history in the unified manager


# ─── Singleton ───────────────────────────────────────────────────

_monitor_instance: Optional[BankrollMonitorService] = None


def get_bankroll_monitor_service() -> BankrollMonitorService:
    """Get or create the BankrollMonitorService singleton."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = BankrollMonitorService()
    return _monitor_instance
