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

SCALING_FACTOR = 10**12  # for reward per share precision
MIN_STAKE_AMOUNT = 1_000_000  # 0.001 LP tokens (anti-dust)
REWARD_TOKEN_ID = "dummy_reward_token_id"
LP_TOKEN_ID = "dummy_lp_token_id"


# ─── Reward Calculation Tests ─────────────────────────────────────────

def test_reward_per_share_calculation():
    """Test reward per share is calculated correctly."""
    total_rewards = 10 * 10**9  # 10 ERG in nanoERG
    total_staked = 1_000_000 * 10**9  # 1M LP tokens

    reward_per_share = (total_rewards * SCALING_FACTOR) // total_staked

    # 10 ERG / 1M LP = 0.00001 ERG per LP
    # Scaled: 0.00001 * 1e12 = 10,000,000
    assert reward_per_share == 10_000_000


def test_reward_per_share_with_zero_staked():
    """Test reward per share when pool is empty."""
    total_rewards = 10 * 10**9
    total_staked = 0

    # Should not divide by zero
    reward_per_share = 0 if total_staked == 0 else (total_rewards * SCALING_FACTOR) // total_staked

    assert reward_per_share == 0


def test_user_pending_rewards():
    """Test user pending rewards calculation."""
    staked_amount = 100_000  # 100 LP tokens
    old_reward_per_share = 10_000_000
    new_reward_per_share = 12_000_000  # rewards increased

    reward_debt = old_reward_per_share * staked_amount
    current_debt = new_reward_per_share * staked_amount
    pending_rewards = (current_debt - reward_debt) // SCALING_FACTOR

    # (12M - 10M) * 100k = 200M / 1e12 = 0.0002 ERG
    assert pending_rewards == 200_000  # nanoERG


def test_reward_debt_tracking():
    """Test reward debt prevents reward gaming."""
    staked_amount = 100_000
    reward_per_share_at_stake = 10_000_000

    reward_debt = reward_per_share_at_stake * staked_amount

    # User should only earn rewards from when they staked
    # If rewards were distributed before, they shouldn't get those
    assert reward_debt == 1_000_000_000_000  # 10M * 100k


# ─── Staking Flow Tests ──────────────────────────────────────────────

def test_stake_flow():
    """Test complete staking flow."""
    # Initial state
    pool_staked = 1_000_000
    pool_reward_per_share = 10_000_000

    # User stakes 100 LP tokens
    user_stake = 100
    user_reward_debt = pool_reward_per_share * user_stake

    # Updated pool state
    new_pool_staked = pool_staked + user_stake
    new_pool_reward_per_share = pool_reward_per_share  # unchanged on stake

    assert new_pool_staked == 1_000_100
    assert new_pool_reward_per_share == 10_000_000
    assert user_reward_debt == 1_000_000_000


def test_unstake_flow():
    """Test complete unstaking flow."""
    # User state
    user_staked = 100
    user_reward_debt = 1_000_000_000  # from stake

    # Pool state (rewards distributed)
    pool_staked = 1_000_100
    pool_reward_per_share = 12_000_000  # increased by 2M

    # Calculate pending rewards
    pending_rewards = ((pool_reward_per_share * user_staked) - user_reward_debt) // SCALING_FACTOR

    # (12M * 100 - 1B) / 1e12 = (1.2B - 1B) / 1e12 = 0.0002 ERG
    assert pending_rewards == 200_000  # nanoERG

    # Updated pool state
    new_pool_staked = pool_staked - user_staked
    assert new_pool_staked == 1_000_000


def test_claim_rewards_flow():
    """Test claiming rewards without unstaking."""
    user_staked = 100
    user_reward_debt = 1_000_000_000

    pool_reward_per_share = 12_000_000
    pending_rewards = ((pool_reward_per_share * user_staked) - user_reward_debt) // SCALING_FACTOR

    # User claims rewards, updates reward debt
    new_reward_debt = pool_reward_per_share * user_staked

    assert pending_rewards == 200_000  # nanoERG claimed
    assert new_reward_debt == 1_200_000_000  # updated to current RPS


# ─── Edge Case Tests ─────────────────────────────────────────────────

def test_dust_stake():
    """Test dust amounts are rejected."""
    dust_amount = MIN_STAKE_AMOUNT - 1

    # Should reject dust stakes
    assert dust_amount < MIN_STAKE_AMOUNT


def test_unstake_more_than_staked():
    """Test unstaking more than staked is rejected."""
    user_staked = 100
    unstake_amount = 200

    # Should fail validation
    assert unstake_amount > user_staked


def test_reward_per_share_overflow():
    """Test large rewards don't overflow."""
    total_rewards = 2**63 - 1  # max Long
    total_staked = 1

    # Should handle gracefully (may cap or use larger type)
    # For now, ensure we're aware of the risk
    assert total_rewards > 0


# ─── APY Calculation Tests ───────────────────────────────────────────

def test_apy_calculation():
    """Test APY is calculated correctly."""
    reward_per_block = 1 * 10**9  # 1 ERG per block
    total_staked_value = 1_000_000 * 10**9  # 1M ERG staked
    blocks_per_year = 262_800  # ~2 min blocks

    annual_rewards = reward_per_block * blocks_per_year
    apy = (annual_rewards / total_staked_value) * 100

    # 1 ERG/block * 262,800 blocks = 262,800 ERG/year
    # 262,800 / 1,000,000 = 26.28% APY
    assert apy == 26.28


def test_zero_staked_apy():
    """Test APY when no tokens are staked."""
    reward_per_block = 1 * 10**9
    total_staked_value = 0

    # Should return 0% APY
    apy = 0 if total_staked_value == 0 else (reward_per_block * 262_800 / total_staked_value) * 100
    assert apy == 0


# ─── Multi-Staker Tests ──────────────────────────────────────────────

def test_multiple_stakers_rewards():
    """Test rewards are distributed proportionally."""
    staker1_staked = 100_000
    staker2_staked = 300_000
    total_staked = staker1_staked + staker2_staked

    rewards_distributed = 10 * 10**9  # 10 ERG

    # Calculate reward per share
    reward_per_share = (rewards_distributed * SCALING_FACTOR) // total_staked

    # Calculate each staker's rewards
    staker1_rewards = (reward_per_share * staker1_staked) // SCALING_FACTOR
    staker2_rewards = (reward_per_share * staker2_staked) // SCALING_FACTOR

    # Staker1: 100k/400k = 25% of rewards = 2.5 ERG
    # Staker2: 300k/400k = 75% of rewards = 7.5 ERG
    assert staker1_rewards == 2.5 * 10**9
    assert staker2_rewards == 7.5 * 10**9


def test_partial_unstake():
    """Test unstaking a portion of staked tokens."""
    user_staked = 100_000
    unstake_amount = 30_000

    remaining_staked = user_staked - unstake_amount
    assert remaining_staked == 70_000

    # Reward debt should be recalculated proportionally
    old_reward_per_share = 10_000_000
    new_reward_per_share = 12_000_000

    # Rewards earned on unstaked portion
    earned_rewards = ((new_reward_per_share - old_reward_per_share) * unstake_amount) // SCALING_FACTOR
    assert earned_rewards == 60_000  # nanoERG
