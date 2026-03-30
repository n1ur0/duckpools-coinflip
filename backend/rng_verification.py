"""
RNG Fairness Verification Module - Implements comprehensive RNG verification

This module implements verification of the RNG implementation against the on-chain contract
and statistical fairness testing to ensure the RNG cannot be manipulated and produces
truly random outcomes.
"""

import hashlib
import math
import random
import os
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass
from rng_module import compute_rng, generate_commit, verify_commit, RNGTestResult, simulate_coinflip


@dataclass
class RNGVerificationResult:
    """Results of RNG verification testing."""
    is_contract_match: bool
    is_fair: bool
    statistical_test: RNGTestResult
    vulnerabilities_found: List[str]
    recommendations: List[str]


def test_contract_match() -> bool:
    """
    Test that the off-chain RNG implementation matches the on-chain contract exactly.
    
    Returns:
        bool: True if implementations match, False otherwise
    """
    # Test 1: Verify compute_rng function matches on-chain contract logic
    # On-chain: blake2b256(blockId_raw_bytes || playerSecret_raw_bytes)[0] % 2
    # Off-chain: Same logic implemented in compute_rng()
    
    # Generate test data
    test_block_hash = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"
    test_secret = os.urandom(8)  # 8 random bytes
    
    # Compute using our off-chain implementation
    offchain_result = compute_rng(test_block_hash, test_secret)
    
    # Simulate on-chain computation (same logic)
    block_hash_bytes = bytes.fromhex(test_block_hash)
    rng_data = block_hash_bytes + test_secret
    rng_hash = hashlib.blake2b(rng_data, digest_size=32).digest()
    onchain_result = rng_hash[0] % 2
    
    return offchain_result == onchain_result


def test_commit_reveal_consistency() -> bool:
    """
    Test that commit and reveal operations are consistent.
    
    Returns:
        bool: True if commit-reveal is consistent, False otherwise
    """
    # Generate random test data
    secret = os.urandom(8)
    choice = random.choice([0, 1])
    
    # Generate commitment
    commit = generate_commit(secret, choice)
    
    # Verify commitment
    is_valid = verify_commit(commit, secret, choice)
    
    return is_valid


def test_edge_cases() -> List[str]:
    """
    Test edge cases and potential vulnerabilities in RNG implementation.
    
    Returns:
        List[str]: List of vulnerabilities found
    """
    vulnerabilities = []
    
    # Test 1: Test with all-zero secret
    secret_zero = bytes([0] * 8)
    choice = 0
    commit = generate_commit(secret_zero, choice)
    is_valid = verify_commit(commit, secret_zero, choice)
    if not is_valid:
        vulnerabilities.append("Commit-reveal fails with zero secret")
    
    # Test 2: Test with maximum secret value
    secret_max = bytes([255] * 8)
    choice = 1
    commit = generate_commit(secret_max, choice)
    is_valid = verify_commit(commit, secret_max, choice)
    if not is_valid:
        vulnerabilities.append("Commit-reveal fails with max secret")
    
    # Test 3: Test with invalid secret length
    secret_invalid = os.urandom(7)  # 7 bytes instead of 8
    try:
        generate_commit(secret_invalid, 0)
        vulnerabilities.append("No validation for invalid secret length")
    except ValueError:
        pass  # Expected behavior
    
    # Test 4: Test with invalid choice
    secret_valid = os.urandom(8)
    try:
        generate_commit(secret_valid, 2)  # Invalid choice (not 0 or 1)
        vulnerabilities.append("No validation for invalid choice")
    except ValueError:
        pass  # Expected behavior
    
    return vulnerabilities


