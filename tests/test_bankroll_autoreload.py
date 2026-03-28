#!/usr/bin/env python3
"""
Integration tests for DuckPools Bankroll Auto-Reload (bankroll_autoreload.py)

Tests threshold detection, reload amount calculation, cooldown period,
config management, and dry-run behavior.

MAT-242: [MAT-12] Write integration tests for bankroll management system
Author: QA Developer Sr (Matsuzaka)
"""

import asyncio
import sys
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from services.bankroll_autoreload import (
    AutoReloadConfig,
    ReloadEvent,
    BankrollAutoReload,
)


# ═══════════════════════════════════════════════════════════════
# AutoReloadConfig
# ═══════════════════════════════════════════════════════════════

class TestAutoReloadConfig:
    """Test configuration dataclass."""

    def test_default_values(self):
        c = AutoReloadConfig()
        assert c.enabled is True
        assert c.min_erg == 10.0
        assert c.target_erg == 100.0
        assert c.check_interval_sec == 60
        assert c.max_erg_per_reload == 100.0
        assert c.cooldown_sec == 600
        assert c.reserve_wallet_address == ""

    def test_custom_config(self):
        c = AutoReloadConfig(
            enabled=False,
            min_erg=5.0,
            target_erg=50.0,
            cooldown_sec=300,
        )
        assert c.enabled is False
        assert c.min_erg == 5.0
        assert c.target_erg == 50.0
        assert c.cooldown_sec == 300


# ═══════════════════════════════════════════════════════════════
# ReloadEvent
# ═══════════════════════════════════════════════════════════════

class TestReloadEvent:
    """Test reload event record."""

    def test_dry_run_event(self):
        e = ReloadEvent(
            timestamp="2026-03-27T23:00:00Z",
            triggered_by_balance_erg=5.0,
            target_amount_erg=95.0,
            actual_amount_erg=0.0,
            status="dry_run",
            error="No reserve wallet configured",
        )
        assert e.status == "dry_run"
        assert e.actual_amount_erg == 0.0
        assert e.tx_id is None


# ═══════════════════════════════════════════════════════════════
# BankrollAutoReload - Core Logic
# ═══════════════════════════════════════════════════════════════

