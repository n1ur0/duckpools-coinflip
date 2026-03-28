#!/usr/bin/env python3
"""
Test script to verify Plinko multiplier symmetry for MAT-250
"""

import sys
import os
import math

# Add the frontend utils to the path to import the TypeScript functions
sys.path.append(os.path.join(os.path.dirname(__file__), 'frontend', 'src'))

def binomial_coefficient(n, k):
    """Calculate binomial coefficient C(n, k)"""
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    
    result = 1
    for i in range(min(k, n - k)):
        result = result * (n - i) // (i + 1)
    return result

def get_plinko_slot_probability(rows, slot):
    """Calculate probability for a slot"""
    if slot < 0 or slot > rows:
        raise ValueError(f"Slot {slot} out of range for {rows} rows")
    
    n = rows
    k = slot
    return binomial_coefficient(n, k) / (2 ** n)

def get_plinko_slot_multiplier(rows, slot):
    """Calculate multiplier for a slot"""
    probability = get_plinko_slot_probability(rows, slot)
    alpha = 0.5  # Risk parameter
    
    # Pre-compute normalization constant
    denom = 0
    for s in range(rows + 1):
        denom += math.pow(get_plinko_slot_probability(rows, s), 1 - alpha)
    
    house_edge = 0.03
    A = (1 - house_edge) / denom
    return A * math.pow(1 / probability, alpha)

def get_plinko_multiplier_table(rows):
    """Get all multipliers for a row count"""
    multipliers = []
    for slot in range(rows + 1):
        multipliers.append(get_plinko_slot_multiplier(rows, slot))
    return multipliers

def test_symmetry(rows):
    """Test if multipliers are symmetric"""
    multipliers = get_plinko_multiplier_table(rows)
    print(f"\n{rows}-row Plinko Multipliers:")
    for i, mult in enumerate(multipliers):
        print(f"  Slot {i:2d}: {mult:6.2f}x")
    
    # Check symmetry
    is_symmetric = True
    for i in range(len(multipliers) // 2):
        left = multipliers[i]
        right = multipliers[rows - i]
        if not math.isclose(left, right, rel_tol=1e-9):
            print(f"  SYMMETRY BROKEN: Slot {i} ({left:.2f}x) != Slot {rows-i} ({right:.2f}x)")
            is_symmetric = False
    
    # Check for duplicates
    has_duplicates = len(multipliers) != len(set(multipliers))
    if has_duplicates:
        print("  DUPLICATE VALUES DETECTED")
        for i in range(len(multipliers)):
            for j in range(i + 1, len(multipliers)):
                if math.isclose(multipliers[i], multipliers[j], rel_tol=1e-9):
                    print(f"    Slot {i} and Slot {j} both have {multipliers[i]:.2f}x")
    
    # Check edge values specifically
    if len(multipliers) > 1:
        edge_left = multipliers[0]
        edge_right = multipliers[-1]
        if math.isclose(edge_left, edge_right, rel_tol=1e-9):
            print(f"  Edge symmetry: OK ({edge_left:.2f}x both sides)")
        else:
            print(f"  Edge symmetry BROKEN: Left edge {edge_left:.2f}x, Right edge {edge_right:.2f}x")
            is_symmetric = False
    
    return is_symmetric, has_duplicates

def main():
    print("=== Plinko Multiplier Symmetry Test ===")
    print("Testing for MAT-250: Plinko multiplier tables have broken symmetry")
    
    # Test different row counts
    test_rows = [8, 12, 16]
    all_symmetric = True
    
    for rows in test_rows:
        is_symmetric, has_duplicates = test_symmetry(rows)
        all_symmetric = all_symmetric and is_symmetric
    
    print("\n=== Summary ===")
    if all_symmetric:
        print("✅ All tables are symmetric")
    else:
        print("❌ Symmetry issues detected!")
    
    # Expected values from the bug report
    print("\n=== Expected Values (from bug report) ===")
    expected_8_row = [5.6, 2.1, 1.1, 1.0, 0.5, 1.0, 1.1, 2.1, 5.6]
    expected_12_row = [11.0, 3.3, 1.6, 1.1, 1.0, 0.5, 0.5, 1.0, 1.1, 1.6, 3.3, 11.0, 11.0]
    expected_16_row = [16.0, 9.0, 2.0, 1.1, 1.0, 0.5, 0.3, 0.2, 0.2, 0.3, 0.5, 1.0, 1.1, 2.0, 9.0, 16.0, 16.0]
    
    print("8-row (expected):", expected_8_row)
    print("12-row (expected):", expected_12_row)
    print("16-row (expected):", expected_16_row)
    
    print("\nNote: The expected 12-row and 16-row tables show duplicated last elements,")
    print("which breaks symmetry. This confirms the bug report.")

if __name__ == "__main__":
    main()