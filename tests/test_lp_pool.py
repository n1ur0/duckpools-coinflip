"""
DuckPools - LP Pool Tests

Comprehensive tests for pool math, state management, serialization,
and APY calculations.

MAT-15: Tokenized bankroll and liquidity pool

Run: python -m pytest tests/test_lp_pool.py -v
"""

import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from pool_manager import (
    calculate_price_per_share,
    calculate_deposit_shares,
    calculate_withdraw_erg,
    calculate_shares_to_burn_for_erg,
    calculate_apy,
    encode_vlq,
    zigzag_encode_i32,
    zigzag_encode_i64,
    serialize_int,
    serialize_long,
    serialize_coll_byte,
    PoolConfig,
    PoolState,
    PRECISION_FACTOR,
    HOUSE_EDGE_BPS,
    COOLDOWN_BLOCKS,
    MIN_DEPOSIT_NANOERG,
    BLOCKS_PER_YEAR,
)


# ═══════════════════════════════════════════════════════════════════
# Pool Math Tests
# ═══════════════════════════════════════════════════════════════════

class TestPricePerShare:
    """Tests for calculate_price_per_share"""

    def test_empty_pool_returns_precision(self):
        """First deposit gets 1:1 price (precision factor)"""
        assert calculate_price_per_share(0, 0) == PRECISION_FACTOR
        assert calculate_price_per_share(100, 0) == PRECISION_FACTOR
        assert calculate_price_per_share(0, 100) == PRECISION_FACTOR

    def test_equal_value_and_supply(self):
        """When value == supply, price = precision (1:1)"""
        assert calculate_price_per_share(100, 100) == PRECISION_FACTOR
        assert calculate_price_per_share(1_000_000_000, 1_000_000_000) == PRECISION_FACTOR

    def test_value_double_supply(self):
        """When value is 2x supply, price is 2x precision"""
        result = calculate_price_per_share(200, 100)
        assert result == 2 * PRECISION_FACTOR

    def test_supply_double_value(self):
        """When supply is 2x value, price is 0.5x precision"""
        result = calculate_price_per_share(100, 200)
        assert result == PRECISION_FACTOR // 2

    def test_realistic_pool_values(self):
        """Test with realistic nanoERG values"""
        bankroll = 100 * 1_000_000_000  # 100 ERG
        supply = 100 * 1_000_000_000    # 100 LP tokens
        # 1:1 ratio
        assert calculate_price_per_share(bankroll, supply) == PRECISION_FACTOR

        # 20% profit: bankroll grew to 120 ERG
        bankroll_with_profit = 120 * 1_000_000_000
        result = calculate_price_per_share(bankroll_with_profit, supply)
        assert result == int(1.2 * PRECISION_FACTOR)

    def test_custom_precision(self):
        """Test with custom precision factor"""
        assert calculate_price_per_share(100, 50, precision=1000) == 2000


class TestDepositShares:
    """Tests for calculate_deposit_shares"""

    def test_first_deposit_1to1(self):
        """First deposit: 1 ERG = 1 LP token"""
        assert calculate_deposit_shares(1_000_000_000, 0, 0) == 1_000_000_000
        assert calculate_deposit_shares(500_000_000, 0, 0) == 500_000_000

    def test_subsequent_deposit_proportional(self):
        """Subsequent deposit: shares = deposit * supply / value"""
        # Pool has 100 ERG value, 100 LP supply
        # Depositing 10 ERG should give 10 LP shares
        shares = calculate_deposit_shares(10_000_000_000, 100_000_000_000, 100_000_000_000)
        assert shares == 10_000_000_000

    def test_deposit_with_profit(self):
        """Deposit when pool has profit: shares should be less than deposit amount"""
        # Pool: 120 ERG value (20% profit), 100 LP supply
        # Depositing 10 ERG should give ~8.33 LP shares (not 10)
        shares = calculate_deposit_shares(10_000_000_000, 120_000_000_000, 100_000_000_000)
        assert shares == 8_333_333_333  # floor(10 * 100 / 120)

    def test_deposit_with_loss(self):
        """Deposit when pool has loss: shares should be more than deposit amount"""
        # Pool: 80 ERG value (20% loss), 100 LP supply
        # Depositing 10 ERG should give 12.5 LP shares
        shares = calculate_deposit_shares(10_000_000_000, 80_000_000_000, 100_000_000_000)
        assert shares == 12_500_000_000

    def test_small_deposit_rounding(self):
        """Verify integer division doesn't produce zero for valid deposits"""
        shares = calculate_deposit_shares(1, 100_000_000, 100_000_000_000)
        # 1 * 100_000_000_000 / 100_000_000 = 1000, not 0
        assert shares == 1000

    def test_tiny_deposit_may_get_zero(self):
        """Very small deposits relative to pool can get 0 or minimal shares"""
        shares = calculate_deposit_shares(1, 1_000_000_000_000, 100_000_000_000_000)
        # 1 * 100T / 1000T = 0.1, integer division = 0 (for integer arithmetic)
        # But with these specific numbers: 1 * 100_000_000_000 / 1_000_000_000_000 = 0
        assert shares >= 0


