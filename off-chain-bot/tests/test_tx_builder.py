"""
Tests for off-chain bot transaction builder.

MAT-419: Implement off-chain bot reveal logic
"""

import pytest
from tx_builder import (
    compute_win_payout,
    compute_refund_amount,
    build_reveal_request,
    _pk_to_prop_bytes,
)


class TestComputeWinPayout:
    """Tests for compute_win_payout."""

    def test_exact_erg(self):
        """Test with exactly 1 ERG."""
        # 1 ERG = 1_000_000_000 nanoERG
        # Payout = 1_000_000_000 * 97 / 50 = 1_940_000_000
        assert compute_win_payout(1_000_000_000) == 1_940_000_000

    def test_small_bet(self):
        """Test with small bet."""
        # 0.01 ERG = 10_000_000 nanoERG
        # Payout = 10_000_000 * 97 / 50 = 19_400_000
        assert compute_win_payout(10_000_000) == 19_400_000

    def test_large_bet(self):
        """Test with 100 ERG bet."""
        result = compute_win_payout(100_000_000_000)
        assert result == 194_000_000_000  # 194 ERG

    def test_matches_1_94_multiplier(self):
        """Payout should be approximately 1.94x the bet."""
        bet = 50_000_000_000  # 50 ERG
        payout = compute_win_payout(bet)
        ratio = payout / bet
        assert abs(ratio - 1.94) < 0.01


class TestComputeRefundAmount:
    """Tests for compute_refund_amount."""

    def test_exact_erg(self):
        """Test with 1 ERG."""
        # Refund = 1_000_000_000 - 1_000_000_000/50 = 1_000_000_000 - 20_000_000 = 980_000_000
        assert compute_refund_amount(1_000_000_000) == 980_000_000

    def test_matches_0_98_multiplier(self):
        """Refund should be approximately 0.98x the bet."""
        bet = 50_000_000_000
        refund = compute_refund_amount(bet)
        ratio = refund / bet
        assert abs(ratio - 0.98) < 0.01

    def test_less_than_bet(self):
        """Refund should always be less than bet."""
        for bet in [1_000_000, 100_000_000_000, 1_000_000_000_000]:
            assert compute_refund_amount(bet) < bet


class TestBuildRevealRequest:
    """Tests for build_reveal_request."""

    def _make_bet_box(self, value=1_000_000_000):
        """Create a minimal PendingBetBox-like object."""
        class MockBox:
            pass
        box = MockBox()
        box.box_id = "a" * 64
        box.value = value
        box.player_choice = 0
        return box

    def test_player_wins_request(self):
        """Build request for player win."""
        box = self._make_bet_box(1_000_000_000)
        player_addr = "3player_address_hex"
        house_addr = "3house_address_hex"

        req = build_reveal_request(box, True, player_addr, house_addr)
        assert req is not None
        assert "requests" in req
        assert len(req["requests"]) == 1
        assert req["requests"][0]["address"] == player_addr
        # 1.94x payout
        assert req["requests"][0]["value"] == str(1_940_000_000)
        assert req["inputsRaw"] == [box.box_id]

    def test_house_wins_request(self):
        """Build request for house win."""
        box = self._make_bet_box(1_000_000_000)
        player_addr = "3player_address_hex"
        house_addr = "3house_address_hex"

        req = build_reveal_request(box, False, player_addr, house_addr)
        assert req is not None
        assert req["requests"][0]["address"] == house_addr
        # House gets full bet
        assert req["requests"][0]["value"] == str(1_000_000_000)

    def test_below_minimum_payout(self):
        """Bet too small for valid payout should return None."""
        box = self._make_bet_box(100)  # Way below minimum
        req = build_reveal_request(box, True, "3addr", "3addr")
        assert req is None


class TestPkToPropBytes:
    """Tests for _pk_to_prop_bytes."""

    def test_produces_hex_string(self):
        """Should return a hex string starting with 08 (proveDlog tag)."""
        pk = b"\x02" + b"\x00" * 32  # 33-byte compressed PK
        prop = _pk_to_prop_bytes(pk)
        assert prop.startswith("08")
        assert len(prop) == 2 + 66  # "08" + 33 bytes hex

    def test_length(self):
        """Output should be 68 hex chars (2 prefix + 33 bytes)."""
        pk = bytes(range(33))
        prop = _pk_to_prop_bytes(pk)
        assert len(prop) == 68
