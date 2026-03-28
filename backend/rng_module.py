"""
DuckPools RNG Module - Implements provably-fair random number generation

This module implements the ACTUAL protocol RNG scheme as documented in:
- docs/ARCHITECTURE.md
- smart-contracts/SECURITY_AUDIT_PREPARATION.md
- sdk/README.md

Protocol RNG Formula:
    SHA256(blockHash_as_utf8 || secret_bytes)[0] % 2

Where:
    - blockHash: UTF-8 encoded hex string (NOT "||" literal separator)
    - secret_bytes: Raw 8-byte secret
    - Outcome: First byte of SHA256 hash, modulo 2 for coinflip

MAT-252: Fix RNG module to match actual protocol implementation
"""

import hashlib
import math
import os
from typing import Tuple, List, Dict
from dataclasses import dataclass


# ─── Core RNG Functions ────────────────────────────────────────────────

def compute_rng(block_hash: str, secret_bytes: bytes) -> int:
    """
    Compute RNG outcome using ACTUAL protocol scheme.

    Formula: SHA256(blockHash_as_utf8 || secret_bytes)[0] % 2

    Args:
        block_hash: Block hash as hex string (e.g., "abcd1234...")
        secret_bytes: 8-byte secret from player commitment

    Returns:
        int: 0 (tails) or 1 (heads)

    Examples:
        >>> compute_rng("abcd1234", bytes([1,2,3,4,5,6,7,8]))
        0  # or 1
    """
    # UTF-8 encode the block hash string
    block_hash_bytes = block_hash.encode('utf-8')

    # Raw byte concatenation (no "||" separator)
    rng_data = block_hash_bytes + secret_bytes

    # Compute SHA256 hash
    rng_hash = hashlib.sha256(rng_data).digest()

    # Extract first byte and apply modulo 2
    outcome = rng_hash[0] % 2

    return outcome


def generate_commit(secret_bytes: bytes, choice: int) -> str:
    """
    Generate commitment hash for bet placement.

    Uses SHA256(secret_bytes || choice_byte) for commitment.

    Args:
        secret_bytes: 8-byte secret
        choice: 0 (heads) or 1 (tails)

    Returns:
        Hex string of commitment hash
    """
    if len(secret_bytes) != 8:
        raise ValueError(f"Secret must be 8 bytes, got {len(secret_bytes)}")

    if choice not in (0, 1):
        raise ValueError(f"Choice must be 0 or 1, got {choice}")

    choice_byte = bytes([choice])
    commit_data = secret_bytes + choice_byte
    commit_hash = hashlib.sha256(commit_data).digest()

    return commit_hash.hex()


def verify_commit(commit_hex: str, secret_bytes: bytes, choice: int) -> bool:
    """
    Verify that commitment matches secret and choice.

    Args:
        commit_hex: Hex string of commitment hash
        secret_bytes: 8-byte secret
        choice: 0 (heads) or 1 (tails)

    Returns:
        bool: True if commitment is valid
    """
    if len(secret_bytes) != 8:
        return False

    if choice not in (0, 1):
        return False

    computed_commit = generate_commit(secret_bytes, choice)
    return computed_commit.lower() == commit_hex.lower()


# ─── Dice RNG (Future expansion) ───────────────────────────────────

def dice_rng(block_hash: str, secret_bytes: bytes) -> int:
    """
    Compute dice roll outcome using rejection sampling.

    Formula: Rejection-sampled from SHA256(blockHash || secret) to get 0-99

    Rejection sampling prevents modulo bias (MAT-249 fix):
    - Use first byte < 200 (2 * 100)
    - Reject bytes >= 200 to ensure uniform distribution
    - Continue through hash bytes until valid value found

    Args:
        block_hash: Block hash as hex string
        secret_bytes: Secret bytes

    Returns:
        int: Roll value 0-99
    """
    block_hash_bytes = block_hash.encode('utf-8')
    rng_data = block_hash_bytes + secret_bytes
    rng_hash = hashlib.sha256(rng_data).digest()

    # Rejection sampling: only use bytes < 200
    for byte_val in rng_hash:
        if byte_val < 200:  # 200 = 2 * 100
            return byte_val % 100

    # Fallback (astronomically unlikely to reach) - also use rejection sampling
    # Use 16-bit value but reject >= 65500 to avoid modulo bias
    sixteen_bit_value = int.from_bytes(rng_hash[:2], 'big')
    if sixteen_bit_value < 65500:  # 65500 = 655 * 100
        return sixteen_bit_value % 100
    else:
        # If somehow still in rejection territory, use single byte with rejection
        for byte_val in rng_hash[2:]:
            if byte_val < 200:
                return byte_val % 100
        # Ultimate fallback - just use first byte mod 100 (extremely biased but virtually impossible)
        return rng_hash[0] % 100


# ─── Statistical Analysis ────────────────────────────────────────────

@dataclass
class RNGTestResult:
    """Results of RNG statistical testing."""
    total_outcomes: int
    heads_count: int
    tails_count: int
    heads_ratio: float
    tails_ratio: float
    expected_ratio: float = 0.5
    chi_square: float = 0.0
    p_value: float = 0.0
    entropy_bits: float = 0.0
    uniform: bool = False