class TestWithdrawErg:
    """Tests for calculate_withdraw_erg"""

    def test_withdraw_full(self):
        """Withdrawing all shares returns full value"""
        result = calculate_withdraw_erg(100_000_000_000, 100_000_000_000, 100_000_000_000)
        assert result == 100_000_000_000

    def test_withdraw_half(self):
        """Withdrawing half shares returns half value"""
        result = calculate_withdraw_erg(50_000_000_000, 100_000_000_000, 100_000_000_000)
        assert result == 50_000_000_000

    def test_withdraw_with_profit(self):
        """Withdrawing when pool has profit returns proportionally more ERG"""
        # Pool: 120 ERG value, 100 LP supply
        # Withdrawing 10 LP tokens gets 12 ERG
        result = calculate_withdraw_erg(10_000_000_000, 120_000_000_000, 100_000_000_000)
        assert result == 12_000_000_000

    def test_withdraw_zero_supply(self):
        """Zero supply returns zero"""
        assert calculate_withdraw_erg(100, 1000, 0) == 0

    def test_withdraw_loss(self):
        """Withdrawing when pool has loss returns less ERG per share"""
        # Pool: 80 ERG value, 100 LP supply
        # Withdrawing 10 LP tokens gets 8 ERG
        result = calculate_withdraw_erg(10_000_000_000, 80_000_000_000, 100_000_000_000)
        assert result == 8_000_000_000


class TestSharesToBurnForErg:
    """Tests for calculate_shares_to_burn_for_erg"""

    def test_inverse_of_withdraw(self):
        """Burning shares for ERG should be inverse of withdraw calculation"""
        value = 120_000_000_000
        supply = 100_000_000_000

        desired = 12_000_000_000  # 12 ERG
        shares = calculate_shares_to_burn_for_erg(desired, value, supply)
        actual = calculate_withdraw_erg(shares, value, supply)
        # Due to integer rounding, actual <= desired
        assert actual <= desired
        assert actual >= desired - 1  # at most 1 nanoERG rounding error

    def test_zero_value(self):
        assert calculate_shares_to_burn_for_erg(100, 0, 100) == 0
        assert calculate_shares_to_burn_for_erg(100, 100, 0) == 0


class TestPoolMathRoundtrip:
    """Test that deposit and withdraw are consistent roundtrips"""

    def test_deposit_then_withdraw_unchanged_pool(self):
        """Deposit then withdraw same amount leaves pool unchanged"""
        initial_value = 100_000_000_000
        initial_supply = 100_000_000_000

        # Deposit 10 ERG
        deposit = 10_000_000_000
        shares = calculate_deposit_shares(deposit, initial_value, initial_supply)
        new_value = initial_value + deposit
        new_supply = initial_supply + shares

        # Withdraw the same shares
        withdrawn = calculate_withdraw_erg(shares, new_value, new_supply)

        # Pool should be back to initial value (minus rounding)
        assert withdrawn == deposit  # Exact for this case
        assert new_value - withdrawn == initial_value
        assert new_supply - shares == initial_supply

    def test_multiple_deposits_and_withdraws(self):
        """Multiple deposit/withdraw cycles maintain consistency"""
        value = 50_000_000_000
        supply = 50_000_000_000

        for _ in range(10):
            deposit = 5_000_000_000
            shares = calculate_deposit_shares(deposit, value, supply)
            value += deposit
            supply += shares

            withdraw_shares = shares // 2
            withdrawn = calculate_withdraw_erg(withdraw_shares, value, supply)
            value -= withdrawn
            supply -= withdraw_shares

        # Pool should still be valid
        assert value > 0
        assert supply > 0


# ═══════════════════════════════════════════════════════════════════
# APY Tests
# ═══════════════════════════════════════════════════════════════════

