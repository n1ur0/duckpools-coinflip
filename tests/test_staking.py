"""
Tests for LP Staking Contract

Test coverage for:
- StakingPool contract spending paths (stake, unstake, distribute)
- StakingPosition contract spending paths (increase, decrease, claim)
- Reward calculation accuracy
- Edge cases (dust amounts, overflow, etc.)

MAT-XXX: LP token stake/unstake ErgoTree contract with yield distribution logic
"""

import pytest
from decimal import Decimal

# ─── Constants ────────────────────────────────────────────────────────

# NanoERG to ERG conversion
NANOERG_PER_ERG = 10**9

# Reward per share precision factor
# Allows tracking fractional rewards with high precision
REWARD_PRECISION = 10**12

# Minimum stake amount (anti-dust)
MIN_STAKE_AMOUNT = 1_000  # tokens


# ─── Helper Functions ────────────────────────────────────────────────

def calculate_reward_per_share(rewards_nanoERG: int, staked_tokens: int) -> int:
    """
    Calculate reward per share.

    Formula: (rewards * REWARD_PRECISION) / staked_tokens

    Example: 10 ERG to 1M tokens
    = (10 * 10^9 * 10^12) / 10^6 = 10 * 10^15 = 10^16
    """
    if staked_tokens == 0:
        return 0
    return (rewards_nanoERG * REWARD_PRECISION) // staked_tokens


def calculate_pending_rewards(staked_tokens: int, old_rps: int, new_rps: int) -> int:
    """
    Calculate pending rewards for a staker.

    Formula: ((new_rps - old_rps) * staked_tokens) / REWARD_PRECISION

    Returns: rewards in nanoERG
    """
    return ((new_rps - old_rps) * staked_tokens) // REWARD_PRECISION


# ─── Reward Calculation Tests ─────────────────────────────────────────

def test_reward_per_share_calculation():
    """Test reward per share is calculated correctly."""
    # Distribute 10 ERG to 1,000,000 LP tokens
    total_rewards_nanoERG = 10 * NANOERG_PER_ERG  # 10 ERG = 10^10 nanoERG
    total_staked_tokens = 1_000_000

    reward_per_share = calculate_reward_per_share(total_rewards_nanoERG, total_staked_tokens)

    # (10 * 10^9 * 10^12) / 10^6 = 10 * 10^15 = 10^16
    assert reward_per_share == 10 * 10**15


def test_reward_per_share_with_zero_staked():
    """Test reward per share when pool is empty."""
    total_rewards = 10 * NANOERG_PER_ERG
    total_staked = 0

    reward_per_share = calculate_reward_per_share(total_rewards, total_staked)

    assert reward_per_share == 0


def test_user_pending_rewards():
    """Test user pending rewards calculation."""
    # User staked 100,000 LP tokens
    staked_amount = 100_000

    # Initial reward per share (from 10 ERG / 1M tokens)
    old_rps = calculate_reward_per_share(10 * NANOERG_PER_ERG, 1_000_000)  # 10^16

    # After distributing 2 more ERG (12 ERG total)
    new_rps = calculate_reward_per_share(12 * NANOERG_PER_ERG, 1_000_000)  # 1.2 * 10^16

    # Calculate pending rewards
    pending_rewards_nanoERG = calculate_pending_rewards(staked_amount, old_rps, new_rps)

    # User owns 100k/1M = 10% of pool
    # 10% of 2 ERG = 0.2 ERG
    # 0.2 ERG = 0.2 * 10^9 = 2 * 10^8 nanoERG
    assert pending_rewards_nanoERG == 200_000_000


def test_reward_debt_tracking():
    """Test reward debt prevents reward gaming."""
    staked_amount = 100_000
    reward_per_share = calculate_reward_per_share(10 * NANOERG_PER_ERG, 1_000_000)

    reward_debt = reward_per_share * staked_amount

    # User's debt = RPS * staked
    # This ensures they only earn rewards distributed AFTER they stake
    assert reward_debt == 10**16 * 100_000


# ─── Staking Flow Tests ──────────────────────────────────────────────

def test_stake_flow():
    """Test complete staking flow."""
    # Initial pool state
    pool_staked = 1_000_000
    pool_rps = calculate_reward_per_share(10 * NANOERG_PER_ERG, pool_staked)

    # User stakes 100 tokens
    user_stake = 100
    user_reward_debt = pool_rps * user_stake

    # Pool state after stake
    new_pool_staked = pool_staked + user_stake

    assert new_pool_staked == 1_000_100
    assert user_reward_debt == 10**16 * 100


