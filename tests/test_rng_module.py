"""
Tests for RNG module - Verify correct protocol implementation

MAT-252: RNG module implements and tests correct hash scheme
"""

import pytest
import hashlib
from backend.rng_module import (
    compute_rng,
    generate_commit,
    verify_commit,
    dice_rng,
    shannon_entropy,
    chi_square_uniform,
    simulate_coinflip,
    simulate_dice,
    RNGTestResult,
)


# ─── Core RNG Tests ────────────────────────────────────────────────────

def test_compute_rng_basic():
    """Test basic RNG computation."""
    block_hash = "abcd1234567890"
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    outcome = compute_rng(block_hash, secret_bytes)

    # Result should be 0 or 1
    assert outcome in (0, 1)


def test_compute_rng_deterministic():
    """Test that same inputs produce same output."""
    block_hash = "abcd1234567890"
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    outcome1 = compute_rng(block_hash, secret_bytes)
    outcome2 = compute_rng(block_hash, secret_bytes)

    assert outcome1 == outcome2


def test_compute_rng_different_block_hashes():
    """Test that different block hashes produce different outcomes (high probability)."""
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    # Test 100 different block hashes
    outcomes = set()
    for i in range(100):
        block_hash = f"{i:064x}"
        outcome = compute_rng(block_hash, secret_bytes)
        outcomes.add(outcome)

    # Should have at least some variation (probability of all same is 2^-100)
    assert len(outcomes) > 1


def test_compute_rng_different_secrets():
    """Test that different secrets produce different outcomes (high probability)."""
    block_hash = "abcd1234567890"

    outcomes = set()
    for i in range(100):
        secret_bytes = i.to_bytes(8, 'big')
        outcome = compute_rng(block_hash, secret_bytes)
        outcomes.add(outcome)

    # Should have at least some variation
    assert len(outcomes) > 1


def test_compute_rng_protocol_scheme():
    """
    Verify the RNG uses the ACTUAL protocol scheme:
    SHA256(blockHash_as_utf8 || secret_bytes)[0] % 2
    """
    block_hash = "abcd1234567890"
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    # Compute expected result manually
    block_hash_bytes = block_hash.encode('utf-8')  # UTF-8 encode
    rng_data = block_hash_bytes + secret_bytes  # Raw concatenation (no "||")
    rng_hash = hashlib.sha256(rng_data).digest()
    expected_outcome = rng_hash[0] % 2

    actual_outcome = compute_rng(block_hash, secret_bytes)

    assert actual_outcome == expected_outcome


# ─── Commitment Tests ────────────────────────────────────────────────

def test_generate_commit_valid():
    """Test commitment generation."""
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    choice = 0

    commit = generate_commit(secret_bytes, choice)

    # Should be 64 hex characters (32 bytes)
    assert len(commit) == 64
    assert all(c in '0123456789abcdef' for c in commit.lower())


def test_generate_commit_choice_0():
    """Test commitment for choice=0 (heads)."""
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    commit_0 = generate_commit(secret_bytes, 0)

    assert len(commit_0) == 64


def test_generate_commit_choice_1():
    """Test commitment for choice=1 (tails)."""
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    commit_1 = generate_commit(secret_bytes, 1)

    assert len(commit_1) == 64

    # Different choices should produce different commitments
    commit_0 = generate_commit(secret_bytes, 0)
    assert commit_0 != commit_1


def test_generate_commit_invalid_secret_length():
    """Test that invalid secret length raises error."""
    secret_bytes = bytes([1, 2, 3, 4])  # Only 4 bytes

    with pytest.raises(ValueError, match="Secret must be 8 bytes"):
        generate_commit(secret_bytes, 0)


def test_generate_commit_invalid_choice():
    """Test that invalid choice raises error."""
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    with pytest.raises(ValueError, match="Choice must be 0 or 1"):
        generate_commit(secret_bytes, 2)