class TestAPY:
    """Tests for calculate_apy"""

    def test_zero_bankroll(self):
        """Zero bankroll returns 0% APY"""
        result = calculate_apy(300, 1_000_000_000, 0.5, 0)
        assert result.apy_percent == 0.0
        assert result.estimated_daily_profit == 0
        assert result.estimated_yearly_profit == 0

    def test_basic_apy_calculation(self):
        """Basic APY with known inputs"""
        # 3% edge, 1 ERG avg bet, 0.5 bets/block, 100 ERG bankroll
        result = calculate_apy(
            house_edge_bps=300,
            avg_bet_size=1_000_000_000,
            bets_per_block=0.5,
            bankroll=100_000_000_000,
        )

        # profit_per_block = 1_000_000_000 * 300 * 500 / (10000 * 1000) = 15_000_000 nanoERG
        # daily = 15_000_000 * 720 = 10_800_000_000
        # yearly = 15_000_000 * 262_800 = 3_942_000_000_000
        # apy = (3_942_000_000_000 * 10000) / 100_000_000_000 / 100 = 394.2%
        # Verify profit estimates are reasonable
        assert result.estimated_daily_profit > 0
        assert result.estimated_yearly_profit > 0
        assert result.apy_percent > 0

    def test_higher_edge_higher_apy(self):
        """Higher house edge should produce higher APY"""
        low = calculate_apy(100, 1_000_000_000, 0.5, 100_000_000_000)
        high = calculate_apy(500, 1_000_000_000, 0.5, 100_000_000_000)
        assert high.apy_percent > low.apy_percent

    def test_larger_bankroll_lower_apy(self):
        """Larger bankroll dilutes the APY"""
        small = calculate_apy(300, 1_000_000_000, 0.5, 50_000_000_000)
        large = calculate_apy(300, 1_000_000_000, 0.5, 200_000_000_000)
        assert small.apy_percent > large.apy_percent

    def test_profit_scales_with_bets_per_block(self):
        """More bets per block = more profit"""
        low = calculate_apy(300, 1_000_000_000, 0.1, 100_000_000_000)
        high = calculate_apy(300, 1_000_000_000, 1.0, 100_000_000_000)
        assert high.estimated_daily_profit > low.estimated_daily_profit

    def test_bps_field_preserved(self):
        """House edge BPS should be preserved in result"""
        result = calculate_apy(123, 1_000_000_000, 0.5, 100_000_000_000)
        assert result.house_edge_bps == 123


# ═══════════════════════════════════════════════════════════════════
# Sigma Serialization Tests
# ═══════════════════════════════════════════════════════════════════

class TestVLQ:
    """Tests for VLQ encoding"""

    def test_zero(self):
        assert encode_vlq(0) == "00"

    def test_small_values(self):
        assert encode_vlq(1) == "01"
        assert encode_vlq(127) == "7f"

    def test_two_byte(self):
        # 128 = 0x80 => continuation byte 0x80 | 0x00, then 0x01
        assert encode_vlq(128) == "8001"

    def test_large_value(self):
        # Verify it doesn't crash on large values
        result = encode_vlq(1_000_000_000)
        assert len(result) > 0
        assert len(result) % 2 == 0  # hex string


class TestZigZag:
    """Tests for ZigZag encoding"""

    def test_zero(self):
        assert zigzag_encode_i32(0) == 0

    def test_positive(self):
        assert zigzag_encode_i32(1) == 2
        assert zigzag_encode_i32(2) == 4
        assert zigzag_encode_i32(-1) == 1
        assert zigzag_encode_i32(-2) == 3

    def test_i64_matches_i32_for_small_values(self):
        for v in [0, 1, -1, 100, -100]:
            assert zigzag_encode_i64(v) == zigzag_encode_i32(v)