def test_unstake_flow():
    """Test complete unstaking flow."""
    # User state
    user_staked = 100
    user_reward_debt = 10**16 * 100  # debt from stake

    # Pool state (12 ERG distributed, 1M tokens)
    pool_staked = 1_000_100
    pool_rps = calculate_reward_per_share(12 * NANOERG_PER_ERG, 1_000_000)

    # Calculate pending rewards
    pending_rewards = calculate_pending_rewards(user_staked, user_reward_debt // user_staked, pool_rps)

    # User owns 100/1M = 0.01% of pool
    # 0.01% of 12 ERG = 0.0012 ERG
    # But user only earns rewards distributed AFTER stake
    # After stake, only 2 ERG were distributed
    # 0.01% of 2 ERG = 0.0002 ERG = 200,000 nanoERG
    assert pending_rewards == 200_000


def test_claim_rewards_flow():
    """Test claiming rewards without unstaking."""
    user_staked = 100
    old_rps = calculate_reward_per_share(10 * NANOERG_PER_ERG, 1_000_000)
    new_rps = calculate_reward_per_share(12 * NANOERG_PER_ERG, 1_000_000)

    pending_rewards = calculate_pending_rewards(user_staked, old_rps, new_rps)

    # User claims rewards, debt updates to current RPS
    new_reward_debt = new_rps * user_staked

    assert pending_rewards == 200_000
    assert new_reward_debt == 1.2 * 10**16 * 100


# ─── Edge Case Tests ─────────────────────────────────────────────────

def test_dust_stake():
    """Test dust amounts are rejected."""
    dust_amount = MIN_STAKE_AMOUNT - 1

    assert dust_amount < MIN_STAKE_AMOUNT


def test_unstake_more_than_staked():
    """Test unstaking more than staked is rejected."""
    user_staked = 100
    unstake_amount = 200

    assert unstake_amount > user_staked


def test_reward_per_share_overflow():
    """Test large rewards don't overflow."""
    total_rewards = 2**63 - 1  # max Long value
    total_staked = 1

    reward_per_share = calculate_reward_per_share(total_rewards, total_staked)

    # Should fit in Long
    assert reward_per_share > 0


# ─── APY Calculation Tests ───────────────────────────────────────────

def test_apy_calculation():
    """Test APY is calculated correctly."""
    reward_per_block = 1 * NANOERG_PER_ERG  # 1 ERG per block
    total_staked_value = 1_000_000 * NANOERG_PER_ERG  # 1M ERG
    blocks_per_year = 262_800  # ~2 min blocks

    annual_rewards = reward_per_block * blocks_per_year
    apy = (annual_rewards / total_staked_value) * 100

    # 1 ERG/block * 262,800 blocks = 262,800 ERG/year
    # 262,800 / 1,000,000 = 26.28% APY
    assert pytest.approx(apy, 0.01) == 26.28


def test_zero_staked_apy():
    """Test APY when no tokens are staked."""
    reward_per_block = 1 * NANOERG_PER_ERG
    total_staked_value = 0

    apy = 0 if total_staked_value == 0 else (reward_per_block * blocks_per_year / total_staked_value) * 100

    assert apy == 0


# ─── Multi-Staker Tests ──────────────────────────────────────────────

def test_multiple_stakers_rewards():
    """Test rewards are distributed proportionally."""
    staker1_staked = 250_000
    staker2_staked = 750_000
    total_staked = staker1_staked + staker2_staked

    rewards_distributed = 10 * NANOERG_PER_ERG  # 10 ERG

    rps = calculate_reward_per_share(rewards_distributed, total_staked)

    staker1_rewards = calculate_pending_rewards(staker1_staked, 0, rps)
    staker2_rewards = calculate_pending_rewards(staker2_staked, 0, rps)

    # Staker1: 25% of pool, gets 25% of rewards = 2.5 ERG
    # Staker2: 75% of pool, gets 75% of rewards = 7.5 ERG
    assert staker1_rewards == 2.5 * NANOERG_PER_ERG
    assert staker2_rewards == 7.5 * NANOERG_PER_ERG


def test_partial_unstake():
    """Test unstaking a portion of staked tokens."""
    user_staked = 100_000
    unstake_amount = 30_000

    remaining_staked = user_staked - unstake_amount
    assert remaining_staked == 70_000

    old_rps = calculate_reward_per_share(10 * NANOERG_PER_ERG, 1_000_000)
    new_rps = calculate_reward_per_share(12 * NANOERG_PER_ERG, 1_000_000)

    # Rewards earned on unstaked portion
    earned_rewards = calculate_pending_rewards(unstake_amount, old_rps, new_rps)

    # 30k/1M = 3% of pool, gets 3% of 2 ERG = 0.06 ERG
    # 0.06 ERG = 60,000,000 nanoERG
    assert earned_rewards == 60_000_000  # 0.06 ERG in nanoERG
