#!/usr/bin/env python3
"""
Tests for the RNG Statistical Test Suite (Issue 01c50a13)

Tests verify:
1. The suite uses the CORRECT blake2b256 scheme (not SHA-256)
2. Each statistical test produces valid results
3. Known-biased sequences are correctly detected
4. Fair sequences pass all tests
5. Edge cases are handled gracefully
6. Commitment binding verification works
7. The suite is self-consistent (same data = same results)

CRITICAL: These tests validate the PRODUCTION scheme:
    blake2b256(blockId_raw_bytes || playerSecret_raw_bytes)[0] % 2
"""

import hashlib
import math
import secrets
import sys
import os

import pytest

# Add backend to path — handle running from worktree root or main project root
_test_dir = os.path.dirname(os.path.abspath(__file__))
for _candidate in [
    os.path.join(_test_dir, "..", "backend"),
    os.path.join(_test_dir, "..", "..", "backend"),
]:
    _candidate = os.path.abspath(_candidate)
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from rng_statistical_suite import (
    SingleTestResult,
    SuiteResult,
    autocorrelation_test,
    chi_square_test,
    frequency_test,
    kolmogorov_smirnov_test,
    miner_manipulation_analysis,
    runs_test,
    serial_test,
    shannon_entropy,
    simulate_outcomes,
    streak_analysis,
    verify_commitment_binding,
    run_full_suite,
    _chi2_sf,
)
from rng_module import compute_rng, generate_commit, verify_commit


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_fair_sequence(n: int) -> list:
    """Generate a fair sequence using production RNG scheme."""
    return simulate_outcomes(n)


def make_biased_sequence(n: int, p_heads: float = 0.7) -> list:
    """
    Generate a biased sequence where outcome=1 occurs with probability p_heads.
    Uses a deterministic but biased PRNG (not blake2b256).
    """
    import random
    rng = random.Random(42)  # Fixed seed for reproducibility
    return [1 if rng.random() < p_heads else 0 for _ in range(n)]


def make_alternating_sequence(n: int) -> list:
    """Generate a perfectly alternating sequence (010101...)."""
    return [i % 2 for i in range(n)]


# ─── Scheme Correctness Tests ─────────────────────────────────────────────────


class TestSchemeCorrectness:
    """Verify the suite uses the CORRECT blake2b256 scheme."""

    def test_uses_blake2b256_not_sha256(self):
        """
        CRITICAL: The production RNG MUST use blake2b256, not SHA-256.
        On-chain contract uses the blake2b256 opcode.
        """
        block_hash = "a" * 64  # Valid 64-char hex
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])

        # Compute using production module
        outcome = compute_rng(block_hash, secret)

        # Manually verify with blake2b256
        block_bytes = bytes.fromhex(block_hash)
        rng_data = block_bytes + secret
        blake_hash = hashlib.blake2b(rng_data, digest_size=32).digest()
        expected = blake_hash[0] % 2

        assert outcome == expected, (
            "RNG module does NOT use blake2b256! "
            "This would cause every on-chain reveal to FAIL."
        )

    def test_does_not_use_utf8_encoded_hash(self):
        """
        CRITICAL: Block hash must be hex-decoded (raw bytes), NOT UTF-8 encoded.
        On-chain contract uses CONTEXT.preHeader.parentId (Coll[Byte]).
        """
        block_hash = "b" * 64
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])

        outcome = compute_rng(block_hash, secret)

        # UTF-8 encoded would give different result
        utf8_hash = block_hash.encode("utf-8") + secret
        sha_wrong = hashlib.blake2b(utf8_hash, digest_size=32).digest()
        wrong_outcome = sha_wrong[0] % 2

        # These should NOT match (they encode the block hash differently)
        # With blake2b256's avalanche effect, different inputs -> different outputs
        # (They could match by chance at ~50%, so we test with multiple hashes)
        mismatches = 0
        for i in range(20):
            bh = f"{i:064x}"
            correct = compute_rng(bh, secret)
            utf8_data = bh.encode("utf-8") + secret
            wrong = hashlib.blake2b(utf8_data, digest_size=32).digest()[0] % 2
            if correct != wrong:
                mismatches += 1

        # At least some should differ (probability of all matching = 2^-20)
        assert mismatches > 0, (
            "Block hash appears to be UTF-8 encoded instead of hex-decoded! "
            "This would cause on-chain/off-chain mismatch."
        )

    def test_commitment_uses_blake2b256(self):
        """Commitment scheme must also use blake2b256."""
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        choice = 0

        commit = generate_commit(secret, choice)

        # Manual blake2b256 verification
        data = secret + bytes([choice])
        expected = hashlib.blake2b(data, digest_size=32).hexdigest()

        assert commit == expected, "Commitment does not use blake2b256!"