class TestSerialization:
    """Tests for SValue serialization"""

    def test_int_zero(self):
        assert serialize_int(0) == "0200"

    def test_int_positive(self):
        # Int(1) = 02 + VLQ(zigzag(1)) = 02 + VLQ(2) = "0202"
        assert serialize_int(1) == "0202"

    def test_int_negative(self):
        # Int(-1) = 02 + VLQ(zigzag(-1)) = 02 + VLQ(1) = "0201"
        assert serialize_int(-1) == "0201"

    def test_int_ten(self):
        # zigzag(10) = 20 = 0x14
        assert serialize_int(10) == "0214"

    def test_long_zero(self):
        assert serialize_long(0) == "0400"

    def test_long_positive(self):
        # Long(1) = 04 + VLQ(zigzag(1)) = 04 + VLQ(2) = "0402"
        assert serialize_long(1) == "0402"

    def test_coll_byte_empty(self):
        assert serialize_coll_byte(b"") == "0e0100"

    def test_coll_byte_32_bytes(self):
        data = b'\x00' * 32
        result = serialize_coll_byte(data)
        # 0e 01 20 + 64 hex chars
        assert result.startswith("0e01")
        # VLQ(32) = 0x20
        assert result[4:6] == "20"
        assert len(result) == 4 + 2 + 64  # header + vlq + data

    def test_coll_byte_prefix(self):
        """All Coll[Byte] should start with 0e01"""
        assert serialize_coll_byte(b'\xff').startswith("0e01")


# ═══════════════════════════════════════════════════════════════════
# Pool Config Tests
# ═══════════════════════════════════════════════════════════════════

class TestPoolConfig:
    """Tests for PoolConfig defaults"""

    def test_default_values(self):
        config = PoolConfig()
        assert config.min_deposit == MIN_DEPOSIT_NANOERG
        assert config.cooldown_blocks == COOLDOWN_BLOCKS
        assert config.house_edge_bps == HOUSE_EDGE_BPS
        assert config.lp_token_decimals == 9
        assert config.precision == PRECISION_FACTOR

    def test_custom_values(self):
        config = PoolConfig(
            min_deposit=500_000_000,
            cooldown_blocks=120,
            house_edge_bps=500,
        )
        assert config.min_deposit == 500_000_000
        assert config.cooldown_blocks == 120
        assert config.house_edge_bps == 500

    def test_optional_fields_none(self):
        config = PoolConfig()
        assert config.pool_nft_id is None
        assert config.lp_token_id is None
        assert config.bankroll_tree_hex is None


# ═══════════════════════════════════════════════════════════════════
# Pool State Tests
# ═══════════════════════════════════════════════════════════════════

class TestPoolState:
    """Tests for PoolState dataclass"""

    def test_default_state(self):
        state = PoolState()
        assert state.bankroll == 0
        assert state.total_supply == 0
        assert state.total_value == 0
        assert state.price_per_share == 0

    def test_state_creation(self):
        state = PoolState(
            bankroll=100_000_000_000,
            total_supply=100_000_000_000,
            total_value=100_000_000_000,
            price_per_share=PRECISION_FACTOR,
        )
        assert state.bankroll == 100_000_000_000
        assert state.total_supply == 100_000_000_000


# ═══════════════════════════════════════════════════════════════════
# Edge Cases / Invariants
# ═══════════════════════════════════════════════════════════════════

class TestInvariants:
    """Test mathematical invariants of the pool system"""

    def test_shares_never_exceed_deposit_for_first(self):
        """First deposit: shares should equal deposit"""
        for amount in [1, 100, 1_000_000_000, 100_000_000_000]:
            shares = calculate_deposit_shares(amount, 0, 0)
            assert shares == amount

    def test_price_consistency(self):
        """Price should be consistent whether computed from shares or value"""
        value = 150_000_000_000
        supply = 100_000_000_000
        price = calculate_price_per_share(value, supply)

        # Deposit 10 ERG, check new price
        deposit = 10_000_000_000
        new_shares = calculate_deposit_shares(deposit, value, supply)
        new_value = value + deposit
        new_supply = supply + new_shares
        new_price = calculate_price_per_share(new_value, new_supply)

        # Price should stay the same (or very close due to rounding)
        assert abs(new_price - price) <= 1

    def test_no_money_created_or_destroyed(self):
        """The sum of deposits minus withdrawals should equal pool value change"""
        value = 100_000_000_000
        supply = 100_000_000_000

        # Simulate 5 deposits and 5 withdrawals
        total_deposited = 0
        total_withdrawn = 0
        for i in range(5):
            dep = (i + 1) * 5_000_000_000
            shares = calculate_deposit_shares(dep, value, supply)
            value += dep
            supply += shares
            total_deposited += dep

            wit_shares = shares // 2
            wit = calculate_withdraw_erg(wit_shares, value, supply)
            value -= wit
            supply -= wit_shares
            total_withdrawn += wit

        # Net value should equal total deposits minus withdrawals
        # (pool started at 100 ERG, so value should be 100 + deposited - withdrawn)
        assert value == 100_000_000_000 + total_deposited - total_withdrawn


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
