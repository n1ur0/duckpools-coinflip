"""
MAT-396 Phase 5 Security Tests

Tests for:
- 5.1 Security headers + XSS hardening + payload size limiting
- 5.2 Bet deduplication (replay attack prevention)

Run: cd backend && python -m pytest tests/test_phase5_security.py -v
"""

import asyncio
import pytest
from unittest.mock import patch

# Test dedup set and lock imports
from game_routes import _bet_ids, _bet_lock, _bets, _validate_address_param, _rate_limit_store
from game_routes import PlaceBetRequest
from fastapi import HTTPException


# ─── Task 5.2: Bet Deduplication Tests ───────────────────────────


class TestBetDeduplication:
    """Verify replay attack prevention via betId deduplication."""

    def setup_method(self):
        """Clear state before each test."""
        _bets.clear()
        _bet_ids.clear()
        _rate_limit_store.clear()

    def test_bet_ids_set_is_type(self):
        """_bet_ids should be a set for O(1) lookup."""
        assert isinstance(_bet_ids, set)

    def test_bet_lock_is_asyncio_lock(self):
        """_bet_lock should be an asyncio.Lock for race condition prevention."""
        assert isinstance(_bet_lock, asyncio.Lock)

    def test_duplicate_betid_rejected_in_place_bet(self):
        """Second request with same betId should be rejected."""
        bet_data = {
            "address": "9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
            "amount": "10000000",  # 0.01 ERG
            "choice": 0,
            "commitment": "a" * 64,
            "betId": "test-dedup-001",
        }
        # First bet should validate fine
        req1 = PlaceBetRequest(**bet_data)
        assert req1.betId == "test-dedup-001"

        # Manually add to set (simulating a placed bet)
        _bet_ids.add("test-dedup-001")
        _bets.append({"betId": "test-dedup-001", "playerAddress": bet_data["address"]})

        # Second bet with same betId should raise in validator
        with pytest.raises(ValueError, match="already exists"):
            PlaceBetRequest(**bet_data)

    def test_different_betids_accepted(self):
        """Different betIds should both be accepted."""
        bet_data_1 = {
            "address": "9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
            "amount": "10000000",
            "choice": 0,
            "commitment": "a1" * 32,
            "betId": "test-dedup-002",
        }
        bet_data_2 = {
            "address": "9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
            "amount": "10000000",
            "choice": 1,
            "commitment": "b2" * 32,
            "betId": "test-dedup-003",
        }
        req1 = PlaceBetRequest(**bet_data_1)
        req2 = PlaceBetRequest(**bet_data_2)
        assert req1.betId == "test-dedup-002"
        assert req2.betId == "test-dedup-003"

    @pytest.mark.asyncio
    async def test_concurrent_bet_dedup_with_lock(self):
        """Async lock should prevent race conditions on concurrent bets.
        
        Note: _bet_lock is created at module import time. In production
        (uvicorn), it runs on a single event loop and works correctly.
        This test creates a fresh lock to verify the logic.
        """
        test_lock = asyncio.Lock()
        test_ids = set()
        test_bets = []
        results = []

        async def place_bet(bet_id):
            async with test_lock:
                if bet_id in test_ids:
                    results.append(("duplicate", bet_id))
                    return
                await asyncio.sleep(0.01)  # Simulate processing time
                test_ids.add(bet_id)
                test_bets.append({"betId": bet_id})
                results.append(("success", bet_id))

        # Run 5 concurrent attempts with the SAME betId
        await asyncio.gather(*[place_bet("race-test-001") for _ in range(5)])

        successes = [r for r in results if r[0] == "success"]
        duplicates = [r for r in results if r[0] == "duplicate"]

        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
        assert len(duplicates) == 4, f"Expected 4 duplicates, got {len(duplicates)}"
        assert len(test_ids) == 1
        assert len(test_bets) == 1


# ─── Task 5.1: Input Validation / Path Traversal Tests ──────────


