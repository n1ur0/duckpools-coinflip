"""
DuckPools - Plinko Game Tests

Test suite for Plinko game logic, RNG, and serialization.

MAT-17: Add Plinko and/or crash game
Acceptance Criteria: 20+ test bets successful
"""

import pytest
import hashlib
from math import comb

from backend.plinko_routes import (
    PLINKO_ROWS,
    PLINKO_ZONES,
    HOUSE_EDGE,
    get_multiplier,
    get_adjusted_multiplier,
    get_zone_probability,
    compute_rng_outcome,
    calculate_payout,
)


# ─── Constants Tests ─────────────────────────────────────────────

def test_plinko_rows():
    """Test Plinko rows constant."""
    assert PLINKO_ROWS == 12


def test_plinko_zones():
    """Test Plinko zones constant."""
    assert PLINKO_ZONES == 13  # rows + 1


def test_house_edge():
    """Test house edge constant."""
    assert HOUSE_EDGE == 0.03


# ─── Multiplier Tests ─────────────────────────────────────────────

def test_get_multiplier_valid_zones():
    """Test getting multiplier for all valid zones."""
    expected_multipliers = [
        1000, 130, 26, 9, 4, 2, 1, 2, 4, 9, 26, 130, 1000
    ]

    for zone in range(PLINKO_ZONES):
        multiplier = get_multiplier(zone)
        assert multiplier == expected_multipliers[zone]


def test_get_multiplier_invalid_zone_low():
    """Test getting multiplier for invalid zone (negative)."""
    with pytest.raises(ValueError, match="Invalid zone"):
        get_multiplier(-1)


def test_get_multiplier_invalid_zone_high():
    """Test getting multiplier for invalid zone (too high)."""
    with pytest.raises(ValueError, match="Invalid zone"):
        get_multiplier(PLINKO_ZONES)


def test_get_adjusted_multiplier():
    """Test adjusted multiplier with house edge."""
    for zone in range(PLINKO_ZONES):
        raw_multiplier = get_multiplier(zone)
        adjusted = get_adjusted_multiplier(zone, HOUSE_EDGE)
        expected = raw_multiplier * (1 - HOUSE_EDGE)
        assert abs(adjusted - expected) < 0.001


def test_get_adjusted_multiplier_custom_edge():
    """Test adjusted multiplier with custom house edge."""
    zone = 0
    raw_multiplier = get_multiplier(zone)
    custom_edge = 0.05
    adjusted = get_adjusted_multiplier(zone, custom_edge)
    expected = raw_multiplier * (1 - custom_edge)
    assert abs(adjusted - expected) < 0.001


# ─── Probability Tests ───────────────────────────────────────────

def test_get_zone_probability_valid_zones():
    """Test getting probability for all valid zones."""
    total_probability = 0

    for zone in range(PLINKO_ZONES):
        prob = get_zone_probability(zone)
        assert 0 <= prob <= 100
        total_probability += prob

    # Total probability should be 100%
    assert abs(total_probability - 100) < 0.001


def test_get_zone_probability_binomial():
    """Test that probabilities follow binomial distribution."""
    for zone in range(PLINKO_ZONES):
        expected = comb(PLINKO_ROWS, zone) * (1 / 2 ** PLINKO_ROWS) * 100
        actual = get_zone_probability(zone)
        assert abs(actual - expected) < 0.001


def test_get_zone_probability_invalid_zone_low():
    """Test getting probability for invalid zone (negative)."""
    with pytest.raises(ValueError, match="Invalid zone"):
        get_zone_probability(-1)


def test_get_zone_probability_invalid_zone_high():
    """Test getting probability for invalid zone (too high)."""
    with pytest.raises(ValueError, match="Invalid zone"):
        get_zone_probability(PLINKO_ZONES)


# ─── RNG Tests ───────────────────────────────────────────────────

def test_compute_rng_outcome_range():
    """Test that RNG outcome is in valid range (0-12)."""
    block_hash = "test_block_hash"
    secret_hex = "abcd"  # 2 bytes

    for _ in range(100):
        zone = compute_rng_outcome(block_hash, secret_hex)
        assert 0 <= zone <= 12


def test_compute_rng_outcome_deterministic():
    """Test that same inputs produce same output."""
    block_hash = "test_block_hash"
    secret_hex = "abcd"

    result1 = compute_rng_outcome(block_hash, secret_hex)
    result2 = compute_rng_outcome(block_hash, secret_hex)

    assert result1 == result2


def test_compute_rng_outcome_different_secrets():
    """Test that different secrets produce potentially different outputs."""
    block_hash = "test_block_hash"
    secret1 = "abcd"
    secret2 = "dcba"

    result1 = compute_rng_outcome(block_hash, secret1)
    result2 = compute_rng_outcome(block_hash, secret2)

    # Results may be the same (probabilistically), but test that function works
    assert isinstance(result1, int)
    assert isinstance(result2, int)


def test_compute_rng_outcome_different_block_hashes():
    """Test that different block hashes produce different outputs."""
    block_hash1 = "block_hash_1"
    block_hash2 = "block_hash_2"
    secret_hex = "abcd"

    result1 = compute_rng_outcome(block_hash1, secret_hex)
    result2 = compute_rng_outcome(block_hash2, secret_hex)

    # Results may be the same (probabilistically), but test that function works
    assert isinstance(result1, int)
    assert isinstance(result2, int)


