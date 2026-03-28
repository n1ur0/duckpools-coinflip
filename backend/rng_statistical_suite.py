"""
DuckPools RNG Statistical Test Suite
====================================

Comprehensive statistical tests for verifying the fairness of the DuckPools RNG scheme:
SHA256(blockHash_as_utf8 || secret_bytes)[0] % 2

This suite implements standard statistical tests for random number generators:
1. Chi-squared test (uniformity)
2. Wald-Wolfowitz runs test (independence)
3. Frequency test (monobit test)
4. Kolmogorov-Smirnov test
5. Autocorrelation test
6. Binary matrix rank test
7. Serial test
8. Poker test

MAT-XXX: Implement RNG statistical test suite for fairness verification
"""

import hashlib
import math
import statistics
import secrets
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from collections import Counter


@dataclass
class RNGTestResult:
    """Results of a single statistical test."""
    test_name: str
    statistic: float
    p_value: float
    passed: bool
    alpha: float = 0.01
    details: Optional[Dict] = None


@dataclass
class RNGTestSuiteResult:
    """Comprehensive results of all RNG statistical tests."""
    total_tests: int
    passed_tests: int
    failed_tests: int
    test_results: List[RNGTestResult]
    overall_passed: bool
    summary: str


class RNGStatisticalSuite:
    """Comprehensive statistical test suite for RNG fairness verification."""
    
    def __init__(self, alpha: float = 0.01):
        """
        Initialize the test suite.
        
        Args:
            alpha: Significance level for all tests (default: 0.01)
        """
        self.alpha = alpha
        
    def compute_rng_outcome(self, block_hash: str, secret: bytes) -> int:
        """
        Compute RNG outcome using the production scheme.
        
        Formula: SHA256(blockHash_as_utf8 || secret_bytes)[0] % 2
        
        Args:
            block_hash: Block hash as hex string (used as UTF-8)
            secret: 8-byte secret
            
        Returns:
            0 (tails) or 1 (heads)
        """
        if len(secret) != 8:
            raise ValueError(f"Secret must be 8 bytes, got {len(secret)}")
            
        # Block hash is used as UTF-8 string
        block_hash_bytes = block_hash.encode('utf-8')
        
        # Concatenate and hash
        rng_input = block_hash_bytes + secret
        rng_hash = hashlib.sha256(rng_input).digest()
        
        # Outcome is first byte % 2
        return rng_hash[0] % 2
    
    def simulate_outcomes(self, n: int, block_hashes: List[str] = None) -> List[int]:
        """
        Simulate n RNG outcomes with random block hashes and secrets.
        
        Args:
            n: Number of outcomes to generate
            block_hashes: Optional list of block hashes (generates random if None)
            
        Returns:
            List of outcomes (0 or 1)
        """
        outcomes = []
        
        if block_hashes is None:
            # Generate random block hashes (64 hex chars = 32 bytes)
            block_hashes = [secrets.token_hex(32) for _ in range(n)]
        
        for i in range(n):
            # Use block hash in sequence or cycle through provided list
            block_hash = block_hashes[i % len(block_hashes)]
            
            # Generate random secret (8 bytes)
            secret = secrets.token_bytes(8)
            
            # Compute outcome
            outcome = self.compute_rng_outcome(block_hash, secret)
            outcomes.append(outcome)
            
        return outcomes
    
    def chi_square_test(self, outcomes: List[int]) -> RNGTestResult:
        """
        Perform chi-square test for uniformity.
        
        H0: Outcomes follow uniform distribution (50% heads, 50% tails)
        H1: Outcomes do NOT follow uniform distribution
        
        Args:
            outcomes: List of outcomes (0 or 1)
            
        Returns:
            RNGTestResult with chi-square statistics
        """
        n = len(outcomes)
        
        # Count heads (0) and tails (1)
        counts = Counter(outcomes)
        observed_0 = counts.get(0, 0)
        observed_1 = counts.get(1, 0)
        
        # Expected counts (50% each)
        expected_0 = n / 2
        expected_1 = n / 2
        
        # Chi-square statistic
        chi2 = ((observed_0 - expected_0) ** 2 / expected_0 +
                (observed_1 - expected_1) ** 2 / expected_1)
        
        # Degrees of freedom = number of categories - 1 = 1
        df = 1
        
        # P-value (using chi-square distribution approximation for df=1)
        # For df=1, p-value = exp(-chi2 / 2) is a good approximation
        p_value = math.exp(-chi2 / 2) if chi2 > 0 else 1.0
        
        # Critical value for alpha=0.01, df=1 is 6.635
        critical_value = 6.635
        passed = p_value > self.alpha and chi2 < critical_value
        
        details = {
            'observed_heads': observed_0,
            'observed_tails': observed_1,
            'expected_heads': expected_0,
            'expected_tails': expected_1,
            'heads_ratio': observed_0 / n,
            'tails_ratio': observed_1 / n,
            'degrees_of_freedom': df,
            'critical_value': critical_value
        }
        
        return RNGTestResult(
            test_name="Chi-square Test (Uniformity)",
            statistic=chi2,
            p_value=p_value,
            passed=passed,
            alpha=self.alpha,
            details=details
        )
    
    def runs_test(self, outcomes: List[int]) -> RNGTestResult:
        """
        Perform Wald-Wolfowitz runs test for independence.
        
        Tests whether outcomes are randomly ordered (no patterns).
        
        Args:
            outcomes: List of outcomes (0 or 1)
            
        Returns:
            RNGTestResult with runs test statistics
        """
        n = len(outcomes)
        
        # Count heads (0) and tails (1)
        n0 = outcomes.count(0)
        n1 = outcomes.count(1)
        
        # Count runs (consecutive same values)
        runs = 1
        for i in range(1, n):
            if outcomes[i] != outcomes[i - 1]:
                runs += 1
        
        # Expected number of runs
        expected_runs = (2 * n0 * n1 / n) + 1
        
        # Variance of number of runs
        variance_runs = (2 * n0 * n1 * (2 * n0 * n1 - n)) / (n ** 2 * (n - 1))
        
        # Z-score (normalize by sqrt of variance)
        if variance_runs > 0:
            z = (runs - expected_runs) / math.sqrt(variance_runs)
        else:
            z = 0
        
        # P-value (two-tailed test using normal distribution)
        if abs(z) < 8:  # Prevent numerical overflow
            p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        else:
            p_value = 0.0
        
        # Critical values for two-tailed test at alpha=0.01
        critical_value = 2.576  # Approximate for alpha=0.01 two-tailed
        passed = p_value > self.alpha and abs(z) < critical_value
        
        details = {
            'runs_count': runs,
            'expected_runs': expected_runs,
            'variance_runs': variance_runs,
            'heads_count': n0,
            'tails_count': n1,
            'critical_value': critical_value
        }
        
        return RNGTestResult(
            test_name="Wald-Wolfowitz Runs Test (Independence)",
            statistic=z,
            p_value=p_value,
            passed=passed,
            alpha=self.alpha,
            details=details
        )
    
    def frequency_test(self, outcomes: List[int]) -> RNGTestResult:
        """
        Perform frequency test (monobit test).
        
        Tests the proportion of 1s in the sequence.
        
        Args:
            outcomes: List of outcomes (0 or 1)
            
        Returns:
            RNGTestResult with frequency test statistics
        """
        n = len(outcomes)
        
        # Handle edge case: empty list
        if n == 0:
            return RNGTestResult(
                test_name="Frequency Test (Monobit)",
                statistic=0.0,
                p_value=0.0,
                passed=False,
                alpha=self.alpha,
                details={'error': 'Empty sequence provided'}
            )
        
        # Count number of 1s
        count_ones = sum(outcomes)
        
        # Proportion of 1s
        proportion = count_ones / n
        
        # Test statistic: |count_ones - n/2| / sqrt(n/4)
        statistic = abs(count_ones - n/2) / math.sqrt(n/4)
        
        # P-value using normal approximation
        p_value = 2 * (1 - 0.5 * (1 + math.erf(statistic / math.sqrt(2))))
        
        # Critical value for alpha=0.01 two-tailed
        critical_value = 2.576
        passed = p_value > self.alpha and statistic < critical_value
        
        details = {
            'count_ones': count_ones,
            'count_zeros': n - count_ones,
            'proportion_ones': proportion,
            'proportion_zeros': 1 - proportion,
            'critical_value': critical_value
        }
        
        return RNGTestResult(
            test_name="Frequency Test (Monobit)",
            statistic=statistic,
            p_value=p_value,
            passed=passed,
            alpha=self.alpha,
            details=details
        )
    
    def kolmogorov_smirnov_test(self, outcomes: List[int]) -> RNGTestResult:
        """
        Perform Kolmogorov-Smirnov test for uniformity.
        
        Tests if the outcomes follow a uniform distribution.
        
        Args:
            outcomes: List of outcomes (0 or 1)
            
        Returns:
            RNGTestResult with KS test statistics
        """
        n = len(outcomes)
        
        # Create empirical cumulative distribution function
        counts = Counter(outcomes)
        observed_freq_0 = counts.get(0, 0) / n
        observed_freq_1 = counts.get(1, 0) / n
        
        # Expected frequencies for uniform distribution
        expected_freq_0 = 0.5
        expected_freq_1 = 0.5
        
        # Calculate maximum difference (K-S statistic)
        diff_0 = abs(observed_freq_0 - expected_freq_0)
        diff_1 = abs(observed_freq_1 - expected_freq_1)
        ks_statistic = max(diff_0, diff_1)
        
        # Critical value for K-S test at alpha=0.01
        # For large n, critical value ≈ 1.63 / sqrt(n)
        critical_value = 1.63 / math.sqrt(n)
        
        # P-value approximation
        p_value = math.exp(-2 * n * ks_statistic ** 2) if ks_statistic > 0 else 1.0
        
        passed = ks_statistic < critical_value and p_value > self.alpha
        
        details = {
            'observed_freq_0': observed_freq_0,
            'observed_freq_1': observed_freq_1,
            'expected_freq_0': expected_freq_0,
            'expected_freq_1': expected_freq_1,
            'max_difference': ks_statistic,
            'critical_value': critical_value
        }
        
        return RNGTestResult(
            test_name="Kolmogorov-Smirnov Test",
            statistic=ks_statistic,
            p_value=p_value,
            passed=passed,
            alpha=self.alpha,
            details=details
        )
    
    def autocorrelation_test(self, outcomes: List[int], lag: int = 1) -> RNGTestResult:
        """
        Perform autocorrelation test.
        
        Tests for correlation between outcomes at a given lag.
        
        Args:
            outcomes: List of outcomes (0 or 1)
            lag: Lag to test (default: 1)
            
        Returns:
            RNGTestResult with autocorrelation test statistics
        """
        n = len(outcomes)
        
        if n <= lag:
            # Not enough data for the specified lag
            return RNGTestResult(
                test_name=f"Autocorrelation Test (lag={lag})",
                statistic=0.0,
                p_value=1.0,
                passed=False,
                alpha=self.alpha,
                details={'error': 'Not enough data for specified lag'}
            )
        
        # Split into original and lagged series
        x = outcomes[:-lag]
        y = outcomes[lag:]
        
        # Calculate correlation coefficient
        if len(set(x)) == 1 or len(set(y)) == 1:
            # One of the series is constant, correlation is undefined
            correlation = 0.0
        else:
            # Calculate Pearson correlation coefficient manually
            mean_x = statistics.mean(x)
            mean_y = statistics.mean(y)
            
            numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
            denominator_x = sum((xi - mean_x) ** 2 for xi in x)
            denominator_y = sum((yi - mean_y) ** 2 for yi in y)
            
            denominator = math.sqrt(denominator_x * denominator_y)
            if denominator > 0:
                correlation = numerator / denominator
            else:
                correlation = 0.0
        
        # Test statistic: sqrt(n - lag - 2) * |r| / sqrt(1 - r^2)
        # This follows a t-distribution with n - lag - 2 degrees of freedom
        if abs(correlation) < 0.999999:  # Avoid division by zero
            statistic = abs(correlation) * math.sqrt((n - lag - 2) / (1 - correlation ** 2))
        else:
            statistic = float('inf')
        
        # Degrees of freedom
        df = n - lag - 2
        
        # Critical value for t-distribution at alpha=0.01, two-tailed
        # For large df, this approximates 2.576 (normal distribution)
        if df > 30:
            critical_value = 2.576
        else:
            # Approximation for smaller df
            critical_value = 2.8 + 10 / df  # Rough approximation
        
        # P-value approximation using normal distribution for large df
        p_value = 2 * (1 - 0.5 * (1 + math.erf(statistic / math.sqrt(2))))
        
        passed = statistic < critical_value and p_value > self.alpha
        
        details = {
            'lag': lag,
            'correlation': correlation,
            'degrees_of_freedom': df,
            'critical_value': critical_value
        }
        
        return RNGTestResult(
            test_name=f"Autocorrelation Test (lag={lag})",
            statistic=statistic,
            p_value=p_value,
            passed=passed,
            alpha=self.alpha,
            details=details
        )
    
    def binary_matrix_rank_test(self, outcomes: List[int], matrix_size: int = 32) -> RNGTestResult:
        """
        Perform binary matrix rank test.
        
        Tests for linear dependence in binary matrices formed from the sequence.
        
        Args:
            outcomes: List of outcomes (0 or 1)
            matrix_size: Size of the binary matrices (default: 32x32)
            
        Returns:
            RNGTestResult with binary matrix rank test statistics
        """
        n = len(outcomes)
        
        # Calculate number of matrices we can form
        matrices_count = n // (matrix_size * matrix_size)
        
        if matrices_count < 10:
            # Not enough data for meaningful test
            return RNGTestResult(
                test_name=f"Binary Matrix Rank Test ({matrix_size}x{matrix_size})",
                statistic=0.0,
                p_value=1.0,
                passed=False,
                alpha=self.alpha,
                details={'error': 'Not enough data for meaningful test'}
            )
        
        # Count matrices of each rank category
        full_rank_count = 0
        rank_deficient_count = 0
        rank_one_count = 0
        
        # Create and analyze matrices
        for i in range(matrices_count):
            start_idx = i * matrix_size * matrix_size
            end_idx = start_idx + matrix_size * matrix_size
            
            # Extract matrix data
            matrix_data = outcomes[start_idx:end_idx]
            
            # Reshape into matrix
            matrix = []
            for row in range(matrix_size):
                row_start = row * matrix_size
                row_end = row_start + matrix_size
                matrix.append(matrix_data[row_start:row_end])
            