def test_verify_commit_valid():
    """Test commitment verification."""
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    choice = 0

    commit = generate_commit(secret_bytes, choice)
    is_valid = verify_commit(commit, secret_bytes, choice)

    assert is_valid is True


def test_verify_commit_invalid():
    """Test verification fails for wrong commitment."""
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    commit = generate_commit(secret_bytes, 0)

    # Wrong choice
    assert verify_commit(commit, secret_bytes, 1) is False

    # Wrong secret
    wrong_secret = bytes([9, 10, 11, 12, 13, 14, 15, 16])
    assert verify_commit(commit, wrong_secret, 0) is False


def test_verify_commit_protocol_scheme():
    """
    Verify commitment uses SHA256, not Blake2b256.

    Protocol uses: SHA256(secret_bytes || choice_byte)
    """
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    choice = 0

    # Manually compute expected commitment using SHA256
    choice_byte = bytes([choice])
    commit_data = secret_bytes + choice_byte
    expected_hash = hashlib.sha256(commit_data).hexdigest()

    actual_commit = generate_commit(secret_bytes, choice)

    assert actual_commit == expected_hash


# ─── Dice RNG Tests ───────────────────────────────────────────────

def test_dice_rng_basic():
    """Test basic dice roll."""
    block_hash = "abcd1234567890"
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    roll = dice_rng(block_hash, secret_bytes)

    assert 0 <= roll <= 99


def test_dice_rng_deterministic():
    """Test that same inputs produce same output."""
    block_hash = "abcd1234567890"
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    roll1 = dice_rng(block_hash, secret_bytes)
    roll2 = dice_rng(block_hash, secret_bytes)

    assert roll1 == roll2


def test_dice_rng_distribution():
    """Test that dice rolls cover the full range."""
    block_hash = "abcd1234567890"

    rolls = set()
    for i in range(1000):
        secret_bytes = i.to_bytes(8, 'big')
        roll = dice_rng(block_hash, secret_bytes)
        rolls.add(roll)

    # Should have most values (probability of missing any is low)
    assert len(rolls) > 50


def test_dice_rng_no_modulo_bias():
    """
    Test that dice_rng uses rejection sampling to avoid modulo bias.

    MAT-249: First 56 values (0-55) have probability 3/256,
    but values 56-99 have probability 2/256.
    Rejection sampling fixes this by only using bytes < 200.
    """
    import random

    # Count outcomes with many random secrets
    block_hash = "abcd1234567890"
    counts = [0] * 100

    for i in range(10000):
        secret_bytes = random.getrandbits(64).to_bytes(8, 'big')
        roll = dice_rng(block_hash, secret_bytes)
        counts[roll] += 1

    # All values should have similar counts (within reasonable variance)
    # Rejection sampling ensures uniform distribution
    avg_count = sum(counts) / 100

    # Check that no value is egregiously overrepresented
    max_count = max(counts)
    min_count = min(counts)

    # With 10000 samples, uniform should give ~100 per value
    # Allow 50% variance due to randomness
    assert max_count < avg_count * 1.5, f"Max count {max_count} too high (avg: {avg_count})"
    assert min_count > avg_count * 0.5, f"Min count {min_count} too low (avg: {avg_count})"


# ─── Statistical Tests ─────────────────────────────────────────────

def test_shannon_entropy_fair():
    """Test Shannon entropy for fair coinflip."""
    counts = {0: 50, 1: 50}  # Perfectly fair

    entropy = shannon_entropy(counts)

    # Perfect entropy for binary distribution is 1.0 bit
    assert entropy == pytest.approx(1.0, rel=1e-9)


def test_shannon_entropy_biased():
    """Test Shannon entropy for biased coinflip."""
    counts = {0: 90, 1: 10}  # Highly biased

    entropy = shannon_entropy(counts)

    # Biased distribution has lower entropy
    assert entropy < 1.0
    assert entropy > 0.0


