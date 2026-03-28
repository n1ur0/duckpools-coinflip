"""
Tests for the RNG Statistical Test Suite
========================================

This file tests the RNG statistical test suite implementation
to ensure it works correctly and produces expected results.
"""

import sys
import os

# Add the current directory to the path so we can import rng_statistical_suite
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rng_statistical_suite import RNGStatisticalSuite, RNGTestResult, RNGTestSuiteResult
import secrets

def test_rng_outcome_computation():
    """Test that RNG outcomes are computed correctly."""
    suite = RNGStatisticalSuite()
    
    # Test with known inputs
    block_hash = "00000000000000000007a7a86f2f6c6e6d6f6e65797374656d"
    secret = b'\x01\x02\x03\x04\x05\x06\x07\x08'
    
    # Compute outcome
    outcome = suite.compute_rng_outcome(block_hash, secret)
    
    # Should be 0 or 1
    assert outcome in [0, 1], f"Expected outcome to be 0 or 1, got {outcome}"
    
    # Test with same inputs (should produce same result)
    outcome2 = suite.compute_rng_outcome(block_hash, secret)
    assert outcome == outcome2, f"Expected same outcome for same inputs, got {outcome} and {outcome2}"
    
    # Test with different secret (should produce different result)
    different_secret = b'\x08\x07\x06\x05\x04\x03\x02\x01'
    outcome3 = suite.compute_rng_outcome(block_hash, different_secret)
    
    # Note: We don't test that outcome != outcome3 because they could be the same by chance
    # The important thing is that the function is deterministic
    
    print("✓ RNG outcome computation test passed")

def test_chi_square_test():
    """Test the chi-square test implementation."""
    suite = RNGStatisticalSuite()
    
    # Test with perfectly uniform distribution
    perfect_uniform = [0, 1] * 50  # Exactly 50% heads, 50% tails
    result = suite.chi_square_test(perfect_uniform)
    
    # Should pass with flying colors
    assert result.passed, "Perfectly uniform distribution should pass chi-square test"
    assert result.test_name == "Chi-square Test (Uniformity)"
    assert 0 <= result.p_value <= 1, f"P-value should be between 0 and 1, got {result.p_value}"
    assert result.details['observed_heads'] == 50
    assert result.details['observed_tails'] == 50
    
    # Test with extremely biased distribution
    extreme_bias = [0] * 100  # All heads
    result = suite.chi_square_test(extreme_bias)
    
    # Should fail
    assert not result.passed, "Extremely biased distribution should fail chi-square test"
    assert result.details['observed_heads'] == 100
    assert result.details['observed_tails'] == 0
    
    print("✓ Chi-square test passed")

def test_runs_test():
    """Test the runs test implementation."""
    suite = RNGStatisticalSuite()
    
    # Test with alternating pattern (should have maximum runs)
    alternating = [0, 1] * 50
    result = suite.runs_test(alternating)
    
    # Should fail because too many runs indicates non-randomness
    assert not result.passed, "Alternating pattern should fail runs test"
    assert result.test_name == "Wald-Wolfowitz Runs Test (Independence)"
    assert result.details['runs_count'] == 100  # Each change is a new run
    
    # Test with all same values (minimum runs)
    all_same = [0] * 100
    result = suite.runs_test(all_same)
    
    # Should fail because too few runs indicates non-randomness
    assert not result.passed, "All same values should fail runs test"
    assert result.details['runs_count'] == 1
    
    # Test with random-looking data
    random_like = [1, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 1, 1] * 5
    result = suite.runs_test(random_like)
    
    # This might pass or fail, but we can check the structure
    assert result.test_name == "Wald-Wolfowitz Runs Test (Independence)"
    assert isinstance(result.passed, bool)
    assert result.details['heads_count'] + result.details['tails_count'] == len(random_like)
    
    print("✓ Runs test passed")

def test_frequency_test():
    """Test the frequency test implementation."""
    suite = RNGStatisticalSuite()
    
    # Test with perfectly uniform distribution
    perfect_uniform = [0, 1] * 50
    result = suite.frequency_test(perfect_uniform)
    
    # Should pass
    assert result.passed, "Perfectly uniform distribution should pass frequency test"
    assert result.test_name == "Frequency Test (Monobit)"
    assert result.details['count_ones'] == 50
    assert result.details['count_zeros'] == 50
    assert result.details['proportion_ones'] == 0.5
    assert result.details['proportion_zeros'] == 0.5
    
    # Test with extreme bias
    extreme_bias = [0] * 100
    result = suite.frequency_test(extreme_bias)
    
    # Should fail
    assert not result.passed, "Extreme bias should fail frequency test"
    assert result.details['count_ones'] == 0
    assert result.details['count_zeros'] == 100
    
    print("✓ Frequency test passed")

def test_simulate_outcomes():
    """Test the outcome simulation functionality."""
    suite = RNGStatisticalSuite()
    
    # Test simulation
    outcomes = suite.simulate_outcomes(1000)
    
    # Check length
    assert len(outcomes) == 1000, f"Expected 1000 outcomes, got {len(outcomes)}"
    
    # Check all values are 0 or 1
    assert all(outcome in [0, 1] for outcome in outcomes), "All outcomes should be 0 or 1"
    
    # Test with custom block hashes
    block_hashes = ["a" * 64, "b" * 64, "c" * 64]
    outcomes = suite.simulate_outcomes(10, block_hashes)
    
    assert len(outcomes) == 10, f"Expected 10 outcomes, got {len(outcomes)}"
    assert all(outcome in [0, 1] for outcome in outcomes), "All outcomes should be 0 or 1"
    
    print("✓ Outcome simulation test passed")

def test_run_all_tests():
    """Test running all tests together."""
    suite = RNGStatisticalSuite()
    
    # Generate random outcomes
    outcomes = suite.simulate_outcomes(10000)
    
    # Run all tests
    results = suite.run_all_tests(outcomes)
    
    # Check structure
    assert isinstance(results, RNGTestSuiteResult)
    assert results.total_tests > 0
    assert results.passed_tests + results.failed_tests == results.total_tests
    assert isinstance(results.overall_passed, bool)
    assert isinstance(results.summary, str)
    assert len(results.test_results) == results.total_tests
    
    # Check that each test result has the right structure
    for test_result in results.test_results:
        assert isinstance(test_result, RNGTestResult)
        assert isinstance(test_result.test_name, str)
        assert isinstance(test_result.statistic, (int, float))
        assert 0 <= test_result.p_value <= 1
        assert isinstance(test_result.passed, bool)
        assert 0 < test_result.alpha < 1
    
    print("✓ Run all tests test passed")

def main():
    """Run all tests."""
    print("Running RNG Statistical Test Suite Tests...")
    print("=" * 50)
    
    try:
        test_rng_outcome_computation()
        test_chi_square_test()
        test_runs_test()
        test_frequency_test()
        test_simulate_outcomes()
        test_run_all_tests()
        
        print("=" * 50)
        print("All tests passed! ✓")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())