"""
DuckPools RNG Module - Implements provably-fair random number generation

This module implements the ACTUAL protocol RNG scheme matching the
compiled on-chain contract (coinflip_v2.es):

On-chain contract (coinflip_v2.es lines 51-53):
    val blockSeed  = CONTEXT.preHeader.parentId      // Coll[Byte] — raw 32 bytes
    val rngHash    = blake2b256(blockSeed ++ playerSecret)
    val flipResult = rngHash(0) % 2

OFF-CHAIN MUST MATCH ON-CHAIN EXACTLY:
    blake2b256(blockId_raw_bytes || playerSecret_raw_bytes)[0] % 2

Where:
    - blockId: Raw 32-byte block ID (hex-decoded, NOT UTF-8 encoded hex string)
    - playerSecret: Raw secret bytes (same bytes stored in R9)
    - Outcome: First byte of blake2b256 hash, modulo 2 for coinflip

SECURITY (SEC-CRITICAL-1): blake2b256 is the native hash on Ergo.
The on-chain contracts use the blake2b256 opcode. Using SHA-256 would
cause every single reveal to fail verification, making the protocol unusable.

SECURITY (SEC-CRITICAL-3): Previous version UTF-8 encoded the block hash hex
string before hashing. This produced DIFFERENT results than the on-chain
contract which uses raw bytes from CONTEXT.preHeader.parentId. Fixed 2026-03-28.

MAT-328: Fix incomplete RNG code in smart contract and backend
"""

import hashlib
import math
import os
from typing import Tuple, List, Dict
from dataclasses import dataclass


# ─── Core RNG Functions ────────────────────────────────────────────────

def compute_rng(block_hash: str, secret_bytes: bytes) -> int:
    """
    Compute RNG outcome matching on-chain contract exactly.

    Formula: blake2b256(blockId_raw_bytes || playerSecret_raw_bytes)[0] % 2

    Args:
        block_hash: Block ID as 64-character hex string (e.g., "abcd1234...")
                      Will be hex-decoded to raw 32 bytes to match
                      CONTEXT.preHeader.parentId (Coll[Byte]) on-chain.
        secret_bytes: Raw secret bytes (same bytes stored in contract R9)

    Returns:
        int: 0 (tails) or 1 (heads)

    Examples:
        >>> compute_rng("abcd1234" + "0" * 56, bytes([1,2,3,4,5,6,7,8]))
        0  # or 1
    """
    # CRITICAL: Hex-decode the block hash to raw bytes.
    # The on-chain contract uses CONTEXT.preHeader.parentId which is
    # Coll[Byte] (raw 32 bytes), NOT a UTF-8 encoded hex string.
    block_hash_bytes = bytes.fromhex(block_hash)

    # Raw byte concatenation (no separator) — matches on-chain
    rng_data = block_hash_bytes + secret_bytes

    # Compute blake2b256 hash (native Ergo hash — MUST match on-chain)
    rng_hash = hashlib.blake2b(rng_data, digest_size=32).digest()

    # Extract first byte and apply modulo 2
    outcome = rng_hash[0] % 2

    return outcome