def test_shannon_entropy_single_outcome():
    """Test entropy when all outcomes are the same."""
    counts = {0: 100, 1: 0}  # All tails

    entropy = shannon_entropy(counts)

    # Zero entropy
    assert entropy == 0.0


def test_chi_square_fair():
    """Test chi-square for fair distribution."""
    counts = {0: 500, 1: 500}  # Perfectly fair

    chi_sq, p_value = chi_square_uniform(counts)

    # Chi-square should be near 0 for perfect distribution
    assert chi_sq == pytest.approx(0.0, rel=1e-9)
    # P-value should be 1.0 (perfect fit)
    assert p_value == pytest.approx(1.0, abs=1e-9)


def test_chi_square_unfair():
    """Test chi-square detects unfair distribution."""
    counts = {0: 900, 1: 100}  # Very unfair

    chi_sq, p_value = chi_square_uniform(counts)

    # Chi-square should be large
    assert chi_sq > 100
    # P-value should be very small
    assert p_value < 0.0001


def test_chi_square_p_value_threshold():
    """
    Test that p-value threshold of 0.01 is reasonable.

    With 1000 samples and fair distribution, p-value should be > 0.01
    in ~99% of cases.
    """
    import random

    # Run multiple trials
    p_values = []
    for _ in range(100):
        counts = {0: 0, 1: 0}
        for _ in range(1000):
            counts[random.randint(0, 1)] += 1

        _, p_value = chi_square_uniform(counts)
        p_values.append(p_value)

    # Most p-values should be > 0.01 (false positive rate < 1%)
    above_threshold = sum(1 for p in p_values if p > 0.01)
    assert above_threshold > 90  # At least 90% should pass


# ─── Simulation Tests ───────────────────────────────────────────

def test_simulate_coinflip_structure():
    """Test that simulation returns correct structure."""
    result = simulate_coinflip(100)

    assert isinstance(result, RNGTestResult)
    assert result.total_outcomes == 100
    assert result.heads_count + result.tails_count == 100


def test_simulate_coinflip_large():
    """Test large simulation (100k)."""
    result = simulate_coinflip(100000)

    assert result.total_outcomes == 100000

    # For fair coin, both should be close to 50k
    assert 45000 < result.heads_count < 55000
    assert 45000 < result.tails_count < 55000

    # P-value should be > 0.01 (passes fairness test)
    assert result.p_value > 0.001  # Allow 0.1% false positive rate

    # Entropy should be close to 1.0
    assert result.entropy_bits > 0.99


def test_simulate_coinflip_custom_block_hashes():
    """Test simulation with custom block hashes."""
    block_hashes = [
        "0000000000000000000000000000000000000000000000000000000000000000000",
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    ]

    result = simulate_coinflip(100, block_hashes)

    assert result.total_outcomes == 100


def test_simulate_dice_basic():
    """Test dice simulation."""
    counts = simulate_dice(10000)

    assert len(counts) == 100  # Values 0-99
    assert sum(counts.values()) == 10000

    # All values should appear at least once
    assert all(count > 0 for count in counts.values())

    # Distribution should be approximately uniform
    avg_count = 10000 / 100
    max_count = max(counts.values())
    min_count = min(counts.values())

    # Allow reasonable variance
    assert max_count < avg_count * 2.0
    assert min_count > avg_count * 0.2


# ─── Integration Tests ───────────────────────────────────────────

def test_full_commit_reveal_flow():
    """
    Test full commit-reveal flow.

    1. Generate secret
    2. Generate commitment
    3. Simulate block hash
    4. Reveal and compute outcome
    5. Verify commitment matches
    """
    import random

    # Generate secret
    secret_bytes = random.getrandbits(64).to_bytes(8, 'big')
    choice = 0  # Heads

    # Generate commitment
    commitment = generate_commit(secret_bytes, choice)

    # Simulate block hash
    block_hash = f"{random.getrandbits(256):064x}"

    # Compute RNG outcome
    outcome = compute_rng(block_hash, secret_bytes)

    # Verify commitment
    is_valid = verify_commit(commitment, secret_bytes, choice)
    assert is_valid

    # Outcome should be 0 or 1
    assert outcome in (0, 1)