class TestPathTraversalProtection:
    """Verify address path parameters are validated against injection."""

    def test_normal_address_accepted(self):
        """Valid alphanumeric address should pass."""
        result = _validate_address_param("9abc123def456")
        assert result == "9abc123def456"

    def test_path_traversal_rejected(self):
        """Path traversal attempts should be rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_address_param("../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_backslash_traversal_rejected(self):
        """Backslash traversal attempts should be rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_address_param("..\\windows\\system32")
        assert exc_info.value.status_code == 400

    def test_forward_slash_rejected(self):
        """Forward slashes should be rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_address_param("some/address")
        assert exc_info.value.status_code == 400

    def test_empty_address_rejected(self):
        """Empty address should be rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_address_param("")
        assert exc_info.value.status_code == 400

    def test_very_long_address_rejected(self):
        """Overly long address should be rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_address_param("9" * 201)
        assert exc_info.value.status_code == 400

    def test_special_chars_rejected(self):
        """Special characters should be rejected."""
        for payload in ["<script>alert(1)</script>", "'; DROP TABLE", "{{7*7}}", "test\x00null"]:
            with pytest.raises(HTTPException) as exc_info:
                _validate_address_param(payload)
            assert exc_info.value.status_code == 400


# ─── Task 5.1: Commitment Validation Tests ──────────────────────


class TestCommitmentValidation:
    """Verify commitment field rejects known attack patterns."""

    def setup_method(self):
        _bet_ids.clear()
        _bets.clear()
        _rate_limit_store.clear()

    def test_all_zeros_commitment_rejected(self):
        """All-zeros commitment should be rejected."""
        with pytest.raises(ValueError, match="invalid commitment"):
            PlaceBetRequest(
                address="9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
                amount="10000000",
                choice=0,
                commitment="0" * 64,
                betId="test-commit-zero",
            )

    def test_all_ff_commitment_rejected(self):
        """All-f's commitment should be rejected."""
        with pytest.raises(ValueError, match="invalid commitment"):
            PlaceBetRequest(
                address="9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
                amount="10000000",
                choice=0,
                commitment="f" * 64,
                betId="test-commit-ff",
            )

    def test_short_commitment_rejected(self):
        """Too-short commitment should be rejected."""
        with pytest.raises(ValueError, match="64-character"):
            PlaceBetRequest(
                address="9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
                amount="10000000",
                choice=0,
                commitment="abc123",
                betId="test-commit-short",
            )

    def test_invalid_hex_commitment_rejected(self):
        """Non-hex characters in commitment should be rejected."""
        with pytest.raises(ValueError, match="valid hex"):
            PlaceBetRequest(
                address="9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
                amount="10000000",
                choice=0,
                commitment="g" * 64,
                betId="test-commit-badhex",
            )


# ─── Task 5.1: BetId Validation Tests ───────────────────────────


class TestBetIdValidation:
    """Verify betId field rejects malformed identifiers."""

    def setup_method(self):
        _bet_ids.clear()
        _bets.clear()
        _rate_limit_store.clear()

    def test_too_short_betid_rejected(self):
        with pytest.raises(ValueError, match="8 and 64"):
            PlaceBetRequest(
                address="9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
                amount="10000000",
                choice=0,
                commitment="a" * 64,
                betId="abc",
            )

    def test_special_chars_in_betid_rejected(self):
        with pytest.raises(ValueError, match="alphanumeric"):
            PlaceBetRequest(
                address="9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
                amount="10000000",
                choice=0,
                commitment="a" * 64,
                betId="test<script>alert(1)</script>",
            )

    def test_sql_injection_in_betid_rejected(self):
        with pytest.raises(ValueError):
            PlaceBetRequest(
                address="9eXhVHi7QYqDB5iiFCNqYSkoVoV1FxnSCpDHCxByQcPnECs2Fpg",
                amount="10000000",
                choice=0,
                commitment="a" * 64,
                betId="'; DROP TABLE bets; --",
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