def generate_commit(secret_bytes: bytes, choice: int) -> str:
    """
    Generate commitment hash for bet placement.

    Uses blake2b256(secret_bytes || choice_byte) for commitment.
    This MUST match on-chain contract verification which uses the
    blake2b256 opcode on Ergo.

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
    commit_hash = hashlib.blake2b(commit_data, digest_size=32).digest()

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


def verify_rng_fairness(block_hashes: List[str], expected_outcomes: Dict[int, int] = None) -> Dict[str, any]:
    """
    Verify RNG fairness by comparing computed outcomes against expected results.
    
    Args:
        block_hashes: List of block hashes to test
        expected_outcomes: Optional dictionary of expected outcomes {0: tails_count, 1: heads_count}
    
    Returns:
        Dictionary with verification results and statistics
    """
    if expected_outcomes is None:
        expected_outcomes = {0: 0, 1: 0}
    
    counts = {0: 0, 1: 0}  # 0=tails, 1=heads
    
    for block_hash in block_hashes:
        # Use consistent secret for reproducible testing
        test_secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])  # Fixed secret for deterministic testing
        outcome = compute_rng(block_hash, test_secret)
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
    
    # Compare against expected outcomes if provided
    matches_expected = True
    if expected_outcomes:
        for outcome, expected_count in expected_outcomes.items():
            if counts[outcome] != expected_count:
                matches_expected = False
                break
    
    return {
        "total_outcomes": total,
        "heads_count": heads,
        "tails_count": tails,
        "heads_ratio": heads_ratio,
        "tails_ratio": tails_ratio,
        "chi_square": chi_sq,
        "p_value": p_value,
        "entropy_bits": entropy,
        "uniform": is_uniform,
        "matches_expected": matches_expected,
        "verification_passed": is_uniform and matches_expected
    }


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
        # Use different random secret per bet for valid statistical test
        secret_bytes=os.urandom(8)  # 8-byte random secret
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


def verify_rng_fairness(block_hashes: List[str], expected_outcomes: Dict[int, int] = None) -> Dict[str, any]:
    """
    Verify RNG fairness by comparing computed outcomes against expected results.
    
    Args:
        block_hashes: List of block hashes to test
        expected_outcomes: Optional dictionary of expected outcomes {0: tails_count, 1: heads_count}
    
    Returns:
        Dictionary with verification results and statistics
    """
    if expected_outcomes is None:
        expected_outcomes = {0: 0, 1: 0}
    
    counts = {0: 0, 1: 0}  # 0=tails, 1=heads
    
    for block_hash in block_hashes:
        # Use consistent secret for reproducible testing
        test_secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])  # Fixed secret for deterministic testing
        outcome = compute_rng(block_hash, test_secret)
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
    
    # Compare against expected outcomes if provided
    matches_expected = True
    if expected_outcomes:
        for outcome, expected_count in expected_outcomes.items():
            if counts[outcome] != expected_count:
                matches_expected = False
                break
    
    return {
        "total_outcomes": total,
        "heads_count": heads,
        "tails_count": tails,
        "heads_ratio": heads_ratio,
        "tails_ratio": tails_ratio,
        "chi_square": chi_sq,
        "p_value": p_value,
        "entropy_bits": entropy,
        "uniform": is_uniform,
        "matches_expected": matches_expected,
        "verification_passed": is_uniform and matches_expected
    }


def run_rng_verification_test():
    """Run comprehensive RNG verification tests"""
    import sys
    import random
    
    print("Running RNG Fairness Verification Tests")
    print("=" * 60)
    
    # Test 1: Basic statistical distribution test
    print("\n1. Statistical Distribution Test (100,000 simulations):")
    result = simulate_coinflip(100000)
    
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
    
    # Test 2: Deterministic verification with known block hashes
    print("\n2. Deterministic Verification with Known Block Hashes:")
    test_block_hashes = [
        "0000000000000000000000000000000000000000000000000000000000000000",
        "1111111111111111111111111111111111111111111111111111111111111111",
        "2222222222222222222222222222222222222222222222222222222222222222",
        "3333333333333333333333333333333333333333333333333333333333333333",
        "4444444444444444444444444444444444444444444444444444444444444444"
    ]
    
    verification_result = verify_rng_fairness(test_block_hashes)
    
    print(f"Total outcomes: {verification_result['total_outcomes']}")
    print(f"Heads count:    {verification_result['heads_count']} ({verification_result['heads_ratio']:.4%})")
    print(f"Tails count:    {verification_result['tails_count']} ({verification_result['tails_ratio']:.4%})")
    print()
    
    print(f"Chi-square:     {verification_result['chi_square']:.6f}")
    print(f"P-value:       {verification_result['p_value']:.6f}")
    print(f"Entropy:       {verification_result['entropy_bits']:.6f} bits")
    print()
    
    print(f"Uniform distribution: {'PASS' if verification_result['uniform'] else 'FAIL'}")
    print(f"Verification passed: {'PASS' if verification_result['verification_passed'] else 'FAIL'}")
    
    # Test 3: Compare against expected outcomes
    print("\n3. Comparison Against Expected Outcomes:")
    expected_outcomes = {0: 3, 1: 2}  # Expected 3 tails, 2 heads
    comparison_result = verify_rng_fairness(test_block_hashes, expected_outcomes)
    
    print(f"Matches expected outcomes: {'PASS' if comparison_result['matches_expected'] else 'FAIL'}")
    print(f"Verification passed: {'PASS' if comparison_result['verification_passed'] else 'FAIL'}")
    
    return {
        "statistical_test": result.uniform,
        "deterministic_test": verification_result['verification_passed'],
        "comparison_test": comparison_result['matches_expected']
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        # Run RNG verification tests
        results = run_rng_verification_test()
        print("\n" + "=" * 60)
        print("RNG FAIRNESS VERIFICATION SUMMARY:")
        print(f"Statistical Test: {'PASS' if results['statistical_test'] else 'FAIL'}")
        print(f"Deterministic Test: {'PASS' if results['deterministic_test'] else 'FAIL'}")
        print(f"Comparison Test: {'PASS' if results['comparison_test'] else 'FAIL'}")
        print("=" * 60)
        
        # Exit with appropriate code
        all_passed = all(results.values())
        sys.exit(0 if all_passed else 1)
    else:
        # Default behavior: run simulations
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