class TestBankrollAutoReload:
    """Test the auto-reload manager."""

    @pytest.fixture
    def config(self):
        return AutoReloadConfig(
            enabled=True,
            min_erg=10.0,
            target_erg=100.0,
            max_erg_per_reload=100.0,
            cooldown_sec=600,
        )

    @pytest.fixture
    def reload_manager(self, config):
        return BankrollAutoReload(config)

    def test_init_default_config(self):
        mgr = BankrollAutoReload()
        assert mgr.config.enabled is True
        assert mgr._history == []
        assert mgr._last_reload_time == 0.0
        assert mgr._running is False

    def test_init_custom_config(self, config):
        mgr = BankrollAutoReload(config)
        assert mgr.config.min_erg == 10.0

    def test_set_bankroll_fn(self, reload_manager):
        fn = AsyncMock(return_value=50e9)
        reload_manager.set_bankroll_fn(fn)
        assert reload_manager._get_bankroll_fn is fn

    def test_get_config_masks_sensitive(self, reload_manager):
        """Reserve wallet address should be masked."""
        mgr = BankrollAutoReload(AutoReloadConfig(
            reserve_wallet_address="3Wsecret..."
        ))
        cfg = mgr.get_config()
        assert "reserve_wallet_configured" in cfg
        assert cfg["reserve_wallet_configured"] is True
        assert "3Wsecret" not in str(cfg)

    def test_update_config_valid_fields(self, reload_manager):
        new_cfg = reload_manager.update_config(
            min_erg=5.0,
            cooldown_sec=300,
        )
        assert new_cfg.min_erg == 5.0
        assert new_cfg.cooldown_sec == 300
        # Unchanged fields preserved
        assert new_cfg.target_erg == 100.0

    def test_update_config_invalid_field_raises(self, reload_manager):
        with pytest.raises(ValueError, match="Unknown config field"):
            reload_manager.update_config(not_a_field=42)

    def test_stop(self, reload_manager):
        reload_manager._running = True
        reload_manager.stop()
        assert reload_manager._running is False

    def test_get_history_empty(self, reload_manager):
        history = reload_manager.get_history()
        assert history == []

    def test_get_history_limited(self, reload_manager):
        """History should respect limit parameter."""
        for i in range(10):
            reload_manager._history.append(ReloadEvent(
                timestamp=f"2026-03-27T23:0{i}:00Z",
                triggered_by_balance_erg=5.0,
                target_amount_erg=95.0,
                actual_amount_erg=0.0,
                status="dry_run",
            ))
        history = reload_manager.get_history(limit=3)
        assert len(history) == 3  # Returns last 3

    @pytest.mark.asyncio
    async def test_check_and_reload_disabled(self, reload_manager):
        """Disabled config → no reload triggered."""
        reload_manager.config.enabled = False
        reload_manager._get_bankroll_fn = AsyncMock(return_value=1e9)
        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 0

    @pytest.mark.asyncio
    async def test_check_and_reload_above_threshold(self, reload_manager):
        """Balance above threshold → no reload."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=50e9)  # 50 ERG
        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 0

    @pytest.mark.asyncio
    async def test_check_and_reload_triggers_dry_run(self, reload_manager):
        """Balance below threshold, no reserve wallet → dry_run event."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=5e9)  # 5 ERG < 10 ERG
        # Reset cooldown so it's not blocking
        reload_manager._last_reload_time = 0.0

        await reload_manager._check_and_reload()

        assert len(reload_manager._history) == 1
        event = reload_manager._history[0]
        assert event.status == "dry_run"
        assert event.triggered_by_balance_erg == 5.0
        assert event.actual_amount_erg == 0.0
        assert "No reserve wallet" in (event.error or "")

    @pytest.mark.asyncio
    async def test_reload_amount_calculation(self, reload_manager):
        """Reload amount = min(target - current, max_per_reload)."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=5e9)  # 5 ERG
        reload_manager._last_reload_time = 0.0

        await reload_manager._check_and_reload()

        event = reload_manager._history[0]
        # Expected: target=100, current=5, reload=95, max_per_reload=100
        # So reload = min(95, 100) = 95
        assert event.target_amount_erg == 95.0

    @pytest.mark.asyncio
    async def test_reload_amount_capped_by_max(self, config):
        """When target shortfall exceeds max_per_reload, cap it."""
        config.max_erg_per_reload = 20.0  # Only 20 ERG per reload
        config.target_erg = 100.0
        mgr = BankrollAutoReload(config)
        mgr._get_bankroll_fn = AsyncMock(return_value=5e9)  # 5 ERG
        mgr._last_reload_time = 0.0

        await mgr._check_and_reload()

        event = mgr._history[0]
        # Shortfall = 95 ERG, but max = 20 ERG → reload = 20
        assert event.target_amount_erg == 20.0

    @pytest.mark.asyncio
    async def test_cooldown_prevents_double_reload(self, reload_manager):
        """Second reload within cooldown period is skipped."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=5e9)
        reload_manager._last_reload_time = 0.0

        # First check: triggers reload
        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 1

        # Second check immediately: should be blocked by cooldown
        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 1  # No new event

    @pytest.mark.asyncio
    async def test_cooldown_expired_allows_reload(self, reload_manager):
        """After cooldown expires, reload is allowed again."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=5e9)
        reload_manager._last_reload_time = 0.0

        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 1

        # Simulate cooldown expiry
        reload_manager._last_reload_time = time.time() - 700  # 700s ago, cooldown=600s

        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 2

    @pytest.mark.asyncio
    async def test_bankroll_fn_fails_gracefully(self, reload_manager):
        """If bankroll function raises, should not crash."""
        reload_manager._get_bankroll_fn = AsyncMock(side_effect=Exception("Node down"))
        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 0

    @pytest.mark.asyncio
    async def test_bankroll_fn_returns_none(self, reload_manager):
        """If bankroll function returns None, skip check."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=None)
        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 0

    @pytest.mark.asyncio
    async def test_no_bankroll_fn_uses_pool_manager_fallback(self, config):
        """When no custom fn, falls back to pool_manager if provided."""
        mgr = BankrollAutoReload(config)
        # No custom fn set; mock pool_manager
        mock_pm = AsyncMock()
        mock_state = MagicMock()
        mock_state.bankroll = 5e9
        mock_pm.get_pool_state = AsyncMock(return_value=mock_state)

        mgr._last_reload_time = 0.0
        await mgr._check_and_reload(pool_manager=mock_pm)

        assert len(mgr._history) == 1

    @pytest.mark.asyncio
    async def test_balance_exactly_at_threshold(self, reload_manager):
        """Balance exactly at threshold should NOT trigger reload (>= check)."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=10e9)  # Exactly 10 ERG
        reload_manager._last_reload_time = 0.0

        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 0  # Not triggered

    @pytest.mark.asyncio
    async def test_balance_just_below_threshold(self, reload_manager):
        """Balance 0.000000001 ERG below threshold triggers reload."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=int(9.999999999 * 1e9))
        reload_manager._last_reload_time = 0.0

        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 1

    @pytest.mark.asyncio
    async def test_balance_zero_triggers_reload(self, reload_manager):
        """Zero balance should trigger reload."""
        reload_manager._get_bankroll_fn = AsyncMock(return_value=0)
        reload_manager._last_reload_time = 0.0

        await reload_manager._check_and_reload()
        assert len(reload_manager._history) == 1
        # Reload amount should be capped by max_per_reload
        assert reload_manager._history[0].target_amount_erg == 100.0

    @pytest.mark.asyncio
    async def test_target_equals_current_no_reload(self, config):
        """When bankroll already at or above target, reload amount is 0 → skip."""
        config.target_erg = 5.0
        mgr = BankrollAutoReload(config)
        mgr._get_bankroll_fn = AsyncMock(return_value=100e9)  # 100 ERG, way above
        mgr._last_reload_time = 0.0

        await mgr._check_and_reload()
        # Above threshold, so never gets to reload calculation
        assert len(mgr._history) == 0


# ═══════════════════════════════════════════════════════════════
# Background Task (run/stop)
# ═══════════════════════════════════════════════════════════════

class TestBackgroundTask:
    """Test the async run loop."""

    @pytest.mark.asyncio
    async def test_stop_halts_loop(self):
        """Calling stop() should halt the run loop."""
        config = AutoReloadConfig(check_interval_sec=0)  # Fast for testing
        mgr = BankrollAutoReload(config)
        mgr._get_bankroll_fn = AsyncMock(return_value=50e9)

        # Run in background
        task = asyncio.create_task(mgr.run())
        await asyncio.sleep(0.05)
        mgr.stop()
        await asyncio.sleep(0.05)

        assert mgr._running is False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_run_handles_exception_gracefully(self):
        """Exception in check shouldn't crash the loop."""
        config = AutoReloadConfig(check_interval_sec=0)
        mgr = BankrollAutoReload(config)
        mgr._get_bankroll_fn = AsyncMock(side_effect=Exception("test"))

        task = asyncio.create_task(mgr.run())
        await asyncio.sleep(0.05)
        mgr.stop()

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