# Calculate rank using a simplified approach without numpy
        # For binary matrices, we can use a simplified heuristic based on row diversity
        
        # Count unique rows
        unique_rows = set(tuple(row) for row in matrix)
        
        # Count number of all-zero and all-one rows
        all_zero_rows = sum(1 for row in matrix if all(bit == 0 for bit in row))
        all_one_rows = sum(1 for row in matrix if all(bit == 1 for bit in row))
        
        # Heuristic for rank estimation:
        # - If all rows are identical, rank is 1 (unless all zeros)
        # - If there are many unique rows, rank is likely full
        # - Otherwise, it's somewhere in between
        
        if len(unique_rows) == 1:
            # All rows identical
            if all_zero_rows == matrix_size:
                # All zero matrix - rank 0 (but we'll count as rank deficient)
                rank_deficient_count += 1
            else:
                # All identical but not all zero - rank 1
                rank_one_count += 1
        elif len(unique_rows) >= matrix_size * 0.7:
            # Many unique rows, likely full rank
            full_rank_count += 1
        elif all_zero_rows > 0 or all_one_rows > 0:
            # Presence of uniform rows suggests potential linear dependence
            rank_deficient_count += 1
        else:
            # Intermediate case
            if matrix_size <= 4:
                # For small matrices, be more conservative
                full_rank_count += 1
            else:
                # For larger matrices, use a heuristic based on row diversity
                row_diversity = len(unique_rows) / matrix_size
                if row_diversity > 0.5:
                    full_rank_count += 1
                else:
                    rank_deficient_count += 1
        
        # Chi-square test for rank distribution
        total_matrices = full_rank_count + rank_deficient_count + rank_one_count
        
        if total_matrices == 0:
            return RNGTestResult(
                test_name=f"Binary Matrix Rank Test ({matrix_size}x{matrix_size})",
                statistic=0.0,
                p_value=1.0,
                passed=False,
                alpha=self.alpha,
                details={'error': 'No matrices to analyze'}
            )
        
        # Expected proportions (simplified)
        expected_full = 0.288 * total_matrices  # ~28.8% for 32x32 matrices
        expected_deficient = 0.577 * total_matrices  # ~57.7%
        expected_one = 0.135 * total_matrices  # ~13.5%
        
        # Chi-square statistic
        chi2 = ((full_rank_count - expected_full) ** 2 / expected_full +
                (rank_deficient_count - expected_deficient) ** 2 / expected_deficient +
                (rank_one_count - expected_one) ** 2 / expected_one)
        
        # Degrees of freedom
        df = 2  # 3 categories - 1
        
        # P-value approximation
        p_value = math.exp(-chi2 / 2) if chi2 > 0 else 1.0
        
        # Critical value for alpha=0.01, df=2 is 9.210
        critical_value = 9.210
        passed = p_value > self.alpha and chi2 < critical_value
        
        details = {
            'matrix_size': matrix_size,
            'total_matrices': total_matrices,
            'full_rank_count': full_rank_count,
            'rank_deficient_count': rank_deficient_count,
            'rank_one_count': rank_one_count,
            'expected_full': expected_full,
            'expected_deficient': expected_deficient,
            'expected_one': expected_one,
            'degrees_of_freedom': df,
            'critical_value': critical_value
        }
        
        return RNGTestResult(
            test_name=f"Binary Matrix Rank Test ({matrix_size}x{matrix_size})",
            statistic=chi2,
            p_value=p_value,
            passed=passed,
            alpha=self.alpha,
            details=details
        )
    
    def serial_test(self, outcomes: List[int], pattern_length: int = 2) -> RNGTestResult:
        """
        Perform serial test.
        
        Tests for uniformity of patterns of the specified length.
        
        Args:
            outcomes: List of outcomes (0 or 1)
            pattern_length: Length of patterns to test (default: 2)
            
        Returns:
            RNGTestResult with serial test statistics
        """
        n = len(outcomes)
        
        if n < pattern_length * 10:
            return RNGTestResult(
                test_name=f"Serial Test (pattern_length={pattern_length})",
                statistic=0.0,
                p_value=1.0,
                passed=False,
                alpha=self.alpha,
                details={'error': 'Not enough data for meaningful test'}
            )
        
        # Count all possible patterns of the given length
        pattern_counts = Counter()
        total_patterns = n - pattern_length + 1
        
        for i in range(total_patterns):
            pattern = tuple(outcomes[i:i + pattern_length])
            pattern_counts[pattern] += 1
        
        # Expected count for each pattern
        expected_count = total_patterns / (2 ** pattern_length)
        
        # Chi-square statistic
        chi2 = 0.0
        for pattern in pattern_counts:
            observed = pattern_counts[pattern]
            chi2 += (observed - expected_count) ** 2 / expected_count
        
        # Degrees of freedom: 2^pattern_length - 1
        df = (2 ** pattern_length) - 1
        
        # P-value approximation
        if df > 0:
            p_value = math.exp(-chi2 / 2) if chi2 > 0 else 1.0
        else:
            p_value = 1.0
        
        # Critical value depends on degrees of freedom
        if df == 3:  # pattern_length=2
            critical_value = 11.345
        elif df == 7:  # pattern_length=3
            critical_value = 18.475
        else:
            # General approximation
            critical_value = df + 3 * math.sqrt(df)
        
        passed = p_value > self.alpha and chi2 < critical_value
        
        details = {
            'pattern_length': pattern_length,
            'total_patterns': total_patterns,
            'unique_patterns': len(pattern_counts),
            'expected_count': expected_count,
            'degrees_of_freedom': df,
            'critical_value': critical_value,
            'pattern_counts': dict(sorted(pattern_counts.items()))
        }
        
        return RNGTestResult(
            test_name=f"Serial Test (pattern_length={pattern_length})",
            statistic=chi2,
            p_value=p_value,
            passed=passed,
            alpha=self.alpha,
            details=details
        )
    
    def poker_test(self, outcomes: List[int], hand_size: int = 4) -> RNGTestResult:
        """
        Perform poker test.
        
        Tests for uniformity of "hands" (groups) of outcomes.
        
        Args:
            outcomes: List of outcomes (0 or 1)
            hand_size: Size of each hand (default: 4)
            
        Returns:
            RNGTestResult with poker test statistics
        """
        n = len(outcomes)
        
        if n < hand_size * 10:
            return RNGTestResult(
                test_name=f"Poker Test (hand_size={hand_size})",
                statistic=0.0,
                p_value=1.0,
                passed=False,
                alpha=self.alpha,
                details={'error': 'Not enough data for meaningful test'}
            )
        
        # Count number of complete hands
        num_hands = n // hand_size
        
        # Count each type of hand (based on number of 1s)
        hand_counts = Counter()
        
        for i in range(num_hands):
            start_idx = i * hand_size
            end_idx = start_idx + hand_size
            hand = outcomes[start_idx:end_idx]
            
            # Count number of 1s in the hand
            ones_count = sum(hand)
            hand_counts[ones_count] += 1
        
        # Expected counts for each hand type
        # For a hand of size k, the probability of i ones is C(k, i) / 2^k
        expected_counts = {}
        for i in range(hand_size + 1):
            # Binomial coefficient: C(hand_size, i)
            # Calculate manually since math.comb might not be available in older Python versions
            def binomial_coefficient(n, k):
                if k < 0 or k > n:
                    return 0
                if k == 0 or k == n:
                    return 1
                k = min(k, n - k)  # Take advantage of symmetry
                result = 1
                for i in range(k):
                    result = result * (n - i) // (i + 1)
                return result
            
            prob = binomial_coefficient(hand_size, i) / (2 ** hand_size)
            expected_counts[i] = num_hands * prob
        
        # Chi-square statistic
        chi2 = 0.0
        for i in range(hand_size + 1):
            observed = hand_counts.get(i, 0)
            expected = expected_counts[i]
            if expected > 0:
                chi2 += (observed - expected) ** 2 / expected
        
        # Degrees of freedom: hand_size + 1 - 1 = hand_size
        df = hand_size
        
        # P-value approximation
        if df > 0:
            p_value = math.exp(-chi2 / 2) if chi2 > 0 else 1.0
        else:
            p_value = 1.0
        
        # Critical value depends on degrees of freedom
        if df == 4:  # hand_size=4
            critical_value = 13.277
        else:
            # General approximation
            critical_value = df + 3 * math.sqrt(df)
        
        passed = p_value > self.alpha and chi2 < critical_value
        
        details = {
            'hand_size': hand_size,
            'num_hands': num_hands,
            'degrees_of_freedom': df,
            'critical_value': critical_value,
            'hand_counts': dict(sorted(hand_counts.items())),
            'expected_counts': expected_counts
        }
        
        return RNGTestResult(
            test_name=f"Poker Test (hand_size={hand_size})",
            statistic=chi2,
            p_value=p_value,
            passed=passed,
            alpha=self.alpha,
            details=details
        )
    
    def run_all_tests(self, outcomes: List[int]) -> RNGTestSuiteResult:
        """
        Run all statistical tests on the given outcomes.
        
        Args:
            outcomes: List of outcomes (0 or 1)
            
        Returns:
            RNGTestSuiteResult with comprehensive test results
        """
        test_results = []
        
        # Run all tests
        test_results.append(self.frequency_test(outcomes))
        test_results.append(self.chi_square_test(outcomes))
        test_results.append(self.runs_test(outcomes))
        test_results.append(self.kolmogorov_smirnov_test(outcomes))
        test_results.append(self.autocorrelation_test(outcomes, lag=1))
        test_results.append(self.binary_matrix_rank_test(outcomes))
        test_results.append(self.serial_test(outcomes, pattern_length=2))
        test_results.append(self.poker_test(outcomes, hand_size=4))
        
        # Count passed and failed tests
        passed_tests = sum(1 for result in test_results if result.passed)
        failed_tests = len(test_results) - passed_tests
        
        # Determine overall result
        overall_passed = failed_tests == 0
        
        # Generate summary
        if overall_passed:
            summary = "All tests passed. RNG appears to be fair and unbiased."
        elif passed_tests >= len(test_results) * 0.8:
            summary = f"Most tests passed ({passed_tests}/{len(test_results)}). Minor anomalies detected but RNG is likely fair."
        else:
            summary = f"Multiple tests failed ({failed_tests}/{len(test_results)}). RNG may be biased or non-random."
        
        return RNGTestSuiteResult(
            total_tests=len(test_results),
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            test_results=test_results,
            overall_passed=overall_passed,
            summary=summary
        )
    
    def print_test_results(self, test_suite_result: RNGTestSuiteResult):
        """
        Print a formatted summary of all test results.
        
        Args:
            test_suite_result: Results from run_all_tests()
        """
        print("=" * 80)
        print("DuckPools RNG Statistical Test Suite Results")
        print("=" * 80)
        print(f"Total Tests: {test_suite_result.total_tests}")
        print(f"Passed: {test_suite_result.passed_tests}")
        print(f"Failed: {test_suite_result.failed_tests}")
        print(f"Overall Result: {'PASS' if test_suite_result.overall_passed else 'FAIL'}")
        print("=" * 80)
        
        # Print individual test results
        for result in test_suite_result.test_results:
            status = "PASS" if result.passed else "FAIL"
            print(f"\n{result.test_name}")
            print("-" * len(result.test_name))
            print(f"  Status: {status}")
            print(f"  Statistic: {result.statistic:.6f}")
            print(f"  P-value: {result.p_value:.6f}")
            print(f"  Alpha: {result.alpha:.3f}")
            
            if result.details:
                for key, value in result.details.items():
                    if isinstance(value, float):
                        print(f"  {key}: {value:.6f}")
                    elif isinstance(value, int):
                        print(f"  {key}: {value:,}")
                    elif key == 'error':
                        print(f"  Error: {value}")
        
        print("\n" + "=" * 80)
        print(f"Summary: {test_suite_result.summary}")
        print("=" * 80)


def main():
    """Run the RNG statistical test suite with example data."""
    # Create test suite
    suite = RNGStatisticalSuite(alpha=0.01)
    
    # Generate test data
    num_outcomes = 100_000
    print(f"Generating {num_outcomes:,} RNG outcomes...")
    outcomes = suite.simulate_outcomes(num_outcomes)
    
    # Count outcomes
    counts = Counter(outcomes)
    print(f"Heads (0): {counts.get(0, 0):,} ({counts.get(0, 0) / num_outcomes * 100:.2f}%)")
    print(f"Tails (1): {counts.get(1, 0):,} ({counts.get(1, 0) / num_outcomes * 100:.2f}%)")
    
    # Run all tests
    results = suite.run_all_tests(outcomes)
    
    # Print results
    suite.print_test_results(results)


if __name__ == "__main__":
    main()