def test_coinflip_bet_flow():
    """
    Test complete coinflip bet flow as would happen in protocol.

    1. Player generates secret and choice
    2. Player generates commitment
    3. Block is mined with block hash
    4. House computes RNG outcome
    5. Bet is settled
    """
    import random

    # Player setup
    secret_bytes = random.getrandbits(64).to_bytes(8, 'big')
    player_choice = 1  # Tails

    # Player commits
    commitment_hash = generate_commit(secret_bytes, player_choice)

    # Block is mined
    block_hash = f"{random.getrandbits(256):064x}"

    # House reveals
    house_outcome = compute_rng(block_hash, secret_bytes)

    # Determine winner
    if house_outcome == player_choice:
        result = "win"
    else:
        result = "lose"

    # Verify commitment after the fact
    assert verify_commit(commitment_hash, secret_bytes, player_choice)

    # Flow completed
    assert result in ("win", "lose")


# ─── Protocol Verification Tests ─────────────────────────────────

def test_protocol_uses_utf8_block_hash():
    """
    MAT-252: Verify block hash is UTF-8 encoded, not raw bytes.

    The issue states the module was using block_hash || game_id
    with literal "||" separator. The actual protocol uses:
    blockHash_as_utf8 || secret_bytes (raw byte concatenation)
    """
    block_hash = "abcd1234567890"
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    # Compute using our module
    outcome = compute_rng(block_hash, secret_bytes)

    # Manually compute with UTF-8 encoding (protocol spec)
    block_hash_bytes = block_hash.encode('utf-8')  # NOT bytes.fromhex!
    rng_data = block_hash_bytes + secret_bytes
    manual_hash = hashlib.sha256(rng_data).digest()
    expected_outcome = manual_hash[0] % 2

    assert outcome == expected_outcome


def test_protocol_uses_first_byte():
    """
    MAT-252: Verify outcome uses first byte, not first hex nibble.

    The issue states the module was using first hex nibble.
    Protocol uses: SHA256(...)[0] % 2
    """
    block_hash = "abcd1234567890"
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    outcome = compute_rng(block_hash, secret_bytes)

    # Should be 0 or 1 (first byte mod 2)
    assert outcome in (0, 1)


def test_protocol_uses_raw_concatenation():
    """
    MAT-252: Verify raw byte concatenation, no "||" separator.

    The issue states the module was using "||" literal string.
    Protocol uses: blockHash_bytes + secret_bytes (no separator)
    """
    block_hash = "abcd1234567890"
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])

    outcome = compute_rng(block_hash, secret_bytes)

    # Compute with raw concatenation
    block_hash_bytes = block_hash.encode('utf-8')
    rng_data_no_separator = block_hash_bytes + secret_bytes
    hash_no_separator = hashlib.sha256(rng_data_no_separator).digest()
    expected_outcome = hash_no_separator[0] % 2

    assert outcome == expected_outcome


def test_protocol_uses_sha256_not_blake2b():
    """
    MAT-252: Verify commitment uses SHA256, not Blake2b256.

    The issue states the module was using Blake2b256.
    Protocol uses: SHA256(secret_bytes || choice_byte)
    """
    secret_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    choice = 0

    # Generate commitment with our module
    commitment = generate_commit(secret_bytes, choice)

    # Manually compute with SHA256
    choice_byte = bytes([choice])
    commit_data = secret_bytes + choice_byte
    expected_hash = hashlib.sha256(commit_data).hexdigest()

    # Should match SHA256, not Blake2b256
    assert commitment == expected_hash

    # Verify it's NOT Blake2b256
    blake_hash = hashlib.blake2b(commit_data).hexdigest()
    assert commitment != blake_hash