def run_fairness_verification(num_simulations: int = 100000) -> RNGVerificationResult:
    """
    Run comprehensive RNG fairness verification.
    
    Args:
        num_simulations: Number of simulations to run for statistical testing
        
    Returns:
        RNGVerificationResult: Complete verification results
    """
    vulnerabilities = []
    recommendations = []
    
    # Test 1: Contract match verification
    contract_match = test_contract_match()
    if not contract_match:
        vulnerabilities.append("Off-chain RNG does not match on-chain contract")
        recommendations.append("Fix compute_rng() to match on-chain logic exactly")
    
    # Test 2: Commit-reveal consistency
    commit_reveal_ok = test_commit_reveal_consistency()
    if not commit_reveal_ok:
        vulnerabilities.append("Commit-reveal scheme is inconsistent")
        recommendations.append("Fix generate_commit() or verify_commit() implementation")
    
    # Test 3: Edge case testing
    edge_case_vulnerabilities = test_edge_cases()
    vulnerabilities.extend(edge_case_vulnerabilities)
    
    # Test 4: Statistical fairness testing
    statistical_test = simulate_coinflip(num_simulations)
    is_fair = statistical_test.uniform
    
    # Add recommendations based on statistical results
    if not statistical_test.uniform:
        recommendations.append("RNG output is not uniformly distributed")
        recommendations.append("Consider adding more entropy sources or reviewing RNG implementation")
    
    if statistical_test.p_value <= 0.01:
        recommendations.append("Statistical test shows significant deviation from uniform distribution")
    
    if abs(statistical_test.heads_ratio - 0.5) > 0.02:
        recommendations.append("Heads ratio significantly deviates from 50%")
    
    if statistical_test.entropy_bits < 0.99:
        recommendations.append("Entropy is below acceptable threshold for fair coinflip")
    
    # Add general recommendations
    if not vulnerabilities and is_fair:
        recommendations.append("RNG implementation appears fair and secure")
        recommendations.append("Consider periodic re-verification in production")
    
    return RNGVerificationResult(
        is_contract_match=contract_match,
        is_fair=is_fair,
        statistical_test=statistical_test,
        vulnerabilities_found=vulnerabilities,
        recommendations=recommendations
    )


def print_verification_report(result: RNGVerificationResult) -> None:
    """Print a human-readable verification report."""
    print("\n" + "=" * 80)
    print("RNG FAIRNESS VERIFICATION REPORT")
    print("=" * 80)
    
    print(f"\nContract Match: {'PASS' if result.is_contract_match else 'FAIL'}")
    print(f"Statistical Fairness: {'PASS' if result.is_fair else 'FAIL'}")
    
    print("\nSTATISTICAL TEST RESULTS:")
    print(f"  Total outcomes: {result.statistical_test.total_outcomes:,}")
    print(f"  Heads count:    {result.statistical_test.heads_count:,} ({result.statistical_test.heads_ratio:.4%})")
    print(f"  Tails count:    {result.statistical_test.tails_count:,} ({result.statistical_test.tails_ratio:.4%})")
    print(f"  Chi-square:     {result.statistical_test.chi_square:.6f}")
    print(f"  P-value:       {result.statistical_test.p_value:.6f}")
    print(f"  Entropy:       {result.statistical_test.entropy_bits:.6f} bits")
    print(f"  Uniform:       {'PASS' if result.statistical_test.uniform else 'FAIL'}")
    
    print("\nACCEPTANCE CRITERIA:")
    print(f"  [ ] P-value > 0.01: {'PASS' if result.statistical_test.p_value > 0.01 else 'FAIL'}")
    print(f"  [ ] Heads ratio ~50%: {'PASS' if abs(result.statistical_test.heads_ratio - 0.5) < 0.02 else 'FAIL'}")
    print(f"  [ ] Entropy ~1.0 bits: {'PASS' if result.statistical_test.entropy_bits > 0.99 else 'FAIL'}")
    
    if result.vulnerabilities_found:
        print("\nVULNERABILITIES FOUND:")
        for i, vulnerability in enumerate(result.vulnerabilities_found, 1):
            print(f"  {i}. {vulnerability}")
    
    if result.recommendations:
        print("\nRECOMMENDATIONS:")
        for i, recommendation in enumerate(result.recommendations, 1):
            print(f"  {i}. {recommendation}")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    # Run verification with default number of simulations
    verification_result = run_fairness_verification()
    print_verification_report(verification_result)