def shannon_entropy(counts: Dict[int, int]) -> float:
    """
    Calculate Shannon entropy of outcome distribution.

    H(X) = -sum(p(x) * log2(p(x)))

    Args:
        counts: Dictionary mapping outcomes to their counts

    Returns:
        Entropy in bits (max 1.0 for fair coinflip)
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        if count > 0:
            probability = count / total
            # Shannon entropy formula: -p * log2(p)
            entropy -= probability * math.log2(probability)

    return entropy


def chi_square_uniform(counts: Dict[int, int], expected: float = None) -> Tuple[float, float]:
    """
    Perform chi-square test for uniform distribution.

    Args:
        counts: Dictionary mapping outcomes to their counts
        expected: Expected count per outcome (default: total / 2)

    Returns:
        (chi_square_statistic, p_value)
    """
    total = sum(counts.values())
    n_outcomes = len(counts)

    if expected is None:
        expected = total / n_outcomes

    # Chi-square statistic: sum((observed - expected)^2 / expected)
    chi_sq = 0.0
    for obs in counts.values():
        chi_sq += ((obs - expected) ** 2) / expected

    # Degrees of freedom: n_outcomes - 1
    df = n_outcomes - 1

    # Approximate p-value using incomplete gamma function
    # For df=1 (coinflip), chi^2 distribution is known
    # This is a simplified approximation for common use cases
    if df == 1:
        # For coinflip, p-value = exp(-chi_sq / 2)
        p_value = math.exp(-chi_sq / 2)
    else:
        # Approximation for other degrees of freedom
        # Use chi-square CDF approximation
        p_value = max(0.0, 1.0 - (chi_sq / (2 * df)))

    return chi_sq, p_value


def simulate_coinflip(num_bets: int, block_hashes: List[str] = None) -> RNGTestResult:
    """
    Simulate coinflip bets to test RNG distribution.

    Args:
        num_bets: Number of bets to simulate
        block_hashes: Optional list of block hashes (uses random if None)

    Returns:
        RNGTestResult with statistical metrics
    """
    import random

    if block_hashes is None:
        # Generate pseudo-random block hashes
        block_hashes = [f"{random.getrandbits(256):064x}" for _ in range(num_bets)]

    counts = {0: 0, 1: 0}  # 0=tails, 1=heads

    for i in range(num_bets):
        block_hash = block_hashes[i % len(block_hashes)]
        secret_bytes = random.getrandbits(64).to_bytes(8, 'big')
        outcome = compute_rng(block_hash, secret_bytes)
        counts[outcome] += 1

    total = sum(counts.values())
    heads = counts[1]
    tails = counts[0]

    heads_ratio = heads / total
    tails_ratio = tails / total

    # Chi-square test
    chi_sq, p_value = chi_square_uniform(counts)

    # Shannon entropy
    entropy = shannon_entropy(counts)

    # Determine if uniform (p-value > 0.01 threshold)
    is_uniform = p_value > 0.01 and abs(heads_ratio - 0.5) < 0.02

    return RNGTestResult(
        total_outcomes=total,
        heads_count=heads,
        tails_count=tails,
        heads_ratio=heads_ratio,
        tails_ratio=tails_ratio,
        chi_square=chi_sq,
        p_value=p_value,
        entropy_bits=entropy,
        uniform=is_uniform
    )


def simulate_dice(num_rolls: int, block_hashes: List[str] = None) -> Dict[int, int]:
    """
    Simulate dice rolls to test distribution.

    Args:
        num_rolls: Number of dice rolls
        block_hashes: Optional list of block hashes

    Returns:
        Dictionary mapping roll values (0-99) to their counts
    """
    import random

    if block_hashes is None:
        block_hashes = [f"{random.getrandbits(256):064x}" for _ in range(num_rolls)]

    counts = {i: 0 for i in range(100)}

    for i in range(num_rolls):
        block_hash = block_hashes[i % len(block_hashes)]
        secret_bytes = os.urandom(8)
        roll = dice_rng(block_hash, secret_bytes)
        counts[roll] += 1

    return counts


# ─── Command Line Interface ────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Run 100k simulations by default
    num_simulations = 100000
    if len(sys.argv) > 1:
        num_simulations = int(sys.argv[1])

    print(f"Running {num_simulations:,} coinflip simulations...")
    print("=" * 60)

    result = simulate_coinflip(num_simulations)

    print(f"Total outcomes: {result.total_outcomes:,}")
    print(f"Heads count:    {result.heads_count:,} ({result.heads_ratio:.4%})")
    print(f"Tails count:    {result.tails_count:,} ({result.tails_ratio:.4%})")
    print(f"Expected ratio: {result.expected_ratio:.4%}")
    print()
    print(f"Chi-square:     {result.chi_square:.6f}")
    print(f"P-value:       {result.p_value:.6f}")
    print(f"Entropy:       {result.entropy_bits:.6f} bits (max 1.0)")
    print()
    print(f"Uniform distribution: {'PASS' if result.uniform else 'FAIL'}")
    print()
    print("Acceptance criteria:")
    print(f"  [ ] P-value > 0.01: {'PASS' if result.p_value > 0.01 else 'FAIL'}")
    print(f"  [ ] Heads ratio ~50%: {'PASS' if abs(result.heads_ratio - 0.5) < 0.02 else 'FAIL'}")
    print(f"  [ ] Entropy ~1.0 bits: {'PASS' if result.entropy_bits > 0.99 else 'FAIL'}")