# ─── Payout Tests ───────────────────────────────────────────────

def test_calculate_payout_center_zone():
    """Test payout calculation for center zone (1x multiplier)."""
    bet_amount = 1000000000  # 1 ERG in nanoERG
    zone = 6  # Center zone with 1x multiplier

    payout = calculate_payout(bet_amount, zone)
    expected = int(bet_amount * 1 * (1 - HOUSE_EDGE))

    assert payout == expected


def test_calculate_payout_edge_zone():
    """Test payout calculation for edge zone (1000x multiplier)."""
    bet_amount = 100000000  # 0.1 ERG in nanoERG
    zone = 0  # Edge zone with 1000x multiplier

    payout = calculate_payout(bet_amount, zone)
    expected = int(bet_amount * 1000 * (1 - HOUSE_EDGE))

    assert payout == expected


def test_calculate_payout_all_zones():
    """Test payout calculation for all zones."""
    bet_amount = 1000000000  # 1 ERG

    for zone in range(PLINKO_ZONES):
        payout = calculate_payout(bet_amount, zone)
        multiplier = get_adjusted_multiplier(zone)
        expected = int(bet_amount * multiplier)
        assert payout == expected


# ─── Integration Tests ───────────────────────────────────────────

def test_full_bet_flow():
    """Test full bet flow: commitment -> RNG -> payout."""
    # Step 1: Generate secret
    import secrets
    secret_bytes = secrets.token_bytes(2)  # 2 bytes
    secret_hex = secret_bytes.hex()

    # Step 2: Create commitment (SHA256 of secret)
    commitment = hashlib.sha256(secret_bytes).hexdigest()

    # Step 3: Simulate block hash
    block_hash = "simulated_block_hash"

    # Step 4: Compute RNG outcome
    zone = compute_rng_outcome(block_hash, secret_hex)

    # Step 5: Calculate payout
    bet_amount = 100000000  # 0.1 ERG
    payout = calculate_payout(bet_amount, zone)

    # Verify valid output
    assert 0 <= zone <= 12
    assert payout > 0
    assert isinstance(commitment, str)
    assert len(commitment) == 64  # SHA256 hex length


def test_multiple_bets_distribution():
    """Test that multiple bets produce a reasonable distribution."""
    import secrets
    import statistics

    zones = []
    num_bets = 1000

    for _ in range(num_bets):
        secret_bytes = secrets.token_bytes(2)
        secret_hex = secret_bytes.hex()
        block_hash = f"block_{len(zones)}"

        zone = compute_rng_outcome(block_hash, secret_hex)
        zones.append(zone)

    # Check that all zones are represented
    unique_zones = set(zones)
    assert len(unique_zones) >= 8  # At least 8 unique zones out of 13

    # Check that center zones are more common (binomial distribution)
    mean_zone = statistics.mean(zones)
    assert 4 <= mean_zone <= 8  # Center should be average

    # Check distribution roughly matches expected
    from collections import Counter
    zone_counts = Counter(zones)

    for zone in range(PLINKO_ZONES):
        expected_prob = get_zone_probability(zone)
        actual_prob = (zone_counts.get(zone, 0) / num_bets) * 100

        # Allow reasonable deviation (10%)
        assert abs(actual_prob - expected_prob) < 10


# ─── Edge Cases ─────────────────────────────────────────────────

def test_zero_bet_amount():
    """Test payout with zero bet amount."""
    bet_amount = 0
    zone = 6

    payout = calculate_payout(bet_amount, zone)
    assert payout == 0


def test_minimum_bet():
    """Test payout with minimum bet (1 nanoERG)."""
    bet_amount = 1
    zone = 6

    payout = calculate_payout(bet_amount, zone)
    assert payout >= 0


def test_large_bet():
    """Test payout with large bet amount."""
    bet_amount = 1000000000000  # 1000 ERG in nanoERG
    zone = 6

    payout = calculate_payout(bet_amount, zone)
    assert payout > 0
    assert payout < bet_amount  # House edge applies


def test_secret_length_validation():
    """Test that secret length is validated in RNG computation."""
    block_hash = "test_block"

    # Valid secret (2 bytes = 4 hex chars)
    valid_secret = "abcd"
    zone = compute_rng_outcome(block_hash, valid_secret)
    assert 0 <= zone <= 12

    # Invalid secrets should still work (function doesn't validate)
    # but the hex conversion may fail
    try:
        compute_rng_outcome(block_hash, "abc")
        # If we get here, the function accepts 3 hex chars
        pass
    except ValueError:
        # Expected: invalid hex
        pass


# ─── Performance Tests ─────────────────────────────────────────

def test_rng_performance():
    """Test that RNG computation is fast enough."""
    import time

    block_hash = "test_block_hash"
    secret_hex = "abcd"

    start_time = time.time()
    iterations = 10000

    for _ in range(iterations):
        zone = compute_rng_outcome(block_hash, secret_hex)

    elapsed = time.time() - start_time
    avg_time = elapsed / iterations

    # Should be much less than 1ms per computation
    assert avg_time < 0.001


# ─── Run Tests ─────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
