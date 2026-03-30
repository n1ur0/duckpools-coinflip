"""
MAT-230: Bankroll Monitoring API Tests

Tests for the bankroll monitoring endpoints in bankroll_routes.py.
Focus: on-chain exposure tracking via byErgoTree scan.

Run with: python3 -m pytest tests/test_bankroll_monitoring.py -v
"""

import hashlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_ERGO_TREE = "19d8010c04000200020104000404040005c20105640400040004000564d805d601cdeee4c6a7040ed602e4c6a7090ed603e4c6a70704d604cdeee4c6a7050ed605c1a7eb02ea02ea027201d193cbb3720283010295937203730073017302e4c6a7060ed195939e7eb2cbb3db6902db6503fe72027303000473047203d801d606b2a5730500ed93c27206d0720492c172069d9c720573067307d801d606b2a5730800ed93c27206d0720192c172067205ea02ea02ea02d192a3e4c6a708047204d193c2b2a5730900d07204d192c1b2a5730a009972059d7205730b"

SAMPLE_ERGO_TREE_HASH = hashlib.sha256(bytes.fromhex(SAMPLE_ERGO_TREE)).hexdigest()

SAMPLE_BOXES = [
    {"boxId": "box1", "value": "1000000000", "ergoTree": SAMPLE_ERGO_TREE},
    {"boxId": "box2", "value": "2500000000", "ergoTree": SAMPLE_ERGO_TREE},
    {"boxId": "box3", "value": "500000000", "ergoTree": SAMPLE_ERGO_TREE},
]


# ─── Tests: ergoTree hash computation ────────────────────────────────


class TestErgoTreeHash:
    def test_hash_computation(self):
        """Verify SHA256 hash of ergoTree bytes."""
        expected = hashlib.sha256(bytes.fromhex(SAMPLE_ERGO_TREE)).hexdigest()
        assert len(expected) == 64
        assert hashlib.sha256(bytes.fromhex(SAMPLE_ERGO_TREE)).hexdigest() == expected

    def test_different_trees_different_hashes(self):
        """Different ergoTrees must produce different hashes."""
        other_tree = "ff" * 50  # dummy
        assert hashlib.sha256(bytes.fromhex(SAMPLE_ERGO_TREE)).hexdigest() != \
               hashlib.sha256(bytes.fromhex(other_tree)).hexdigest()


# ─── Tests: on-chain exposure scanning ───────────────────────────────


class TestOnChainExposure:
    @pytest.mark.asyncio
    async def test_exposure_from_on_chain_boxes(self):
        """Sum ERG values from all unspent boxes matching the contract."""
        import bankroll_routes

        # Patch game_routes import and _query_node in bankroll_routes
        with patch.object(bankroll_routes, "_get_ergo_tree_hash", return_value=SAMPLE_ERGO_TREE_HASH), \
             patch.object(bankroll_routes, "_query_node", new_callable=AsyncMock, return_value=SAMPLE_BOXES):

            exposure, count = await bankroll_routes._get_pending_exposure()
            assert count == 3
            # 1_000_000_000 + 2_500_000_000 + 500_000_000 = 4_000_000_000
            assert exposure == 4_000_000_000

    @pytest.mark.asyncio
    async def test_exposure_empty_chain(self):
        """No unspent boxes should return (0, 0)."""
        import bankroll_routes

        with patch.object(bankroll_routes, "_get_ergo_tree_hash", return_value=SAMPLE_ERGO_TREE_HASH), \
             patch.object(bankroll_routes, "_query_node", new_callable=AsyncMock, return_value=[]):

            exposure, count = await bankroll_routes._get_pending_exposure()
            assert exposure == 0
            assert count == 0

    @pytest.mark.asyncio
    async def test_exposure_falls_back_to_memory(self):
        """If node query fails, falls back to in-memory store."""
        import bankroll_routes

        mock_bets = [
            {"betId": "bet1", "outcome": "pending", "betAmount": "1000000000"},
            {"betId": "bet2", "outcome": "win", "betAmount": "2000000000"},
            {"betId": "bet3", "outcome": "pending", "betAmount": "500000000"},
        ]

        with patch.object(bankroll_routes, "_get_ergo_tree_hash", return_value=SAMPLE_ERGO_TREE_HASH), \
             patch.object(bankroll_routes, "_query_node", new_callable=AsyncMock, side_effect=Exception("Node unavailable")), \
             patch("game_routes._bets", mock_bets):

            exposure, count = await bankroll_routes._get_pending_exposure()
            # Should fall back to in-memory: 2 pending bets
            assert count == 2
            # bet1 (1B) + bet3 (0.5B) = 1.5B
            assert exposure == 1_500_000_000

    @pytest.mark.asyncio
    async def test_exposure_no_ergo_tree_hash(self):
        """If ergoTree hash cannot be computed, returns (0, 0) via fallback."""
        import bankroll_routes

        with patch.object(bankroll_routes, "_get_ergo_tree_hash", return_value=""):
            exposure, count = await bankroll_routes._get_pending_exposure()
            assert count == 0
            assert exposure == 0


# ─── Tests: API endpoint integration ─────────────────────────────────


class TestBankrollStatusEndpoint:
    @pytest.mark.asyncio
    async def test_status_returns_balances(self):
        """GET /bankroll/status returns live balance and exposure."""
        import bankroll_routes

        node_responses = {
            "/wallet/balances": {"balance": 10000000000},
            "/info": {"fullHeight": 500000},
        }

        async def mock_query(endpoint, timeout=10):
            if "byErgoTree" in endpoint:
                return SAMPLE_BOXES
            return node_responses.get(endpoint, {})

        with patch.object(bankroll_routes, "_get_ergo_tree_hash", return_value=SAMPLE_ERGO_TREE_HASH), \
             patch.object(bankroll_routes, "_query_node", new_callable=AsyncMock, side_effect=mock_query), \
             patch.object(bankroll_routes, "_record_snapshot"):

            resp = await bankroll_routes.bankroll_status()

            assert resp.wallet_balance_nanoerg == 10_000_000_000
            assert resp.pending_exposure_nanoerg == 4_000_000_000
            # capacity = balance - exposure = 6B
            assert resp.available_capacity_nanoerg == 6_000_000_000
            # max_single_bet = 10% of capacity = 600M
            assert resp.max_single_bet_nanoerg == 600_000_000
            # utilization = 4B/10B = 40%
            assert resp.utilization_pct == 40.0
            assert resp.pending_bet_count == 3
            assert resp.node_height == 500000

    @pytest.mark.asyncio
    async def test_status_handles_node_down(self):
        """GET /bankroll/status gracefully handles node being down."""
        import bankroll_routes

        with patch.object(bankroll_routes, "_get_ergo_tree_hash", return_value=""), \
             patch.object(bankroll_routes, "_query_node", new_callable=AsyncMock, side_effect=Exception("Connection refused")), \
             patch("game_routes._bets", []), \
             patch.object(bankroll_routes, "_record_snapshot"):

            resp = await bankroll_routes.bankroll_status()

            assert resp.wallet_balance_nanoerg == 0
            assert resp.node_height == 0
            assert resp.pending_exposure_nanoerg == 0
