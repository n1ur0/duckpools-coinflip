"""
DuckPools - Bankroll Auto-Reload Mechanism

Periodically monitors bankroll and triggers a top-up when balance drops
below a configurable threshold. Uses asyncio background task.

MAT-233: Auto-reload mechanism when bankroll drops below threshold
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger("duckpools.bankroll_autoreload")


# ─── Configuration ───────────────────────────────────────────────

@dataclass
class AutoReloadConfig:
    """Configuration for the auto-reload mechanism."""
    enabled: bool = True
    min_erg: float = 10.0       # Trigger reload below this (ERG)
    target_erg: float = 100.0   # Target after reload (ERG)
    check_interval_sec: int = 60  # How often to check
    max_erg_per_reload: float = 100.0  # Cap per single reload
    cooldown_sec: int = 600     # Min seconds between reloads (10 min)
    reserve_wallet_address: str = ""  # Wallet to fund reloads (empty = log only)


# ─── Reload Event ────────────────────────────────────────────────

@dataclass
class ReloadEvent:
    """Record of a reload attempt."""
    timestamp: str
    triggered_by_balance_erg: float
    target_amount_erg: float
    actual_amount_erg: float
    status: str  # "success", "failed", "dry_run"
    tx_id: Optional[str] = None
    error: Optional[str] = None


# ─── Auto-Reload Manager ─────────────────────────────────────────

class BankrollAutoReload:
    """
    Manages periodic bankroll monitoring and auto-reload.
    
    Usage:
        manager = BankrollAutoReload(config)
        # In FastAPI lifespan:
        asyncio.create_task(manager.run(app.state.pool_manager))
    """

    def __init__(self, config: Optional[AutoReloadConfig] = None):
        self.config = config or AutoReloadConfig()
        self._history: List[ReloadEvent] = []
        self._last_reload_time: float = 0.0
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._get_bankroll_fn = None  # Set externally

    def set_bankroll_fn(self, fn):
        """
        Set the async function to get current bankroll (nanoERG).
        Signature: async () -> int
        """
        self._get_bankroll_fn = fn

    def get_config(self) -> dict:
        """Return config dict (with sensitive values masked)."""
        return {
            "enabled": self.config.enabled,
            "min_erg": self.config.min_erg,
            "target_erg": self.config.target_erg,
            "check_interval_sec": self.config.check_interval_sec,
            "max_erg_per_reload": self.config.max_erg_per_reload,
            "cooldown_sec": self.config.cooldown_sec,
            "reserve_wallet_configured": bool(self.config.reserve_wallet_address),
        }

    def update_config(self, **kwargs) -> AutoReloadConfig:
        """Update configuration fields. Returns new config."""
        allowed = {
            "enabled", "min_erg", "target_erg",
            "check_interval_sec", "max_erg_per_reload",
            "cooldown_sec", "reserve_wallet_address",
        }
        for key, value in kwargs.items():
            if key in allowed:
                setattr(self.config, key, value)
            else:
                raise ValueError(f"Unknown config field: {key}")
        return self.config

    def get_history(self, limit: int = 50) -> List[dict]:
        """Return recent reload events."""
        events = self._history[-limit:]
        return [
            {
                "timestamp": e.timestamp,
                "triggered_by_balance_erg": e.triggered_by_balance_erg,
                "target_amount_erg": e.target_amount_erg,
                "actual_amount_erg": e.actual_amount_erg,
                "status": e.status,
                "tx_id": e.tx_id,
                "error": e.error,
            }
            for e in events
        ]

    async def run(self, pool_manager=None):
        """
        Main monitoring loop. Run as an asyncio background task.
        
        Args:
            pool_manager: PoolStateManager instance (fallback for bankroll read)
        """
        self._running = True
        logger.info(
            "Auto-reload started: enabled=%s, min=%.1f ERG, target=%.1f ERG, interval=%ds",
            self.config.enabled, self.config.min_erg,
            self.config.target_erg, self.config.check_interval_sec,
        )

        while self._running:
            try:
                await self._check_and_reload(pool_manager)
            except Exception as e:
                logger.error("Auto-reload check failed: %s", e, exc_info=True)

            await asyncio.sleep(self.config.check_interval_sec)

        logger.info("Auto-reload stopped")

    def stop(self):
        """Signal the background task to stop."""
        self._running = False

    async def _check_and_reload(self, pool_manager=None):
        """Check bankroll and trigger reload if below threshold."""
        if not self.config.enabled:
            return

        # Get current bankroll
        bankroll_nanoerg = await self._get_current_bankroll(pool_manager)
        if bankroll_nanoerg is None:
            return

        bankroll_erg = bankroll_nanoerg / 1e9
        min_nano = self.config.min_erg * 1e9

        logger.debug("Auto-reload check: bankroll=%.4f ERG, threshold=%.1f ERG",
                      bankroll_erg, self.config.min_erg)

        if bankroll_nanoerg >= min_nano:
            return  # Above threshold, nothing to do

        # Check cooldown
        now = time.time()
        if now - self._last_reload_time < self.config.cooldown_sec:
            elapsed = now - self._last_reload_time
            remaining = self.config.cooldown_sec - elapsed
            logger.info(
                "Auto-reload cooldown active: %.0fs remaining (bankroll=%.4f ERG)",
                remaining, bankroll_erg,
            )
            return

        # Calculate reload amount
        target_nano = self.config.target_erg * 1e9
        max_nano = self.config.max_erg_per_reload * 1e9
        reload_amount = min(target_nano - bankroll_nanoerg, max_nano)

        if reload_amount <= 0:
            return

        reload_erg = reload_amount / 1e9
        logger.warning(
            "Auto-reload triggered! Bankroll=%.4f ERG < threshold=%.1f ERG. "
            "Attempting reload of %.4f ERG",
            bankroll_erg, self.config.min_erg, reload_erg,
        )

        # Execute reload
        event = await self._execute_reload(bankroll_erg, reload_erg)
        self._history.append(event)
        self._last_reload_time = now

    async def _get_current_bankroll(self, pool_manager=None) -> Optional[int]:
        """Get current bankroll in nanoERG."""
        # Try custom function first
        if self._get_bankroll_fn is not None:
            try:
                return await self._get_bankroll_fn()
            except Exception as e:
                logger.debug("Custom bankroll function failed: %s", e)

        # Fallback to pool manager
        if pool_manager is not None:
            try:
                state = await pool_manager.get_pool_state(force_refresh=True)
                return int(state.bankroll)
            except Exception as e:
                logger.warning("Failed to get pool state: %s", e)

        return None

    async def _execute_reload(self, current_erg: float, target_amount_erg: float) -> ReloadEvent:
        """Execute the reload (or dry-run if no reserve wallet configured)."""
        timestamp = datetime.now(timezone.utc).isoformat()

        if not self.config.reserve_wallet_address:
            # Dry run - no reserve wallet configured
            event = ReloadEvent(
                timestamp=timestamp,
                triggered_by_balance_erg=current_erg,
                target_amount_erg=target_amount_erg,
                actual_amount_erg=0.0,
                status="dry_run",
                error="No reserve wallet configured. Set RESERVE_WALLET_ADDRESS in .env",
            )
            logger.warning(
                "Auto-reload DRY RUN: no reserve wallet configured. "
                "Bankroll is %.4f ERG, needed %.4f ERG reload.",
                current_erg, target_amount_erg,
            )
            return event

        # Real reload - send ERG from reserve wallet via node
        try:
            import httpx
            import os

            node_url = os.getenv("NODE_URL", "http://localhost:9052")
            api_key = os.getenv("API_KEY", "hello")

            amount_nano = int(target_amount_erg * 1e9)

            # Send ERG to the pool/house address
            # Note: the house address and pool NFT need to be configured
            house_addr = os.getenv("HOUSE_ADDRESS", "")

            if not house_addr:
                event = ReloadEvent(
                    timestamp=timestamp,
                    triggered_by_balance_erg=current_erg,
                    target_amount_erg=target_amount_erg,
                    actual_amount_erg=0.0,
                    status="failed",
                    error="HOUSE_ADDRESS not configured",
                )
                return event

            # Build payment request
            requests = [{
                "address": house_addr,
                "value": amount_nano,
                "assets": [],
            }]

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{node_url}/wallet/transaction/send",
                    headers={"api_key": api_key, "Content-Type": "application/json"},
                    json={"requests": requests},
                )
                resp.raise_for_status()
                result = resp.json()

            tx_id = result.get("id", "unknown")

            event = ReloadEvent(
                timestamp=timestamp,
                triggered_by_balance_erg=current_erg,
                target_amount_erg=target_amount_erg,
                actual_amount_erg=target_amount_erg,
                status="success",
                tx_id=tx_id,
            )
            logger.info(
                "Auto-reload SUCCESS: sent %.4f ERG, tx=%s",
                target_amount_erg, tx_id,
            )
            return event

        except Exception as e:
            event = ReloadEvent(
                timestamp=timestamp,
                triggered_by_balance_erg=current_erg,
                target_amount_erg=target_amount_erg,
                actual_amount_erg=0.0,
                status="failed",
                error=str(e),
            )
            logger.error("Auto-reload FAILED: %s", e, exc_info=True)
            return event
