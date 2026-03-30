#!/usr/bin/env python3
"""
Comprehensive RNG Fairness Verification Script

This script verifies the RNG fairness implementation in the DuckPools coinflip contract
by testing both the smart contract implementation and the backend RNG module.
"""

import hashlib
import random
import os
import sys
import json
from typing import Dict, List, Tuple

# Add the backend directory to the path so we can import rng_module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from rng_module import compute_rng, generate_commit, verify_commit, run_comprehensive_rng_verification


def test_commit_reveal_consistency():
    """Test that commitment and reveal are consistent"""
    print("\nTesting Commit-Reveal Consistency...")
    
    secret_length=8
    num_tests = 100
    
    for i in range(num_tests):
        # Generate random secret and choice
        secret_bytes=bytes(random.getrandbits(8) for _ in range(secret_length))
        choice = random.randint(0, 1)
        
        # Generate commitment
        commitment = generate_commit(secret_bytes, choice)
        
        # Verify commitment (should always pass)
        assert verify_commit(commitment, secret_bytes, choice), f"Commitment verification failed for test {i+1}"
        
        print(f"Test {i+1}/{num_tests}: PASSED")
    
    print("All commit-reveal consistency tests passed!")
    return True


def test_rng_distribution():
    """Test RNG distribution fairness"""
    print("\nTesting RNG Distribution Fairness...")
    
    num_tests = 100000
    secret_length=8
    
    outcomes = []
    
    for i in range(num_tests):
        # Generate random secret
        secret_bytes=bytes(random.getrandbits(8) for _ in range(secret_length))
        choice = random.randint(0, 1)
        
        # Generate commitment
        commitment = generate_commit(secret_bytes, choice)
        
        # Verify commitment
        assert verify_commit(commitment, secret_bytes, choice), "Commitment verification failed"
        
        # Compute RNG outcome
        # For testing, we'll use a fixed block hash
        block_hash = "a" * 64  # 64 hex characters = 32 bytes
        outcome = compute_rng(block_hash, secret_bytes)
        outcomes.append(outcome)
    
    # Statistical analysis
    heads_count = outcomes.count(0)
    tails_count = outcomes.count(1)
    total = len(outcomes)
    
    heads_ratio = heads_count / total
    tails_ratio = tails_count / total
    
    print(f"\nStatistical Analysis (n={total}):")
    print(f"Heads: {heads_count} ({heads_ratio:.4%})")
    print(f"Tails: {tails_count} ({tails_ratio:.4%})")
    
    # Check if distribution is approximately uniform (within 5% deviation)
    acceptable_deviation = 0.05
    heads_deviation = abs(heads_ratio - 0.5)
    tails_deviation = abs(tails_ratio - 0.5)
    
    print(f"Heads deviation from 50%: {heads_deviation:.4%}")
    print(f"Tails deviation from 50%: {tails_deviation:.4%}")
    
    is_fair = (heads_deviation < acceptable_deviation and 
              tails_deviation < acceptable_deviation)
    
    print(f"\nRNG Fairness: {'PASSED' if is_fair else 'FAILED'}")
    print(f"Acceptable deviation: ±{acceptable_deviation:.0%}")
    
    if not is_fair:
        print("\nWARNING: RNG may not be fair!")
        print("Consider increasing test size or investigating the RNG implementation.")
    
    return is_fair


def test_rng_entropy():
    """Test RNG entropy quality"""
    print("\nTesting RNG Entropy Quality...")
    
    num_tests = 1000
    secret_length=8
    
    entropy_bits_list = []
    
    for i in range(num_tests):
        # Generate random secret
        secret_bytes=bytes(random.getrandbits(8) for _ in range(secret_length))
        
        # Compute RNG outcome
        block_hash = "a" * 64
        outcome = compute_rng(block_hash, secret_bytes)
        
        # Calculate entropy of the outcome
        # For a single bit, entropy is 1 if perfectly random
        # Use a more sophisticated entropy calculation
        if outcome == 0:
            entropy = 0.0  # Certain outcome has 0 entropy
        else:
            entropy = 1.0  # Random outcome has 1 bit of entropy
        
        entropy_bits_list.append(entropy)
    
    avg_entropy = sum(entropy_bits_list) / len(entropy_bits_list)
    
    print(f"Average entropy: {avg_entropy:.4f} bits (max 1.0)")
    
    # Acceptable entropy threshold (should be close to 1.0 for good RNG)
    is_good_entropy = avg_entropy > 0.9
    
    print(f"Entropy quality: {'GOOD' if is_good_entropy else 'POOR'}")
    
    return is_good_entropy


def verify_contract_implementation():
    """Verify that the smart contract implements RNG correctly"""
    print("\nVerifying Smart Contract RNG Implementation...")
    
    # Read the smart contract
    contract_path = os.path.join(os.path.dirname(__file__), 'smart-contracts', 'coinflip_v1.es')
    with open(contract_path, 'r') as f:
        contract_code = f.read()
    
    # Run comprehensive verification
    verification_results = run_comprehensive_rng_verification(contract_code=contract_code)
    
    contract_analysis = verification_results['contract_analysis']
    statistical_testing = verification_results['statistical_testing']
    
    print("\nContract Analysis Results:")
    for key, value in contract_analysis.items():
        status = "PRESENT" if value else "MISSING"
        print(f"  {key}: {status}")
    
    print("\nStatistical Testing Results:")
    for key, value in statistical_testing.items():
        if key != 'verification_passed':
            print(f"  {key}: {value}")
    
    contract_valid = contract_analysis.get('contract_valid', False)
    statistical_passed = statistical_testing.get('verification_passed', False)
    
    print(f"\nContract Valid: {'PASS' if contract_valid else 'FAIL'}")
    print(f"Statistical Test Passed: {'PASS' if statistical_passed else 'FAIL'}")
    
    return contract_valid and statistical_passed


def run_comprehensive_verification():
    """Run all RNG fairness verification tests"""
    print("DuckPools RNG Fairness Comprehensive Verification")
    print("=" * 60)
    
    # Run tests
    consistency_passed = test_commit_reveal_consistency()
    distribution_passed = test_rng_distribution()
    entropy_passed = test_rng_entropy()
    contract_passed = verify_contract_implementation()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"Commit-Reveal Consistency: {'PASSED' if consistency_passed else 'FAILED'}")
    print(f"RNG Distribution Fairness: {'PASSED' if distribution_passed else 'FAILED'}")
    print(f"RNG Entropy Quality: {'PASSED' if entropy_passed else 'FAILED'}")
    print(f"Contract Implementation: {'PASSED' if contract_passed else 'FAILED'}")
    
    all_passed = consistency_passed and distribution_passed and entropy_passed and contract_passed
    
    if all_passed:
        print("\nAll RNG fairness tests passed!")
        return True
    else:
        print("\nSome RNG fairness tests failed!")
        return False


if __name__ == "__main__":
    success = run_comprehensive_verification()
    sys.exit(0 if success else 1)