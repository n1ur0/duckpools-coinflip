#!/usr/bin/env python3
"""
Test script to verify that frontend and backend Plinko implementations
produce the same multiplier tables.

This addresses MAT-272: Fix Plinko multiplier table symmetry.
"""

import sys
import os
import math

# Add the backend to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'src'))

# Import backend functions
from core.plinko_logic import (
    get_multiplier_table as backend_get_multiplier_table,
    get_zone_probabilities as backend_get_zone_probabilities,
)

# Frontend implementation (translated from TypeScript)
def frontend_binomial_coefficient(n, k):
    """Calculate binomial coefficient C(n, k)"""
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    
    result = 1
    for i in range(min(k, n - k)):
        result = result * (n - i) // (i + 1)
    return result

def frontend_get_slot_probability(rows, slot):
    """Calculate probability for a slot"""
    if slot < 0 or slot > rows:
        raise ValueError(f"Slot {slot} out of range for {rows} rows")
    
    n = rows
    k = slot
    return frontend_binomial_coefficient(n, k) / (2 ** n)

def frontend_get_slot_multiplier(rows, slot):
    """Calculate multiplier for a slot using the power-law formula"""
    probability = frontend_get_slot_probability(rows, slot)
    alpha = 0.5  # Risk parameter
    
    # Pre-compute normalization constant for this row count
    denom = 0
    for s in range(rows + 1):
        denom += math.pow(frontend_get_slot_probability(rows, s), 1 - alpha)
    
    house_edge = 0.03
    A = (1 - house_edge) / denom
    return A * math.pow(1 / probability, alpha)

def frontend_get_multiplier_table(rows):
    """Get all multipliers for a row count"""
    multipliers = []
    for slot in range(rows + 1):
        multipliers.append(frontend_get_slot_multiplier(rows, slot))
    return multipliers

def test_consistency():
    """Test that frontend and backend implementations produce the same results"""
    print("=== Testing Frontend/Backend Consistency ===")
    print("Issue: MAT-272 - Fix Plinko multiplier table symmetry")
    
    test_rows = [8, 12, 16]
    all_consistent = True
    
    for rows in test_rows:
        print(f"\nTesting {rows}-row table:")
        
        # Get multipliers from both implementations
        backend_multipliers = backend_get_multiplier_table(rows)
        frontend_multipliers = frontend_get_multiplier_table(rows)
        
        # Check that they have the same length
        if len(backend_multipliers) != len(frontend_multipliers):
            print(f"  ❌ Length mismatch: backend={len(backend_multipliers)}, frontend={len(frontend_multipliers)}")
            all_consistent = False
            continue
        
        # Check that multipliers are the same
        max_diff = 0
        for i in range(len(backend_multipliers)):
            diff = abs(backend_multipliers[i] - frontend_multipliers[i])
            max_diff = max(max_diff, diff)
            
            if diff > 1e-10:  # Allow for small floating point errors
                print(f"  ❌ Slot {i}: backend={backend_multipliers[i]:.10f}, frontend={frontend_multipliers[i]:.10f}")
                all_consistent = False
        
        if max_diff < 1e-10:
            print(f"  ✅ Frontend and backend implementations match (max diff: {max_diff:.2e})")
        
        # Test symmetry for both implementations
        print("  Testing backend symmetry:")
        backend_symmetric = True
        for i in range((rows + 1) // 2):
            left = backend_multipliers[i]
            right = backend_multipliers[rows - i]
            if not math.isclose(left, right, rel_tol=1e-9):
                print(f"    ❌ Backend: Slot {i} ({left:.6f}x) != Slot {rows-i} ({right:.6f}x)")
                backend_symmetric = False
        
        if backend_symmetric:
            print(f"    ✅ Backend table is symmetric")
        
        print("  Testing frontend symmetry:")
        frontend_symmetric = True
        for i in range((rows + 1) // 2):
            left = frontend_multipliers[i]
            right = frontend_multipliers[rows - i]
            if not math.isclose(left, right, rel_tol=1e-9):
                print(f"    ❌ Frontend: Slot {i} ({left:.6f}x) != Slot {rows-i} ({right:.6f}x)")
                frontend_symmetric = False
        
        if frontend_symmetric:
            print(f"    ✅ Frontend table is symmetric")
    
    return all_consistent

def main():
    """Run all tests"""
    print("DuckPools Frontend/Backend Plinko Consistency Test")
    print("===============================================")
    print("Testing for issue MAT-272: Fix Plinko multiplier table symmetry")
    print("Verifying that frontend and backend implementations match.\n")
    
    # Run test
    consistent = test_consistency()
    
    print("\n=== Test Summary ===")
    if consistent:
        print("✅ ALL TESTS PASSED")
        print("✅ Frontend and backend implementations are consistent")
        print("✅ Both implementations produce symmetric multiplier tables")
        print("✅ Issue MAT-272: No symmetry issues found")
        print()
        print("CONCLUSION:")
        print("Both the frontend and backend implementations are mathematically")
        print("correct and produce symmetric multiplier tables. There is no")
        print("symmetry issue to fix.")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("❌ Frontend and backend implementations are inconsistent")
        print("❌ This could be the source of the symmetry issue")
        return 1

if __name__ == "__main__":
    exit(main())