# ─── Frequency Test ───────────────────────────────────────────────────────────


class TestFrequencyTest:
    def test_fair_sequence_passes(self):
        outcomes = make_fair_sequence(10000)
        result = frequency_test(outcomes)
        assert result.test_name == "Frequency Test (Monobit)"
        assert result.passed is True
        assert 0 <= result.p_value <= 1

    def test_biased_sequence_fails(self):
        outcomes = make_biased_sequence(10000, p_heads=0.8)
        result = frequency_test(outcomes)
        assert result.passed is False
        assert result.p_value < 0.01

    def test_all_zeros_fails(self):
        outcomes = [0] * 1000
        result = frequency_test(outcomes)
        assert result.passed is False

    def test_empty_sequence(self):
        result = frequency_test([])
        assert result.passed is False

    def test_single_element(self):
        result = frequency_test([0])
        # Single element can't be tested for randomness
        assert result.p_value is not None


# ─── Chi-Squared Test ─────────────────────────────────────────────────────────


class TestChiSquaredTest:
    def test_fair_sequence_passes(self):
        outcomes = make_fair_sequence(10000)
        result = chi_square_test(outcomes)
        assert result.test_name == "Chi-Squared Test (Uniformity)"
        assert result.passed is True

    def test_perfect_uniformity(self):
        outcomes = [0, 1] * 5000
        result = chi_square_test(outcomes)
        assert result.statistic == pytest.approx(0.0, abs=1e-10)
        assert result.p_value == pytest.approx(1.0, abs=0.01)

    def test_biased_sequence_fails(self):
        outcomes = make_biased_sequence(10000, p_heads=0.75)
        result = chi_square_test(outcomes)
        assert result.passed is False

    def test_empty_sequence(self):
        result = chi_square_test([])
        assert result.passed is False

    def test_p_value_exact_for_df1(self):
        """Verify p-value uses exact erfc formula for df=1."""
        # For chi_sq=0, p_value should be 1.0
        assert _chi2_sf(0.0, 1) == pytest.approx(1.0, abs=1e-10)

        # For chi_sq=6.635 (critical value at alpha=0.01), p should be ~0.01
        p = _chi2_sf(6.6349, 1)
        assert 0.005 < p < 0.015, f"p={p} should be ~0.01 at critical value"

        # For chi_sq=3.841 (critical value at alpha=0.05), p should be ~0.05
        p = _chi2_sf(3.8415, 1)
        assert 0.03 < p < 0.07, f"p={p} should be ~0.05"


# ─── Runs Test ────────────────────────────────────────────────────────────────


class TestRunsTest:
    def test_fair_sequence_passes(self):
        outcomes = make_fair_sequence(10000)
        result = runs_test(outcomes)
        assert "Runs Test" in result.test_name
        assert result.passed is True

    def test_alternating_sequence_fails(self):
        """Alternating 010101... is NOT random — should fail independence."""
        outcomes = make_alternating_sequence(1000)
        result = runs_test(outcomes)
        assert result.passed is False

    def test_all_same_fails(self):
        """All same value is clearly non-random."""
        outcomes = [0] * 1000
        result = runs_test(outcomes)
        assert result.passed is False

    def test_too_few_outcomes(self):
        result = runs_test([0])
        assert result.passed is False


# ─── Kolmogorov-Smirnov Test ──────────────────────────────────────────────────


class TestKSTest:
    def test_fair_sequence_passes(self):
        outcomes = make_fair_sequence(10000)
        result = kolmogorov_smirnov_test(outcomes)
        assert result.test_name == "Kolmogorov-Smirnov Test"
        assert result.passed is True

    def test_biased_sequence_fails(self):
        outcomes = make_biased_sequence(5000, p_heads=0.8)
        result = kolmogorov_smirnov_test(outcomes)
        assert result.passed is False

    def test_too_few_outcomes(self):
        result = kolmogorov_smirnov_test([0, 1, 0, 1])
        assert result.passed is False


# ─── Autocorrelation Test ─────────────────────────────────────────────────────


