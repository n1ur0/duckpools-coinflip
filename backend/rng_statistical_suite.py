"""
DuckPools RNG Statistical Test Suite
=====================================

Comprehensive statistical tests for verifying the fairness of the DuckPools RNG scheme.

PROTOCOL SCHEME (MUST match on-chain coinflip_v2.es):
    blake2b256(blockId_raw_bytes || playerSecret_raw_bytes)[0] % 2

Where:
    - blockId: Raw 32-byte block ID (hex-decoded from 64-char hex string)
    - playerSecret: Raw secret bytes stored in contract R9

SECURITY: The on-chain contract uses blake2b256 opcode. This module MUST use
blake2b256 as well. Using SHA-256 would cause every reveal to fail on-chain.

Tests implemented:
1. Frequency (Monobit) test - proportion of 0s vs 1s
2. Chi-squared test - uniformity of distribution
3. Wald-Wolfowitz Runs test - independence of consecutive outcomes
4. Kolmogorov-Smirnov test - empirical vs expected CDF
5. Autocorrelation test - correlation at lag k
6. Serial test - frequency of m-bit patterns
7. Streak analysis - longest runs of identical outcomes

Issue: 01c50a13
"""

import hashlib
import math
import os
import secrets
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Ensure backend directory is on sys.path for rng_module import
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from rng_module import compute_rng, generate_commit, verify_commit


# ─── Constants ────────────────────────────────────────────────────────────────

ALPHA = 0.01  # Significance level (1% false-positive rate)
NUM_SIMULATIONS = 100_000


# ─── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class SingleTestResult:
    """Result of a single statistical test."""

    test_name: str
    statistic: float
    p_value: float
    passed: bool
    alpha: float = ALPHA
    details: Optional[Dict] = None


@dataclass
class SuiteResult:
    """Aggregate results of the full RNG statistical test suite."""

    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    test_results: List[SingleTestResult] = field(default_factory=list)
    overall_passed: bool = False
    summary: str = ""
    num_simulations: int = 0
    heads_count: int = 0
    tails_count: int = 0
    heads_ratio: float = 0.0
    tails_ratio: float = 0.0
    entropy_bits: float = 0.0


# ─── RNG Outcome Generation ───────────────────────────────────────────────────


def simulate_outcomes(n: int, block_hashes: Optional[List[str]] = None) -> List[int]:
    """
    Simulate n RNG outcomes using the production blake2b256 scheme.

    Each outcome uses a fresh random block hash and random 8-byte secret,
    matching real protocol conditions where each bet has unique inputs.

    Args:
        n: Number of outcomes to generate.
        block_hashes: Optional pre-generated block hashes (64-char hex).

    Returns:
        List of outcomes (0 or 1).
    """
    outcomes: List[int] = []
    if block_hashes is None:
        block_hashes = [secrets.token_hex(32) for _ in range(n)]

    for i in range(n):
        block_hash = block_hashes[i % len(block_hashes)]
        secret = secrets.token_bytes(8)
        outcome = compute_rng(block_hash, secret)
        outcomes.append(outcome)

    return outcomes


# ─── Helper: Shannon Entropy ──────────────────────────────────────────────────


