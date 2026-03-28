#!/usr/bin/env python3
"""
Test suite for the RNG Statistical Suite

Tests the comprehensive RNG statistical test suite implementation.
"""

import pytest
import sys
import os

# Add the backend directory to Python path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from rng_statistical_suite import RNGStatisticalSuite, RNGTestResult, RNGTestSuiteResult


class TestRNGStatisticalSuite:
    """Test cases for the RNG Statistical Suite."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.suite = RNGStatisticalSuite(alpha=0.05)  # Use higher alpha for tests
        self.test_outcomes = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]  # Small test sequence
    
    def test_compute_rng_outcome(self):
        """Test the core RNG computation."""
        # Test with known inputs
        block_hash = "abcd1234"
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        
        outcome = self.suite.compute_rng_outcome(block_hash, secret)
        
        # Should return either 0 or 1
        assert outcome in [0, 1]
        
        # Same inputs should produce same output
        assert outcome == self.suite.compute_rng_outcome(block_hash, secret)
        
        # Different secrets should produce potentially different outputs
        secret2 = bytes([8, 7, 6, 5, 4, 3, 2, 1])
        outcome2 = self.suite.compute_rng_outcome(block_hash, secret2)
        assert outcome2 in [0, 1]
    
    def test_compute_rng_outcome_invalid_secret(self):
        """Test that invalid secret length raises error."""
        block_hash = "abcd1234"
        invalid_secret = bytes([1, 2, 3])  # Only 3 bytes
        
        with pytest.raises(ValueError, match="Secret must be 8 bytes"):
            self.suite.compute_rng_outcome(block_hash, invalid_secret)
    
    def test_simulate_outcomes(self):
        """Test outcome simulation."""
        num_outcomes = 100
        outcomes = self.suite.simulate_outcomes(num_outcomes)
        
        # Should return correct number of outcomes
        assert len(outcomes) == num_outcomes
        
        # All outcomes should be 0 or 1
        assert all(outcome in [0, 1] for outcome in outcomes)
    
    def test_simulate_outcomes_with_block_hashes(self):
        """Test outcome simulation with provided block hashes."""
        block_hashes = ["aaaa1111", "bbbb2222", "cccc3333"]
        num_outcomes = 10
        
        outcomes = self.suite.simulate_outcomes(num_outcomes, block_hashes)
        
        # Should return correct number of outcomes
        assert len(outcomes) == num_outcomes
        
        # All outcomes should be 0 or 1
        assert all(outcome in [0, 1] for outcome in outcomes)
    
    def test_frequency_test(self):
        """Test the frequency test (monobit test)."""
        result = self.suite.frequency_test(self.test_outcomes)
        
        # Should return a valid test result
        assert isinstance(result, RNGTestResult)
        assert result.test_name == "Frequency Test (Monobit)"
        assert isinstance(result.statistic, float)
        assert 0 <= result.p_value <= 1
        assert isinstance(result.passed, bool)
    
    def test_chi_square_test(self):
        """Test the chi-square test."""
        result = self.suite.chi_square_test(self.test_outcomes)
        
        # Should return a valid test result
        assert isinstance(result, RNGTestResult)
        assert result.test_name == "Chi-square Test (Uniformity)"
        assert isinstance(result.statistic, float)
        assert 0 <= result.p_value <= 1
        assert isinstance(result.passed, bool)
    
    def test_runs_test(self):
        """Test the Wald-Wolfowitz runs test."""
        result = self.suite.runs_test(self.test_outcomes)
        
        # Should return a valid test result
        assert isinstance(result, RNGTestResult)
        assert result.test_name == "Wald-Wolfowitz Runs Test (Independence)"
        assert isinstance(result.statistic, float)
        assert 0 <= result.p_value <= 1
        assert isinstance(result.passed, bool)
    
    def test_kolmogorov_smirnov_test(self):
        """Test the Kolmogorov-Smirnov test."""
        result = self.suite.kolmogorov_smirnov_test(self.test_outcomes)
        
        # Should return a valid test result
        assert isinstance(result, RNGTestResult)
        assert result.test_name == "Kolmogorov-Smirnov Test"
        assert isinstance(result.statistic, float)
        assert 0 <= result.p_value <= 1
        assert isinstance(result.passed, bool)
    
    def test_autocorrelation_test(self):
        """Test the autocorrelation test."""
        result = self.suite.autocorrelation_test(self.test_outcomes, lag=1)
        
        # Should return a valid test result
        assert isinstance(result, RNGTestResult)
        assert "Autocorrelation Test" in result.test_name
        assert isinstance(result.statistic, float)
        assert 0 <= result.p_value <= 1
        assert isinstance(result.passed, bool)
    
    def test_serial_test(self):
        """Test the serial test."""
        result = self.suite.serial_test(self.test_outcomes, pattern_length=2)
        
        # Should return a valid test result
        assert isinstance(result, RNGTestResult)
        assert "Serial Test" in result.test_name
        assert isinstance(result.statistic, float)
        assert 0 <= result.p_value <= 1
        assert isinstance(result.passed, bool)
    
    def test_poker_test(self):
        """Test the poker test."""
        result = self.suite.poker_test(self.test_outcomes, hand_size=4)
        
        # Should return a valid test result
        assert isinstance(result, RNGTestResult)
        assert "Poker Test" in result.test_name
        assert isinstance(result.statistic, float)
        assert 0 <= result.p_value <= 1
        assert isinstance(result.passed, bool)
    
    def test_run_all_tests(self):
        """Test running all statistical tests."""
        # Generate more data for meaningful tests
        large_outcomes = self.suite.simulate_outcomes(1000)
        
        result = self.suite.run_all_tests(large_outcomes)
        
        # Should return a valid test suite result
        assert isinstance(result, RNGTestSuiteResult)
        assert result.total_tests > 0
        assert 0 <= result.passed_tests <= result.total_tests
        assert 0 <= result.failed_tests <= result.total_tests
        assert result.passed_tests + result.failed_tests == result.total_tests
        assert isinstance(result.overall_passed, bool)
        assert isinstance(result.summary, str)
        assert len(result.test_results) == result.total_tests
        
        # All individual test results should be RNGTestResult objects
        for test_result in result.test_results:
            assert isinstance(test_result, RNGTestResult)
    
    def test_print_test_results(self, capsys):
        """Test the print_test_results method."""
        large_outcomes = self.suite.simulate_outcomes(1000)
        suite_result = self.suite.run_all_tests(large_outcomes)
        
        # This should print without error
        self.suite.print_test_results(suite_result)
        
        # Check that output was printed
        captured = capsys.readouterr()
        assert "DuckPools RNG Statistical Test Suite Results" in captured.out
        assert "Total Tests:" in captured.out
    
    def test_edge_cases(self):
        """Test edge cases and error handling."""
        # Empty list should not break tests
        empty_result = self.suite.frequency_test([])
        assert isinstance(empty_result, RNGTestResult)
        
        # Very small lists
        tiny_list = [0, 1]
        tiny_result = self.suite.frequency_test(tiny_list)
        assert isinstance(tiny_result, RNGTestResult)
        
        # All zeros
        all_zeros = [0] * 100
        zeros_result = self.suite.frequency_test(all_zeros)
        assert isinstance(zeros_result, RNGTestResult)
        
        # All ones
        all_ones = [1] * 100
        ones_result = self.suite.frequency_test(all_ones)
        assert isinstance(ones_result, RNGTestResult)
    
    def test_consistency(self):
        """Test that results are consistent when using same data."""
        # Generate test data
        outcomes = self.suite.simulate_outcomes(1000)
        
        # Run tests multiple times with same data
        result1 = self.suite.frequency_test(outcomes)
        result2 = self.suite.frequency_test(outcomes)
        result3 = self.suite.frequency_test(outcomes)
        
        # Results should be identical
        assert result1.statistic == result2.statistic == result3.statistic
        assert result1.p_value == result2.p_value == result3.p_value
        assert result1.passed == result2.passed == result3.passed


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])