class TestAutocorrelation:
    def test_fair_sequence_passes_lag1(self):
        outcomes = make_fair_sequence(10000)
        result = autocorrelation_test(outcomes, lag=1)
        assert "lag=1" in result.test_name
        assert result.passed is True

    def test_fair_sequence_passes_lag10(self):
        outcomes = make_fair_sequence(10000)
        result = autocorrelation_test(outcomes, lag=10)
        assert result.passed is True

    def test_alternating_sequence_fails(self):
        """Alternating sequence has strong autocorrelation at lag=2."""
        outcomes = make_alternating_sequence(1000)
        result = autocorrelation_test(outcomes, lag=2)
        assert result.passed is False

    def test_insufficient_data(self):
        result = autocorrelation_test([0, 1], lag=1)
        assert result.passed is False


# ─── Serial Test ──────────────────────────────────────────────────────────────


class TestSerialTest:
    def test_fair_sequence_passes(self):
        outcomes = make_fair_sequence(10000)
        result = serial_test(outcomes, pattern_length=2)
        assert "Serial Test" in result.test_name
        assert result.passed is True

    def test_biased_sequence_detected(self):
        outcomes = make_biased_sequence(5000, p_heads=0.75)
        result = serial_test(outcomes, pattern_length=2)
        assert result.passed is False

    def test_insufficient_data(self):
        result = serial_test([0, 1], pattern_length=2)
        assert result.passed is False


# ─── Streak Analysis ──────────────────────────────────────────────────────────


class TestStreakAnalysis:
    def test_fair_sequence_within_expected(self):
        outcomes = make_fair_sequence(10000)
        result = streak_analysis(outcomes)
        assert result["within_expected"] is True
        assert result["longest_streak"] > 0

    def test_expected_longest_streak(self):
        """For n=10000, expected longest streak ~ log2(10000) ~ 13.3."""
        outcomes = make_fair_sequence(10000)
        result = streak_analysis(outcomes)
        expected = result["expected_longest"]
        assert 12 < expected < 15

    def test_empty_sequence(self):
        result = streak_analysis([])
        assert result["longest_streak"] == 0


# ─── Shannon Entropy ──────────────────────────────────────────────────────────


class TestShannonEntropy:
    def test_perfect_fair_entropy(self):
        counts = {0: 500, 1: 500}
        assert shannon_entropy(counts) == pytest.approx(1.0, rel=1e-10)

    def test_biased_entropy(self):
        counts = {0: 900, 1: 100}
        e = shannon_entropy(counts)
        assert e < 1.0
        assert e > 0.0

    def test_zero_entropy(self):
        counts = {0: 100, 1: 0}
        assert shannon_entropy(counts) == 0.0

    def test_empty_counts(self):
        assert shannon_entropy({}) == 0.0


# ─── Commitment Binding ──────────────────────────────────────────────────────


class TestCommitmentBinding:
    def test_all_binding_tests_pass(self):
        result = verify_commitment_binding(n_samples=1000)
        assert result["all_passed"] is True

    def test_different_secrets_different_commits(self):
        for _ in range(100):
            s1 = secrets.token_bytes(8)
            s2 = secrets.token_bytes(8)
            assert s1 != s2
            c1 = generate_commit(s1, 0)
            c2 = generate_commit(s2, 0)
            assert c1 != c2

    def test_different_choices_different_commits(self):
        for _ in range(100):
            s = secrets.token_bytes(8)
            c0 = generate_commit(s, 0)
            c1 = generate_commit(s, 1)
            assert c0 != c1

    def test_verification_accepts_valid(self):
        for _ in range(100):
            s = secrets.token_bytes(8)
            c = generate_commit(s, 0)
            assert verify_commit(c, s, 0) is True

    def test_verification_rejects_wrong_choice(self):
        for _ in range(100):
            s = secrets.token_bytes(8)
            c = generate_commit(s, 0)
            assert verify_commit(c, s, 1) is False

    def test_verification_rejects_wrong_secret(self):
        for _ in range(100):
            s = secrets.token_bytes(8)
            c = generate_commit(s, 0)
            assert verify_commit(c, secrets.token_bytes(8), 0) is False


# ─── Full Suite ───────────────────────────────────────────────────────────────