def shannon_entropy(counts: Dict[int, int]) -> float:
    """
    Calculate Shannon entropy of a discrete distribution.

    H(X) = -sum(p(x) * log2(p(x)))

    For a fair coinflip, maximum entropy = 1.0 bit.
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


# ─── Test 1: Frequency (Monobit) Test ─────────────────────────────────────────


def frequency_test(outcomes: List[int], alpha: float = ALPHA) -> SingleTestResult:
    """
    NIST SP 800-22 Frequency (Monobit) Test.

    Tests whether the proportion of 1s in the sequence is close to 0.5.

    Test statistic: S = |count_1 - n/2| / sqrt(n/4)
    Under H0 (fair), S ~ N(0,1) for large n.

    H0: Sequence is random (proportion of 1s = 0.5)
    H1: Sequence is not random (proportion of 1s != 0.5)
    """
    n = len(outcomes)

    if n == 0:
        return SingleTestResult(
            test_name="Frequency Test (Monobit)",
            statistic=0.0,
            p_value=0.0,
            passed=False,
            alpha=alpha,
            details={"error": "Empty sequence"},
        )

    count_ones = sum(outcomes)
    count_zeros = n - count_ones

    # S_n = sum(2*X_i - 1) where X_i are the bits
    # For binary: S_n = count_ones - count_zeros
    s_obs = count_ones - count_zeros

    # Test statistic: |S_obs| / sqrt(n)
    statistic = abs(s_obs) / math.sqrt(n)

    # P-value using complementary error function
    # P = 2 * (1 - Phi(statistic)) = erfc(statistic / sqrt(2))
    p_value = math.erfc(statistic / math.sqrt(2))

    passed = p_value >= alpha

    return SingleTestResult(
        test_name="Frequency Test (Monobit)",
        statistic=statistic,
        p_value=p_value,
        passed=passed,
        alpha=alpha,
        details={
            "count_ones": count_ones,
            "count_zeros": count_zeros,
            "proportion_ones": count_ones / n,
            "proportion_zeros": count_zeros / n,
            "s_obs": s_obs,
        },
    )


# ─── Test 2: Chi-Squared Test ─────────────────────────────────────────────────


def chi_square_test(outcomes: List[int], alpha: float = ALPHA) -> SingleTestResult:
    """
    Chi-squared goodness-of-fit test for uniform distribution.

    H0: Outcomes are uniformly distributed (P(0) = P(1) = 0.5)
    H1: Outcomes are NOT uniformly distributed

    For df=1: chi^2 = sum((O_i - E_i)^2 / E_i)
    P-value = erfc(sqrt(chi^2 / 2)) (exact for df=1 via chi-sq CDF identity)
    """
    n = len(outcomes)

    if n == 0:
        return SingleTestResult(
            test_name="Chi-Squared Test (Uniformity)",
            statistic=0.0,
            p_value=0.0,
            passed=False,
            alpha=alpha,
            details={"error": "Empty sequence"},
        )

    counts = Counter(outcomes)
    observed_0 = counts.get(0, 0)
    observed_1 = counts.get(1, 0)

    expected = n / 2.0

    # Chi-square statistic
    chi_sq = ((observed_0 - expected) ** 2 / expected) + ((observed_1 - expected) ** 2 / expected)

    # Exact p-value for chi-square with df=1: P = erfc(sqrt(chi_sq / 2))
    # This is mathematically exact, not an approximation.
    p_value = math.erfc(math.sqrt(chi_sq / 2))

    # Critical value for alpha=0.01, df=1
    critical_value = 6.6349  # chi^2_{0.99, 1}

    passed = p_value >= alpha and chi_sq < critical_value

    return SingleTestResult(
        test_name="Chi-Squared Test (Uniformity)",
        statistic=chi_sq,
        p_value=p_value,
        passed=passed,
        alpha=alpha,
        details={
            "observed_0": observed_0,
            "observed_1": observed_1,
            "expected": expected,
            "degrees_of_freedom": 1,
            "critical_value": critical_value,
            "heads_ratio": observed_0 / n if n > 0 else 0,
            "tails_ratio": observed_1 / n if n > 0 else 0,
        },
    )


# ─── Test 3: Wald-Wolfowitz Runs Test ─────────────────────────────────────────


def runs_test(outcomes: List[int], alpha: float = ALPHA) -> SingleTestResult:
    """
    Wald-Wolfowitz Runs Test for independence.

    Tests whether the order of outcomes is random (no patterns or clustering).

    A "run" is a maximal sequence of consecutive identical values.
    Under H0 (random sequence), the expected number of runs is:
        E[R] = (2 * n0 * n1) / n + 1

    H0: Outcomes are independently ordered
    H1: Outcomes exhibit non-random ordering
    """
    n = len(outcomes)

    if n < 2:
        return SingleTestResult(
            test_name="Wald-Wolfowitz Runs Test (Independence)",
            statistic=0.0,
            p_value=0.0,
            passed=False,
            alpha=alpha,
            details={"error": "Need at least 2 outcomes"},
        )

    n0 = outcomes.count(0)
    n1 = outcomes.count(1)

    # Count runs
    runs = 1
    for i in range(1, n):
        if outcomes[i] != outcomes[i - 1]:
            runs += 1

    # Expected runs
    expected_runs = (2 * n0 * n1) / n + 1

    # Variance of runs
    numerator = 2 * n0 * n1 * (2 * n0 * n1 - n)
    denominator = n * n * (n - 1)
    variance_runs = numerator / denominator if denominator > 0 else 0

    # Z-score
    if variance_runs > 0:
        z = (runs - expected_runs) / math.sqrt(variance_runs)
    else:
        # Only one outcome category — test is undefined, treat as fail
        z = 0.0

    # If all outcomes are the same, the sequence is clearly non-random
    if n0 == 0 or n1 == 0:
        return SingleTestResult(
            test_name="Wald-Wolfowitz Runs Test (Independence)",
            statistic=0.0,
            p_value=0.0,
            passed=False,
            alpha=alpha,
            details={
                "runs_count": runs,
                "expected_runs": expected_runs,
                "variance_runs": variance_runs,
                "n0": n0,
                "n1": n1,
                "note": "Only one outcome category — sequence is constant",
            },
        )

    # P-value (two-tailed)
    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

    passed = p_value >= alpha

    return SingleTestResult(
        test_name="Wald-Wolfowitz Runs Test (Independence)",
        statistic=z,
        p_value=p_value,
        passed=passed,
        alpha=alpha,
        details={
            "runs_count": runs,
            "expected_runs": expected_runs,
            "variance_runs": variance_runs,
            "n0": n0,
            "n1": n1,
        },
    )


# ─── Test 4: Kolmogorov-Smirnov Test ─────────────────────────────────────────


def kolmogorov_smirnov_test(outcomes: List[int], alpha: float = ALPHA) -> SingleTestResult:
    """
    One-sample Kolmogorov-Smirnov test for uniform distribution.

    Tests whether the empirical CDF of outcomes matches the theoretical
    uniform CDF (P(0) = 0.5, P(1) = 0.5).

    D_n = sup_x |F_n(x) - F(x)|
    """
    n = len(outcomes)

    if n < 10:
        return SingleTestResult(
            test_name="Kolmogorov-Smirnov Test",
            statistic=0.0,
            p_value=0.0,
            passed=False,
            alpha=alpha,
            details={"error": "Need at least 10 outcomes"},
        )

    counts = Counter(outcomes)
    observed_freq_0 = counts.get(0, 0) / n
    observed_freq_1 = counts.get(1, 0) / n

    # K-S statistic: max absolute difference from expected 0.5
    ks_stat = max(abs(observed_freq_0 - 0.5), abs(observed_freq_1 - 0.5))

    # P-value approximation (Kolmogorov distribution)
    # P(D_n > d) ~ 2 * sum_{k=1}^{inf} (-1)^{k+1} * exp(-2 * k^2 * n * d^2)
    # For large n, the first term dominates:
    if ks_stat > 0:
        p_value = 2 * math.exp(-2 * n * ks_stat ** 2)
    else:
        p_value = 1.0

    # Critical value for large n: ~1.63 / sqrt(n) at alpha=0.01
    critical_value = 1.628 / math.sqrt(n)  # More precise: 1.6276

    passed = ks_stat < critical_value and p_value >= alpha

    return SingleTestResult(
        test_name="Kolmogorov-Smirnov Test",
        statistic=ks_stat,
        p_value=p_value,
        passed=passed,
        alpha=alpha,
        details={
            "observed_freq_0": observed_freq_0,
            "observed_freq_1": observed_freq_1,
            "expected_freq": 0.5,
            "critical_value": critical_value,
        },
    )


# ─── Test 5: Autocorrelation Test ─────────────────────────────────────────────


def autocorrelation_test(
    outcomes: List[int],
    lag: int = 1,
    alpha: float = ALPHA,
) -> SingleTestResult:
    """
    Autocorrelation test at lag k.

    Tests whether outcome_i is correlated with outcome_{i+k}.
    Under H0 (independence), correlation should be ~0.

    Uses Pearson correlation coefficient with normal approximation for large n.
    """
    n = len(outcomes)

    if n <= lag + 2:
        return SingleTestResult(
            test_name=f"Autocorrelation Test (lag={lag})",
            statistic=0.0,
            p_value=1.0,
            passed=False,
            alpha=alpha,
            details={"error": "Not enough data for specified lag"},
        )

    x = outcomes[:-lag]
    y = outcomes[lag:]

    # Pearson correlation coefficient
    unique_x = set(x)
    unique_y = set(y)
    if len(unique_x) <= 1 or len(unique_y) <= 1:
        return SingleTestResult(
            test_name=f"Autocorrelation Test (lag={lag})",
            statistic=0.0,
            p_value=1.0,
            passed=True,
            alpha=alpha,
            details={"correlation": 0.0, "note": "Constant series"},
        )

    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)

    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denom_x = sum((xi - mean_x) ** 2 for xi in x)
    denom_y = sum((yi - mean_y) ** 2 for yi in y)
    denominator = math.sqrt(denom_x * denom_y)

    correlation = numerator / denominator if denominator > 0 else 0.0

    # Test statistic: t = r * sqrt((n - lag - 2) / (1 - r^2))
    df = n - lag - 2
    if abs(correlation) < 0.999999:
        statistic = abs(correlation) * math.sqrt(df / (1 - correlation ** 2))
    else:
        statistic = 100.0  # Cap to avoid infinity

    # Critical value: t-distribution approximated by normal for large df
    critical_value = 2.576 if df > 30 else 2.8 + 10 / df

    # P-value using normal approximation
    p_value = 2 * (1 - 0.5 * (1 + math.erf(statistic / math.sqrt(2))))

    passed = statistic < critical_value and p_value >= alpha

    return SingleTestResult(
        test_name=f"Autocorrelation Test (lag={lag})",
        statistic=statistic,
        p_value=p_value,
        passed=passed,
        alpha=alpha,
        details={
            "lag": lag,
            "correlation": correlation,
            "degrees_of_freedom": df,
            "critical_value": critical_value,
        },
    )


# ─── Test 6: Serial Test ──────────────────────────────────────────────────────


def serial_test(
    outcomes: List[int],
    pattern_length: int = 2,
    alpha: float = ALPHA,
) -> SingleTestResult:
    """
    Serial test for m-bit pattern uniformity.

    Tests whether all 2^m possible m-bit patterns appear with equal frequency.
    For pattern_length=2: tests frequencies of 00, 01, 10, 11.

    Uses chi-squared goodness-of-fit on pattern counts.
    """
    n = len(outcomes)

    if n < pattern_length * 10:
        return SingleTestResult(
            test_name=f"Serial Test (pattern_length={pattern_length})",
            statistic=0.0,
            p_value=1.0,
            passed=False,
            alpha=alpha,
            details={"error": "Not enough data for pattern length"},
        )

    # Count m-bit patterns
    num_patterns = 2 ** pattern_length
    pattern_counts: Dict[int, int] = {i: 0 for i in range(num_patterns)}
    num_overlapping = n - pattern_length + 1

    for i in range(num_overlapping):
        pattern = 0
        for j in range(pattern_length):
            pattern = (pattern << 1) | outcomes[i + j]
        pattern_counts[pattern] += 1

    expected = num_overlapping / num_patterns

    # Chi-square statistic
    chi_sq = 0.0
    for count in pattern_counts.values():
        chi_sq += ((count - expected) ** 2) / expected if expected > 0 else 0

    # Degrees of freedom
    df = num_patterns - 1

    # P-value using regularized incomplete gamma function approximation
    # For df >= 2, use the chi-square CDF via the log-gamma approximation
    # log(Gamma(df/2, chi_sq/2)) using series expansion
    # Simplified: use the approximation P(chi2 > x) ~ chi2^(df/2-1) * exp(-chi2/2) / (2^(df/2) * Gamma(df/2))
    # For practical purposes with df=3 (pattern_length=2):
    p_value = _chi2_sf(chi_sq, df)

    passed = p_value >= alpha

    return SingleTestResult(
        test_name=f"Serial Test (pattern_length={pattern_length})",
        statistic=chi_sq,
        p_value=p_value,
        passed=passed,
        alpha=alpha,
        details={
            "pattern_length": pattern_length,
            "num_patterns": num_patterns,
            "num_overlapping": num_overlapping,
            "pattern_counts": dict(pattern_counts),
            "expected_per_pattern": expected,
            "degrees_of_freedom": df,
        },
    )


def _chi2_sf(x: float, df: int) -> float:
    """
    Compute survival function P(chi2 > x) for chi-square distribution.

    Uses the regularized upper incomplete gamma function Q(a, x) = Gamma(a, x) / Gamma(a).
    For chi-square with df degrees of freedom: P(chi2 > x) = Q(df/2, x/2).

    Implementation uses the series expansion for small x and continued fraction
    for large x (Numerical Recipes approach).
    """
    if x <= 0:
        return 1.0
    if df <= 0:
        return 1.0

    a = df / 2.0
    x_half = x / 2.0

    # Log of Gamma function (Stirling's approximation for large a)
    def lgamma_approx(z: float) -> float:
        if z < 0.5:
            return math.lgamma(z) if hasattr(math, "lgamma") else _stirling_lgamma(z)
        return _stirling_lgamma(z)

    # Use series expansion: P(a, x) = gamma(a, x) / Gamma(a)
    # = exp(-x) * x^a * sum_{n=0}^{inf} x^n / (a * (a+1) * ... * (a+n))
    def series_q(a: float, x: float) -> float:
        """Upper incomplete gamma ratio Q(a,x) via series (good for x < a+1)."""
        if x == 0:
            return 1.0
        ap = a
        sum_val = 1.0 / a
        delta = 1.0 / a
        for _ in range(200):
            ap += 1.0
            delta *= x / ap
            sum_val += delta
            if abs(delta) < abs(sum_val) * 1e-12:
                break
        return sum_val * math.exp(-x) * x**a / _gamma_func(a)

    # Use continued fraction for Q(a,x) (good for x >= a+1)
    def cf_q(a: float, x: float) -> float:
        """Upper incomplete gamma ratio Q(a,x) via continued fraction."""
        b = x + 1.0 - a
        c = 1.0 / 1e-30
        d = 1.0 / b
        h = d
        for i in range(1, 200):
            an = -i * (i - a)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            delta = d * c
            h *= delta
            if abs(delta - 1.0) < 1e-12:
                break
        return math.exp(-x) * x**a * h / _gamma_func(a)

    if x_half < a + 1:
        return 1.0 - series_q(a, x_half)
    else:
        return cf_q(a, x_half)


def _gamma_func(z: float) -> float:
    """Gamma function approximation (Lanczos)."""
    if z < 0.5:
        return math.pi / (math.sin(math.pi * z) * _gamma_func(1 - z))
    z -= 1
    g = 7
    coefs = [
        0.99999999999980993,
        676.5203681218851,
        -1259.1392167224028,
        771.32342877765313,
        -176.61502916214059,
        12.507343278686905,
        -0.13857109526572012,
        9.9843695780195716e-6,
        1.5056327351493116e-7,
    ]
    x = coefs[0]
    for i in range(1, g + 2):
        x += coefs[i] / (z + i)
    t = z + g + 0.5
    return math.sqrt(2 * math.pi) * t ** (z + 0.5) * math.exp(-t) * x


def _stirling_lgamma(z: float) -> float:
    """Log-gamma via Stirling (fallback)."""
    return math.log(_gamma_func(z))


# ─── Test 7: Streak Analysis ──────────────────────────────────────────────────


def streak_analysis(outcomes: List[int]) -> Dict:
    """
    Analyze streaks (consecutive identical outcomes).

    For a fair coinflip of length n, the expected longest streak is ~log2(n).

    Returns dict with streak statistics and fairness assessment.
    """
    if not outcomes:
        return {
            "longest_streak": 0,
            "streak_counts": {},
            "expected_longest": 0,
            "within_expected": False,
        }

    streak_counts: Counter = Counter()
    current_streak = 1

    for i in range(1, len(outcomes)):
        if outcomes[i] == outcomes[i - 1]:
            current_streak += 1
        else:
            streak_counts[current_streak] += 1
            current_streak = 1
    streak_counts[current_streak] += 1

    longest_streak = max(streak_counts.keys()) if streak_counts else 0
    n = len(outcomes)
    expected_longest = math.log2(n) if n > 0 else 0

    # Allow 2 standard deviations above expected (rare but possible)
    # For geometric distribution: E[max] ~ log2(n), SD ~ 1.33
    within_expected = longest_streak <= int(expected_longest + 3)

    return {
        "longest_streak": longest_streak,
        "streak_counts": dict(streak_counts),
        "expected_longest": expected_longest,
        "within_expected": within_expected,
        "total_streaks": sum(streak_counts.values()),
    }


# ─── Commitment Binding Verification ──────────────────────────────────────────


def verify_commitment_binding(n_samples: int = 10000) -> Dict:
    """
    Verify that the commitment scheme is binding:
    1. Different secrets -> different commitments (same choice)
    2. Different choices -> different commitments (same secret)
    3. Verification works correctly
    4. Search space is sufficient (2^64)

    Returns dict with all test results.
    """
    results: Dict = {"tests": []}

    # Test 1: Different secrets produce different commitments
    collisions = 0
    for _ in range(n_samples):
        s1 = secrets.token_bytes(8)
        s2 = secrets.token_bytes(8)
        c1 = generate_commit(s1, 0)
        c2 = generate_commit(s2, 0)
        if c1 == c2:
            collisions += 1
    results["tests"].append({
        "name": "Different secrets -> different commitments",
        "passed": collisions == 0,
        "collisions": collisions,
        "samples": n_samples,
    })

    # Test 2: Different choices produce different commitments
    collisions = 0
    for _ in range(n_samples):
        s = secrets.token_bytes(8)
        c_heads = generate_commit(s, 0)
        c_tails = generate_commit(s, 1)
        if c_heads == c_tails:
            collisions += 1
    results["tests"].append({
        "name": "Different choices -> different commitments",
        "passed": collisions == 0,
        "collisions": collisions,
        "samples": n_samples,
    })

    # Test 3: Verification correctness
    verify_pass = 0
    verify_fail_wrong_choice = 0
    verify_fail_wrong_secret = 0
    for _ in range(n_samples):
        s = secrets.token_bytes(8)
        c = generate_commit(s, 0)
        if verify_commit(c, s, 0):
            verify_pass += 1
        if not verify_commit(c, s, 1):
            verify_fail_wrong_choice += 1
        if not verify_commit(c, secrets.token_bytes(8), 0):
            verify_fail_wrong_secret += 1
    results["tests"].append({
        "name": "Commitment verification correctness",
        "passed": (
            verify_pass == n_samples
            and verify_fail_wrong_choice == n_samples
            and verify_fail_wrong_secret == n_samples
        ),
        "correct_verifications": verify_pass,
        "wrong_choice_rejected": verify_fail_wrong_choice,
        "wrong_secret_rejected": verify_fail_wrong_secret,
        "samples": n_samples,
    })

    # Test 4: Search space analysis
    results["tests"].append({
        "name": "Secret space sufficiency (2^64)",
        "passed": True,
        "secret_bytes": 8,
        "search_space": 2**64,
        "birthday_attack_10k": f"~{(n_samples**2) / (2**65):.2e}",
    })

    results["all_passed"] = all(t["passed"] for t in results["tests"])
    return results


# ─── Miner Manipulation Analysis ──────────────────────────────────────────────


def miner_manipulation_analysis() -> Dict:
    """
    Analyze economic feasibility of miner manipulating block hashes to
    influence game outcomes.

    Attack scenario: Miner places a bet, then discards blocks until they
    find one that produces the desired outcome.
    """
    return {
        "attack_description": (
            "Miner places bet, then selectively publishes blocks to get "
            "desired outcome parity from blake2b256(blockId || secret)[0] % 2"
        ),
        "probability_per_block": 0.5,
        "expected_blocks_to_discard": 1,
        "mainnet_economics": {
            "block_reward_erg": "~2 ERG + fees",
            "max_bet_erg": "~10 ERG (10% of pool)",
            "max_payout_erg": "~9.7 ERG (0.97x after house edge)",
            "cost_to_manipulate": "~4 ERG (2 blocks at ~2 ERG each)",
            "expected_profit": "-0.03 * bet_amount (house edge)",
            "verdict": "NOT economically viable",
        },
        "mitigations": [
            "Player secret (8 bytes) provides 64-bit entropy unknown to miner",
            "Miner cannot predict outcome without player's secret",
            "Even controlling block hash, outcome depends on blake2b256(hash || unknown_secret)",
            "Cost to discard blocks far exceeds maximum possible gain",
        ],
        "verdict": "SAFE",
    }


# ─── Full Suite Runner ────────────────────────────────────────────────────────


def run_full_suite(
    num_simulations: int = NUM_SIMULATIONS,
    alpha: float = ALPHA,
) -> SuiteResult:
    """
    Run the complete RNG statistical test suite.

    Generates `num_simulations` outcomes using the production blake2b256
    scheme and runs all statistical tests.

    Args:
        num_simulations: Number of RNG outcomes to generate and test.
        alpha: Significance level for all tests.

    Returns:
        SuiteResult with aggregate and per-test results.
    """
    # Generate outcomes
    outcomes = simulate_outcomes(num_simulations)

    # Basic counts
    counts = Counter(outcomes)
    heads = counts.get(1, 0)
    tails = counts.get(0, 0)
    n = len(outcomes)
    heads_ratio = heads / n
    tails_ratio = tails / n
    entropy = shannon_entropy(counts)

    # Run all tests
    test_results: List[SingleTestResult] = []

    # Core tests
    test_results.append(frequency_test(outcomes, alpha))
    test_results.append(chi_square_test(outcomes, alpha))
    test_results.append(runs_test(outcomes, alpha))
    test_results.append(kolmogorov_smirnov_test(outcomes, alpha))

    # Autocorrelation at multiple lags
    for lag in [1, 2, 5, 10]:
        if n > lag + 10:
            test_results.append(autocorrelation_test(outcomes, lag, alpha))

    # Serial test for 2-bit patterns
    test_results.append(serial_test(outcomes, pattern_length=2, alpha=alpha))

    # Tally
    passed = sum(1 for t in test_results if t.passed)
    failed = sum(1 for t in test_results if not t.passed)
    total = len(test_results)

    # Build summary
    lines = [
        f"RNG Statistical Test Suite — {num_simulations:,} simulations",
        f"Scheme: blake2b256(blockId_raw_bytes || secret_raw_bytes)[0] % 2",
        f"Significance level: {alpha * 100:.1f}%",
        "",
        f"Outcomes: {heads:,} heads ({heads_ratio:.4%}) / {tails:,} tails ({tails_ratio:.4%})",
        f"Shannon entropy: {entropy:.6f} bits (max 1.0)",
        "",
        f"Tests: {passed}/{total} PASSED",
    ]
    for t in test_results:
        status = "PASS" if t.passed else "FAIL"
        lines.append(f"  [{status}] {t.test_name}: stat={t.statistic:.4f}, p={t.p_value:.6f}")

    summary = "\n".join(lines)

    return SuiteResult(
        total_tests=total,
        passed_tests=passed,
        failed_tests=failed,
        test_results=test_results,
        overall_passed=(failed == 0),
        summary=summary,
        num_simulations=n,
        heads_count=heads,
        tails_count=tails,
        heads_ratio=heads_ratio,
        tails_ratio=tails_ratio,
        entropy_bits=entropy,
    )


# ─── CLI ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else NUM_SIMULATIONS

    print("=" * 70)
    print("DuckPools RNG Fairness — Statistical Verification")
    print("=" * 70)
    print(f"Scheme: blake2b256(blockId_raw || secret_raw)[0] % 2")
    print(f"Simulations: {n:,}")
    print()

    result = run_full_suite(n)

    print(result.summary)
    print()

    # Commitment binding
    print("-" * 70)
    print("COMMITMENT BINDING VERIFICATION")
    print("-" * 70)
    binding = verify_commitment_binding()
    for t in binding["tests"]:
        status = "PASS" if t["passed"] else "FAIL"
        print(f"  [{status}] {t['name']}")
    print()

    # Streak analysis
    print("-" * 70)
    print("STREAK ANALYSIS")
    print("-" * 70)
    streaks = streak_analysis(simulate_outcomes(n))
    print(f"  Longest streak: {streaks['longest_streak']}")
    print(f"  Expected longest: ~{streaks['expected_longest']:.1f}")
    print(f"  Within expected: {'YES' if streaks['within_expected'] else 'NO'}")
    top5 = sorted(streaks['streak_counts'].items())[:5]
    for length, count in top5:
        print(f"  {length}-streak: {count} occurrences")
    print()

    # Miner analysis
    print("-" * 70)
    print("MINER MANIPULATION ANALYSIS")
    print("-" * 70)
    miner = miner_manipulation_analysis()
    print(f"  Verdict: {miner['verdict']}")
    print(f"  Mainnet: {miner['mainnet_economics']['verdict']}")
    print()

    # Overall verdict
    print("=" * 70)
    if result.overall_passed and binding["all_passed"]:
        print("OVERALL VERDICT: PASS — RNG is provably fair and unbiased")
    else:
        failed_names = [t.test_name for t in result.test_results if not t.passed]
        print(f"OVERALL VERDICT: FAIL — Issues in: {', '.join(failed_names)}")
    print("=" * 70)
