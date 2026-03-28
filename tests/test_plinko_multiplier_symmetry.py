#!/usr/bin/env python3
"""
Test suite for Plinko multiplier symmetry verification.

Tests:
1. Symmetry test: multiplier[i] should equal multiplier[rows-i] for all i
2. Edge duplication test: verify no incorrect duplication of edge multipliers
3. Expected value test: verify E[X] = 1 - house_edge = 0.97 (3% house edge)
4. Consistency test: verify all multiplier tables are mathematically consistent
"""

import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from core.plinko_logic import calculate_multipliers, get_expected_value, binomial_probability


def test_symmetry():
    """Test that multiplier tables are perfectly symmetric."""
    print("\n=== Testing Multiplier Symmetry ===")
    
    for rows in [8, 12, 16]:
        print(f"\nTesting {rows}-row table...")
        multipliers = calculate_multipliers(rows)
        
        # Test symmetry: multiplier[i] should equal multiplier[rows-i]
        for i in range(len(multipliers) // 2):
            j = len(multipliers) - 1 - i
            diff = abs(multipliers[i] - multipliers[j])
            
            print(f"  Slot {i:2d} vs {j:2d}: {multipliers[i]:6.3f}x vs {multipliers[j]:6.3f}x (diff: {diff:.10f})")
            
            if diff > 1e-10:
                print(f"❌ FAILED: Asymmetry detected at slot {i}")
                return False
    
    print("✅ PASSED: All tables are perfectly symmetric")
    return True


def test_no_edge_duplication():
    """Test that edge multipliers are not incorrectly duplicated."""
    print("\n=== Testing Edge Multiplier Duplication ===")
    
    for rows in [8, 12, 16]:
        print(f"\nTesting {rows}-row table...")
        multipliers = calculate_multipliers(rows)
        
        # For even rows, there's a middle slot that should only appear once
        slots = rows + 1
        if slots % 2 == 1:
            middle_slot = slots // 2
            middle_multiplier = multipliers[middle_slot]
            
            # Check that the middle slot multiplier appears only once
            count = sum(1 for m in multipliers if abs(m - middle_multiplier) < 1e-10)
            
            print(f"  Middle slot {middle_slot}: {middle_multiplier:.3f}x (appears {count} time(s))")
            
            if count > 1:
                print(f"❌ FAILED: Middle slot multiplier appears {count} times, should be 1")
                return False
        
        # Check that we have the correct number of unique slots
        unique_count = len(set(round(m, 6) for m in multipliers))
        expected_count = (slots + 1) // 2  # Half rounded up due to symmetry
        
        print(f"  Unique multipliers: {unique_count}, Expected: {expected_count}")
        
        if unique_count != expected_count:
            print(f"❌ FAILED: Incorrect number of unique multipliers")
            return False
    
    print("✅ PASSED: No incorrect edge duplications found")
    return True


def test_expected_value():
    """Test that expected value equals 1 - house_edge."""
    print("\n=== Testing Expected Value ===")
    
    house_edge = 0.03
    target_expected = 1 - house_edge
    
    for rows in [8, 12, 16]:
        print(f"\nTesting {rows}-row table...")
        multipliers = calculate_multipliers(rows)
        expected = get_expected_value(multipliers, house_edge)
        
        print(f"  Expected value: {expected:.6f}")
        print(f"  Target value:    {target_expected:.6f}")
        print(f"  Difference:      {abs(expected - target_expected):.6f}")
        
        if abs(expected - target_expected) > 1e-6:
            print(f"❌ FAILED: Expected value differs from target")
            return False
    
    print("✅ PASSED: All expected values correct")
    return True


def test_mathematical_consistency():
    """Test that multiplier tables are mathematically consistent."""
    print("\n=== Testing Mathematical Consistency ===")
    
    for rows in [8, 12, 16]:
        print(f"\nTesting {rows}-row table...")
        multipliers = calculate_multipliers(rows)
        
        # Test that multipliers decrease from edges to center
        for i in range(rows // 2):
            if multipliers[i] < multipliers[i + 1]:
                print(f"❌ FAILED: Multiplier should decrease from edge to center at slot {i}")
                return False
        
        # Test that edge multipliers are the highest
        edge_multiplier = multipliers[0]
        center_multiplier = multipliers[rows // 2]
        
        print(f"  Edge multiplier:   {edge_multiplier:.3f}x")
        print(f"  Center multiplier: {center_multiplier:.3f}x")
        
        if edge_multiplier <= center_multiplier:
            print(f"❌ FAILED: Edge multiplier should be higher than center")
            return False
        
        # Test that all multipliers are positive
        for i, m in enumerate(multipliers):
            if m <= 0:
                print(f"❌ FAILED: Negative or zero multiplier at slot {i}")
                return False
    
    print("✅ PASSED: All tables are mathematically consistent")
    return True


def print_multiplier_tables():
    """Print the current multiplier tables for reference."""
    print("\n" + "=" * 60)
    print("CURRENT MULTIPLIER TABLES")
    print("=" * 60)
    
    for rows in [8, 12, 16]:
        print(f"\n{rows}-row Table:")
        print("-" * 40)
        
        multipliers = calculate_multipliers(rows)
        
        # Print in pairs to show symmetry
        for i in range(len(multipliers) // 2):
            j = len(multipliers) - 1 - i
            if i == j:
                print(f"Slot {i:2d}:   {multipliers[i]:7.2f}x")
            else:
                print(f"Slot {i:2d}:   {multipliers[i]:7.2f}x  Slot {j:2d}:   {multipliers[j]:7.2f}x")
        
        expected = get_expected_value(multipliers)
        print(f"\nExpected Value: {expected:.4f} (target: {(1-0.03):.4f})")
        print(f"House Edge: {(1 - expected) * 100:.2f}%")


def main():
    """Run all tests."""
    print("Plinko Multiplier Symmetry Test Suite")
    print("=" * 50)
    
    tests = [
        test_symmetry,
        test_no_edge_duplication,
        test_expected_value,
        test_mathematical_consistency
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ FAILED: {test.__name__} threw exception: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("❌ SOME TESTS FAILED")
        return 1
    else:
        print("✅ ALL TESTS PASSED")
        print_multiplier_tables()
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)