class TestFullSuite:
    def test_full_suite_passes(self):
        result = run_full_suite(num_simulations=10000, alpha=0.05)
        assert isinstance(result, SuiteResult)
        assert result.total_tests > 0
        assert result.overall_passed is True
        assert result.entropy_bits > 0.99
        assert 0.4 < result.heads_ratio < 0.6

    def test_suite_structure(self):
        result = run_full_suite(num_simulations=1000)
        assert result.total_tests > 0
        assert result.passed_tests + result.failed_tests == result.total_tests
        assert len(result.test_results) == result.total_tests

    def test_suite_test_names(self):
        result = run_full_suite(num_simulations=1000)
        names = [t.test_name for t in result.test_results]
        assert any("Frequency" in n for n in names)
        assert any("Chi-Squared" in n for n in names)
        assert any("Runs" in n for n in names)
        assert any("Kolmogorov" in n for n in names)
        assert any("Autocorrelation" in n for n in names)
        assert any("Serial" in n for n in names)

    def test_suite_consistency(self):
        """Same RNG seed should produce same results if we fix the inputs."""
        block_hashes = [f"{i:064x}" for i in range(1000)]
        secrets_list = [bytes([i % 256] * 8) for i in range(1000)]

        outcomes_a = [
            compute_rng(block_hashes[i], secrets_list[i]) for i in range(1000)
        ]
        outcomes_b = [
            compute_rng(block_hashes[i], secrets_list[i]) for i in range(1000)
        ]

        assert outcomes_a == outcomes_b

        # Tests should give identical results
        r1 = frequency_test(outcomes_a)
        r2 = frequency_test(outcomes_b)
        assert r1.statistic == r2.statistic
        assert r1.p_value == r2.p_value
        assert r1.passed == r2.passed


# ─── Miner Analysis ──────────────────────────────────────────────────────────


class TestMinerAnalysis:
    def test_returns_dict(self):
        result = miner_manipulation_analysis()
        assert isinstance(result, dict)
        assert result["verdict"] == "SAFE"
        assert len(result["mitigations"]) > 0

    def test_economic_infeasibility(self):
        result = miner_manipulation_analysis()
        economics = result["mainnet_economics"]
        assert economics["verdict"] == "NOT economically viable"


# ─── _chi2_sf (Chi-square survival function) ─────────────────────────────────


class TestChi2SurvivalFunction:
    def test_zero(self):
        assert _chi2_sf(0.0, 1) == pytest.approx(1.0, abs=1e-10)
        assert _chi2_sf(0.0, 5) == pytest.approx(1.0, abs=1e-10)

    def test_critical_values_df1(self):
        # alpha=0.05, df=1: critical=3.841
        p = _chi2_sf(3.8415, 1)
        assert 0.04 < p < 0.06

        # alpha=0.01, df=1: critical=6.635
        p = _chi2_sf(6.6349, 1)
        assert 0.005 < p < 0.015

    def test_critical_values_df3(self):
        # alpha=0.05, df=3: critical=7.815
        p = _chi2_sf(7.815, 3)
        assert 0.04 < p < 0.06

        # alpha=0.01, df=3: critical=11.34
        p = _chi2_sf(11.34, 3)
        assert 0.005 < p < 0.015

    def test_monotonicity(self):
        """P-value should decrease as chi2 increases."""
        p1 = _chi2_sf(1.0, 5)
        p2 = _chi2_sf(5.0, 5)
        p3 = _chi2_sf(10.0, 5)
        assert p1 > p2 > p3 > 0

    def test_large_chi2_gives_small_p(self):
        p = _chi2_sf(100.0, 5)
        assert p < 0.001

    def test_negative_x_returns_one(self):
        assert _chi2_sf(-1.0, 5) == 1.0


# ─── Simulate Outcomes ───────────────────────────────────────────────────────


class TestSimulateOutcomes:
    def test_generates_correct_count(self):
        outcomes = simulate_outcomes(1000)
        assert len(outcomes) == 1000
        assert all(o in (0, 1) for o in outcomes)

    def test_with_custom_block_hashes(self):
        hashes = [f"{i:064x}" for i in range(100)]
        outcomes = simulate_outcomes(250, block_hashes=hashes)
        assert len(outcomes) == 250

    def test_deterministic_with_fixed_inputs(self):
        """Same block hashes + same secrets should give same outcomes."""
        bh = "a" * 64
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        o1 = compute_rng(bh, secret)
        o2 = compute_rng(bh, secret)
        assert o1 == o2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
