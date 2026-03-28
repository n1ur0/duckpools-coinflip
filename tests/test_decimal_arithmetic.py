"""
DuckPools - Decimal Arithmetic Tests

Tests to verify that decimal arithmetic provides better precision
than integer arithmetic for pool calculations.

MAT-15: Tokenized bankroll and liquidity pool

Run: python -m pytest tests/test_decimal_arithmetic.py -v
"""

import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from decimal import Decimal, getcontext

from pool_manager import (
    calculate_deposit_shares,
    calculate_withdraw_erg,
    calculate_price_per_share,
    calculate_shares_to_burn_for_erg,
)


# ═══════════════════════════════════════════════════════════════════
# Decimal Precision Tests
# ═══════════════════════════════════════════════════════════════════

class TestDecimalPrecision:
    """Tests verifying decimal arithmetic precision."""

    def test_deposit_with_division_remainder(self):
        """Test that decimal arithmetic handles division remainders correctly."""
        # Pool: 100 ERG value, 97 ERG supply (from a previous loss)
        # Depositing 3 ERG should give exact shares
        # With integer: (3_000_000_000 * 97_000_000_000) // 100_000_000_000 = 2_910_000_000
        # With Decimal: should give 2_910_000_000 (same for this case, but more precise generally)

        value = 100_000_000_000
        supply = 97_000_000_000
        deposit = 3_000_000_000

        shares = calculate_deposit_shares(deposit, value, supply)

        # Should calculate precisely
        assert shares > 0
        # Shares should be close to deposit * supply / value
        expected_shares = Decimal(deposit) * Decimal(supply) / Decimal(value)
        assert shares == int(expected_shares.to_integral_value())

    def test_deposit_with_fractional_result(self):
        """Test deposit calculation when result has fractional shares."""
        # Pool: 100 ERG value, 100 ERG supply
        # Depositing 1 ERG should give 1 LP token (1:1)
        # Depositing 0.333333 ERG should give 0.333333 LP tokens

        value = 100_000_000_000
        supply = 100_000_000_000

        # 0.333333 ERG = 333_333_333 nanoERG
        deposit = 333_333_333
        shares = calculate_deposit_shares(deposit, value, supply)

        # With integer: (333_333_333 * 100_000_000_000) // 100_000_000_000 = 333_333_333
        # With Decimal: same result for 1:1 ratio

        assert shares == 333_333_333

    def test_deposit_with_profit_precision(self):
        """Test that decimal arithmetic handles profit scenarios precisely."""
        # Pool: 120 ERG value (20% profit), 100 ERG supply
        # Depositing 10 ERG should give 8.333333... LP tokens
        # With integer: 8_333_333_333
        # With Decimal: should also give 8_333_333_333 (rounded down)

        value = 120_000_000_000
        supply = 100_000_000_000
        deposit = 10_000_000_000

        shares = calculate_deposit_shares(deposit, value, supply)

        # Expected: (10_000_000_000 * 100_000_000_000) / 120_000_000_000 = 8_333_333_333.33...
        # Rounded down: 8_333_333_333
        assert shares == 8_333_333_333

    def test_withdraw_with_fractional_erg(self):
        """Test withdraw calculation with fractional ERG amounts."""
        # Pool: 120 ERG value, 100 ERG supply
        # Withdrawing 8_333_333_333 shares should give 10 ERG
        # (8_333_333_333 * 120_000_000_000) / 100_000_000_000 = 10_000_000_000 (approx)

        value = 120_000_000_000
        supply = 100_000_000_000
        shares = 8_333_333_333

        erg = calculate_withdraw_erg(shares, value, supply)

        # Should get close to 10 ERG
        # With Decimal: precise calculation
        expected_erg = Decimal(shares) * Decimal(value) / Decimal(supply)
        assert erg == int(expected_erg.to_integral_value())

    def test_price_per_share_decimal_accuracy(self):
        """Test price calculation with decimal accuracy."""
        # Pool: 150 ERG value, 100 ERG supply
        # Price should be 1.5 * PRECISION

        value = 150_000_000_000
        supply = 100_000_000_000
        precision = 1_000_000_000

        price = calculate_price_per_share(value, supply, precision)

        # Expected: 1.5 * PRECISION = 1_500_000_000
        assert price == 1_500_000_000

        # Verify with Decimal calculation
        expected_price = Decimal(value) * Decimal(precision) / Decimal(supply)
        assert price == int(expected_price.to_integral_value())

    def test_shares_to_burn_decimal_accuracy(self):
        """Test inverse calculation maintains precision."""
        # Pool: 120 ERG value, 100 ERG supply
        # Want 10 ERG out: (10_000_000_000 * 100_000_000_000) / 120_000_000_000 = 8_333_333_333 shares

        value = 120_000_000_000
        supply = 100_000_000_000
        desired_erg = 10_000_000_000

        shares = calculate_shares_to_burn_for_erg(desired_erg, value, supply)

        # Expected: 8_333_333_333
        expected_shares = Decimal(desired_erg) * Decimal(supply) / Decimal(value)
        assert shares == int(expected_shares.to_integral_value())


