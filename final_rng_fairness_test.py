#!/usr/bin/env python3
"""
Final comprehensive test for RNG fairness verification implementation
"""

import hashlib
import random
import os
import sys
from typing import Dict, List, Tuple

# Add the backend directory to the path so we can import rng_module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from rng_module import compute_rng, generate_commit, verify_commit, run_comprehensive_rng_verification


def test_rng_fairness_implementation():
    """Test the RNG fairness implementation in the contract"""
    print("DuckPools RNG Fairness Verification - Final Test")
    print("=" * 60)
    
    # Test 1: Contract compilation and basic structure
    print("\n1. Contract Structure Verification:")
    contract_path = os.path.join(os.path.dirname(__file__), 'smart-contracts', 'coinflip_v3.es')
    with open(contract_path, 'r') as f:
        contract_code = f.read()
    
    # Run contract analysis
    contract_analysis = run_comprehensive_rng_verification(contract_code=contract_code)['contract_analysis']
    
    print("Contract Analysis Results:")
    for key, value in contract_analysis.items():
        status = "PASS" if value else "FAIL"
        print(f"  {key}: {status}")
    
    contract_valid = contract_analysis.get('contract_valid', False)
    print(f"\nContract Valid: {'PASS' if contract_valid else 'FAIL'}")
    
    # Test 2: Commit-reveal consistency
    print("\n2. Commit-Reveal Consistency Testing:")
    secret_length = 8
    num_tests = 100
    passed_tests = 0
    
    for i in range(num_tests):
        secret_bytes = bytes(random.getrandbits(8) for _ in range(secret_length))
        choice = random.randint(0, 1)
        
        commitment = generate_commit(secret_bytes, choice)
        assert verify_commit(commitment, secret_bytes, choice), f"Commitment verification failed for test {i+1}"
        
        wrong_choice = 1 - choice
        assert not verify_commit(commitment, secret_bytes, wrong_choice), f"Commitment should not verify with wrong choice for test {i+1}"
        
        print(f"  Test {i+1}/{num_tests}: PASSED")
        passed_tests += 1
    
    print(f"  All {passed_tests}/{num_tests} commit-reveal tests passed!")
    
    # Test 3: RNG distribution fairness
    print("\n3. RNG Distribution Fairness Testing:")
    num_tests = 100000
    outcomes = []
    
    for i in range(num_tests):
        secret_bytes = bytes(random.getrandbits(8) for _ in range(secret_length))
        choice = random.randint(0, 1)
        commitment = generate_commit(secret_bytes, choice)
        assert verify_commit(commitment, secret_bytes, choice)
        
        block_hash = "a" * 64
        outcome = compute_rng(block_hash, secret_bytes)
        outcomes.append(outcome)
    
    heads_count = outcomes.count(0)
    tails_count = outcomes.count(1)
    total = len(outcomes)
    
    heads_ratio = heads_count / total
    tails_ratio = tails_count / total
    
    print(f"  Total outcomes: {total:,}")
    print(f"  Heads: {heads_count:,} ({heads_ratio:.4%})")
    print(f"  Tails: {tails_count:,} ({tails_ratio:.4%})")
    
    acceptable_deviation = 0.05
    heads_deviation = abs(heads_ratio - 0.5)
    tails_deviation = abs(tails_ratio - 0.5)
    
    print(f"  Heads deviation from 50%: {heads_deviation:.4%}")
    print(f"  Tails deviation from 50%: {tails_deviation:.4%}")
    
    is_fair = (heads_deviation < acceptable_deviation and 
              tails_deviation < acceptable_deviation)
    
    print(f"  RNG Fairness: {'PASS' if is_fair else 'FAIL'}")
    print(f"  Acceptable deviation: ±{acceptable_deviation:.0%}")
    
    # Test 4: RNG verification implementation
    print("\n4. RNG Verification Implementation:")
    
    # Check that the contract has the necessary components
    required_components = [
        "blake2b256_usage",
        "block_hash_usage", 
        "secret_handling",
        "commitment_verification",
        "rng_verification_path",
        "register_usage",
        "commitment_register"
    ]
    
    missing_components = [comp for comp in required_components if not contract_analysis.get(comp, False)]
    
    if missing_components:
        print(f"  Missing components: {', '.join(missing_components)}")
        print("  RNG verification implementation: FAIL")
    else:
        print("  All required RNG verification components present")
        print("  RNG verification implementation: PASS")
    
    # Overall result
    all_passed = contract_valid and is_fair and (not missing_components)
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS:")
    print(f"Contract Structure: {'PASS' if contract_valid else 'FAIL'}")
    print(f"Commit-Reveal Consistency: {'PASS' if passed_tests == num_tests else 'FAIL'}")
    print(f"RNG Distribution Fairness: {'PASS' if is_fair else 'FAIL'}")
    print(f"RNG Verification Implementation: {'PASS' if not missing_components else 'FAIL'}")
    print(f"Overall RNG Fairness Verification: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = test_rng_fairness_implementation()
    sys.exit(0 if success else 1)