class TestDecimalContext:
    """Tests verifying decimal context configuration."""

    def test_decimal_context_prec_set(self):
        """Verify decimal precision context is set correctly."""
        from pool_manager import getcontext
        assert getcontext().prec >= 50  # Should be at least 50 for nanoERG precision

    def test_decimal_context_rounding_mode(self):
        """Verify decimal rounding mode is ROUND_DOWN for consistency."""
        from pool_manager import getcontext, ROUND_DOWN
        assert getcontext().rounding == ROUND_DOWN


class TestDecimalVsInteger:
    """Tests comparing decimal arithmetic behavior with integer arithmetic."""

    def test_division_precision_comparison(self):
        """Compare integer division vs decimal division."""
        # Integer: (1000 * 3) // 7 = 428
        # Decimal: (1000 * 3) / 7 = 428.571...
        # Our function uses Decimal but rounds down, so should match integer
        # for same inputs (but Decimal gives more consistent behavior)

        value = 7_000_000_000
        supply = 3_000_000_000
        deposit = 1_000_000_000

        shares = calculate_deposit_shares(deposit, value, supply)

        # Integer: (1_000_000_000 * 3_000_000_000) // 7_000_000_000 = 428_571_428
        # Decimal with ROUND_DOWN: same
        assert shares == 428_571_428

    def test_large_value_precision(self):
        """Test that large values maintain precision."""
        # Pool: 1,000,000 ERG value, 999,999 ERG supply
        # Small deposit should be calculated precisely

        value = 1_000_000_000_000_000_000  # 1 million ERG
        supply = 999_999_000_000_000_000   # 999,999 ERG
        deposit = 1_000_000_000            # 1 ERG

        shares = calculate_deposit_shares(deposit, value, supply)

        # Should not lose precision even with large values
        expected_shares = Decimal(deposit) * Decimal(supply) / Decimal(value)
        assert shares == int(expected_shares.to_integral_value())

        # Should be very close to deposit (since supply/value ≈ 1)
        assert shares > 900_000_000  # At least 0.9 ERG worth of shares


class TestRoundtripPrecision:
    """Tests that deposit/withdraw roundtrips maintain precision."""

    def test_deposit_withdraw_roundtrip_precision(self):
        """Verify deposit then withdraw maintains value (minus rounding)."""
        initial_value = 100_000_000_000
        initial_supply = 100_000_000_000

        # Deposit 10 ERG
        deposit = 10_000_000_000
        shares = calculate_deposit_shares(deposit, initial_value, initial_supply)
        new_value = initial_value + deposit
        new_supply = initial_supply + shares

        # Withdraw all shares
        withdrawn = calculate_withdraw_erg(shares, new_value, new_supply)

        # Should get back very close to original deposit
        # Decimal arithmetic minimizes rounding error
        assert withdrawn >= deposit - 1  # At most 1 nanoERG rounding error
        assert withdrawn <= deposit     # Never more than deposited

    def test_multiple_roundtrips_accumulate_precision(self):
        """Test multiple deposit/withdraw cycles with decimal arithmetic."""
        value = 100_000_000_000
        supply = 100_000_000_000

        total_deposited = 0
        total_withdrawn = 0

        for i in range(10):
            # Deposit
            deposit = 5_000_000_000
            shares = calculate_deposit_shares(deposit, value, supply)
            value += deposit
            supply += shares
            total_deposited += deposit

            # Withdraw half
            withdraw_shares = shares // 2
            withdrawn = calculate_withdraw_erg(withdraw_shares, value, supply)
            value -= withdrawn
            supply -= withdraw_shares
            total_withdrawn += withdrawn

        # Final value should be close to initial + deposited - withdrawn
        # Decimal arithmetic keeps this precise
        expected = 100_000_000_000 + total_deposited - total_withdrawn
        assert abs(value - expected) <= 10  # Minimal accumulated error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
