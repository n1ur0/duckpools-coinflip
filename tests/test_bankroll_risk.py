#!/usr/bin/env python3
"""
Integration tests for DuckPools Bankroll Risk Model (bankroll_risk.py)

Tests Kelly criterion, risk-of-ruin, variance projection, and
compute_full_risk_metrics with known-good mathematical values.

MAT-242: [MAT-12] Write integration tests for bankroll management system
Author: QA Developer Sr (Matsuzaka)
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from bankroll_risk import (
    GameParams,
    RiskMetrics,
    VarianceProjection,
    kelly_criterion,
    risk_of_ruin_continuous,
    min_bankroll_for_ror,
    n_bets_for_ev_exceeds_stddev,
    variance_projection,
    compute_full_risk_metrics,
    _expected_value,
    _variance,
    _normal_cdf,
    DEFAULT_P_HOUSE,
    DEFAULT_PAYOUT_MULTIPLIER,
    DEFAULT_HOUSE_EDGE,
)


# ═══════════════════════════════════════════════════════════════
# GameParams
# ═══════════════════════════════════════════════════════════════

class TestGameParams:
    """Test GameParams dataclass construction and derived values."""

    def test_default_values_match_constants(self):
        p = GameParams()
        assert p.p_house == DEFAULT_P_HOUSE == 0.5
        assert p.payout_multiplier == DEFAULT_PAYOUT_MULTIPLIER == 1.94
        assert p.house_edge == DEFAULT_HOUSE_EDGE == 0.03
        assert p.p_player == 0.5
        assert p.profit_on_win == 1.0
        assert pytest.approx(p.loss_on_loss) == 0.94

    def test_post_init_recalculates(self):
        p = GameParams(p_house=0.6, payout_multiplier=1.8)
        assert p.p_player == 0.4
        assert pytest.approx(p.loss_on_loss) == 0.8

    def test_custom_edge_params(self):
        """Dice game with 2% edge: payout = 1.96."""
        p = GameParams(p_house=0.5, payout_multiplier=1.96)
        assert pytest.approx(p.loss_on_loss) == 0.96
        # EV = 0.5*1.0 - 0.5*0.96 = 0.02 (2% edge)
        assert pytest.approx(_expected_value(p)) == 0.02


# ═══════════════════════════════════════════════════════════════
# Kelly Criterion
# ═══════════════════════════════════════════════════════════════

class TestKellyCriterion:
    """Test Kelly Criterion optimal bet fraction."""

    def test_coinflip_kelly_known_value(self):
        """Known-good: f* = 0.03/0.94 ≈ 0.0319149 (3.19%) for coinflip."""
        p = GameParams()
        k = kelly_criterion(p)
        expected = 0.03 / 0.94
        assert pytest.approx(k, rel=1e-6) == expected
        assert k > 0.03  # Should be slightly above house edge
        assert k < 0.04  # But well below 4%

    def test_kelly_returns_zero_for_negative_edge(self):
        """If the house has negative edge, Kelly says don't bet."""
        # Player has edge: payout_multiplier > 2.0
        p = GameParams(p_house=0.5, payout_multiplier=2.1)
        k = kelly_criterion(p)
        assert k == 0.0  # Negative Kelly → clamped to 0

    def test_kelly_zero_edge(self):
        """Fair game: Kelly = 0."""
        # Fair payout: 0.5*1.0 - 0.5*1.0 = 0
        p = GameParams(p_house=0.5, payout_multiplier=2.0)
        k = kelly_criterion(p)
        assert pytest.approx(k) == 0.0

    def test_kelly_high_edge(self):
        """50% house edge: p=0.75, payout=1.33, EV=0.75*1-0.25*0.33=0.6675."""
        p = GameParams(p_house=0.75, payout_multiplier=1.33)
        k = kelly_criterion(p)
        assert k > 0.5  # Should bet aggressively
        assert k <= 1.0  # Capped at full bankroll

    def test_kelly_division_by_zero_protection(self):
        """When W*L = 0, should return 0 (edgeless or degenerate)."""
        p = GameParams(p_house=0.5, payout_multiplier=1.0)
        # loss_on_loss = 0, so W*L = 0
        k = kelly_criterion(p)
        assert k == 0.0


# ═══════════════════════════════════════════════════════════════
# Expected Value & Variance
# ═══════════════════════════════════════════════════════════════

class TestExpectedValueAndVariance:
    """Test core EV and variance calculations."""

    def test_ev_coinflip(self):
        """EV = 0.5*1.0 - 0.5*0.94 = 0.03 per unit bet."""
        p = GameParams()
        ev = _expected_value(p)
        assert pytest.approx(ev) == 0.03

    def test_variance_coinflip(self):
        """Var = E[X²] - mu² = 0.5*1 + 0.5*0.8836 - 0.0009 = 0.9409."""
        p = GameParams()
        v = _variance(p)
        assert pytest.approx(v, rel=1e-6) == 0.9409

    def test_stddev_coinflip(self):
        """stddev = sqrt(0.9409) ≈ 0.9700."""
        p = GameParams()
        v = _variance(p)
        assert pytest.approx(math.sqrt(v), rel=1e-4) == 0.9700

    def test_variance_is_nonnegative(self):
        """Variance should always be >= 0 by definition."""
        p = GameParams()
        assert _variance(p) >= 0
        # Even with extreme params
        for mult in [0.5, 1.0, 2.0, 5.0, 10.0]:
            p2 = GameParams(payout_multiplier=mult)
            assert _variance(p2) >= 0


# ═══════════════════════════════════════════════════════════════
# Risk of Ruin
# ═══════════════════════════════════════════════════════════════

class TestRiskOfRuin:
    """Test risk-of-ruin continuous approximation."""

    def test_ror_decreases_with_bankroll(self):
        """More bankroll → less risk of ruin."""
        p = GameParams()
        ror_10 = risk_of_ruin_continuous(10, p)
        ror_100 = risk_of_ruin_continuous(100, p)
        ror_1000 = risk_of_ruin_continuous(1000, p)
        assert ror_10 > ror_100 > ror_1000

    def test_ror_one_unit_bankroll(self):
        """Bankroll = 1 max bet. High risk of ruin.
        
        RoR = exp(-2 * 0.03 * 1 / 0.9409) = exp(-0.06378) ≈ 0.9382
        """
        p = GameParams()
        ror = risk_of_ruin_continuous(1, p)
        assert 0.9 < ror < 1.0
        # Verify with hand calculation
        expected = math.exp(-2 * 0.03 * 1 / 0.9409)
        assert pytest.approx(ror, rel=1e-4) == expected

    def test_ror_100_units_bankroll(self):
        """Bankroll = 100 max bets. Should be very low RoR.
        
        RoR = exp(-2 * 0.03 * 100 / 0.9409) = exp(-6.378) ≈ 0.00169
        """
        p = GameParams()
        ror = risk_of_ruin_continuous(100, p)
        assert ror < 0.01  # Less than 1% risk
        expected = math.exp(-2 * 0.03 * 100 / 0.9409)
        assert pytest.approx(ror, rel=1e-3) == expected

    def test_ror_zero_bankroll(self):
        """Zero bankroll → certain ruin."""
        p = GameParams()
        ror = risk_of_ruin_continuous(0, p)
        assert ror == 1.0

    def test_ror_negative_bankroll(self):
        """Negative bankroll → certain ruin."""
        p = GameParams()
        ror = risk_of_ruin_continuous(-10, p)
        assert ror == 1.0

    def test_ror_underflow_clamp(self):
        """Extremely large bankroll shouldn't underflow to 0."""
        p = GameParams()
        ror = risk_of_ruin_continuous(100000, p)
        assert 0.0 <= ror <= 1.0


# ═══════════════════════════════════════════════════════════════
# Min Bankroll for Target RoR
# ═══════════════════════════════════════════════════════════════

class TestMinBankrollForRoR:
    """Test minimum bankroll calculation for target risk-of-ruin."""

    def test_min_bankroll_1pct_ror(self):
        """For <1% RoR with 1 ERG max bet.
        
        B = -0.9409 * ln(0.01) / (2 * 0.03) = -0.9409 * (-4.6052) / 0.06 ≈ 72.22 ERG
        """
        p = GameParams()
        min_b = min_bankroll_for_ror(0.01, 1e9, p)
        expected_units = -0.9409 * math.log(0.01) / (2 * 0.03)
        assert pytest.approx(min_b / 1e9, rel=1e-3) == expected_units
        assert min_b > 70e9  # More than 70 ERG

    def test_min_bankroll_stricter_ror(self):
        """Stricter RoR requires more bankroll."""
        p = GameParams()
        min_1pct = min_bankroll_for_ror(0.01, 1e9, p)
        min_01pct = min_bankroll_for_ror(0.001, 1e9, p)
        assert min_01pct > min_1pct
        # 0.1% RoR should need ~1.5x more bankroll than 1% RoR
        ratio = min_01pct / min_1pct
        assert 1.3 < ratio < 2.0

    def test_min_bankroll_negative_or_zero_ror(self):
        """Invalid target RoR → infinity."""
        p = GameParams()
        assert min_bankroll_for_ror(0.0, 1e9, p) == float('inf')
        assert min_bankroll_for_ror(-0.1, 1e9, p) == float('inf')
        assert min_bankroll_for_ror(1.0, 1e9, p) == float('inf')

    def test_min_bankroll_no_edge(self):
        """No house edge → can't guarantee survival → infinity."""
        p = GameParams(p_house=0.5, payout_multiplier=2.0)
        min_b = min_bankroll_for_ror(0.01, 1e9, p)
        assert min_b == float('inf')


# ═══════════════════════════════════════════════════════════════
# N Bets for EV > StdDev
# ═══════════════════════════════════════════════════════════════

class TestNBetsForReliability:
    """Test break-even point calculation."""

    def test_coinflip_n_bets(self):
        """N = (sigma/mu)^2 = (0.9700/0.03)^2 ≈ 1045 bets.
        
        This is the number of bets before the edge is statistically reliable.
        """
        p = GameParams()
        n = n_bets_for_ev_exceeds_stddev(p)
        assert 1000 < n < 1100
        expected = (0.9700 / 0.03) ** 2
        assert pytest.approx(n, rel=1e-2) == expected

    def test_no_edge_returns_infinity(self):
        """Without edge, EV never exceeds stddev."""
        p = GameParams(p_house=0.5, payout_multiplier=2.0)
        n = n_bets_for_ev_exceeds_stddev(p)
        assert n == float('inf')


# ═══════════════════════════════════════════════════════════════
# Variance Projection
# ═══════════════════════════════════════════════════════════════

class TestVarianceProjection:
    """Test CLT-based variance projection."""

    def test_projection_1000_rounds_1erg(self):
        """After 1000 rounds at 1 ERG avg bet.
        
        E[P&L] = 1000 * 0.03 * 1e9 = 30e9 nanoERG (30 ERG profit)
        Std[P&L] = sqrt(1000) * 0.97 * 1e9 ≈ 30.67e9 nanoERG
        """
        proj = variance_projection(1000, 1e9, GameParams())
        assert proj.n_rounds == 1000
        assert pytest.approx(proj.expected_profit / 1e9, rel=1e-3) == 30.0
        assert pytest.approx(proj.stddev / 1e9, rel=1e-2) == 30.67

    def test_projection_1sigma_range(self):
        """1-sigma range should contain the expected value."""
        proj = variance_projection(1000, 1e9, GameParams())
        low, high = proj.profit_1sigma_range
        assert low < proj.expected_profit < high
        assert pytest.approx(high - low) == 2 * proj.stddev

    def test_projection_2sigma_range(self):
        """2-sigma range should be wider."""
        proj = variance_projection(1000, 1e9, GameParams())
        low1, high1 = proj.profit_1sigma_range
        low2, high2 = proj.profit_2sigma_range
        assert low2 < low1 and high2 > high1

    def test_projection_3sigma_worst_case(self):
        """3-sigma worst case should be negative for small N.
        
        Even with positive EV, variance can cause losses in short runs.
        """
        proj = variance_projection(100, 1e9, GameParams())
        # 100 bets: EV = 3 ERG, stddev ≈ 9.7 ERG
        # 3-sigma worst = 3 - 3*9.7 = -26.1 (loss possible)
        assert proj.worst_case_3sigma < 0

    def test_projection_10000_rounds_profitable_likely(self):
        """After 10000 bets, probability of being profitable should be high.
        
        E = 300 ERG, Std = sqrt(10000)*0.97 = 97 ERG → z = 3.09
        P(profitable) = Phi(3.09) ≈ 0.999
        """
        proj = variance_projection(10000, 1e9, GameParams())
        assert proj.prob_profitable > 0.99

    def test_projection_prob_profitable_small_n(self):
        """With few bets, probability of profit should be closer to 50%.
        
        10 bets: EV = 0.3 ERG, Std = 3.07 ERG → z = 0.098
        P(profitable) ≈ 0.54 (barely above 50%)
        """
        proj = variance_projection(10, 1e9, GameParams())
        assert 0.45 < proj.prob_profitable < 0.65

    def test_projection_zero_rounds(self):
        """Zero rounds → zero everything, prob = 0.5."""
        proj = variance_projection(0, 1e9, GameParams())
        assert proj.n_rounds == 0
        assert proj.expected_profit == 0
        assert proj.stddev == 0
        assert proj.prob_profitable == 0.5

    def test_projection_larger_bets_scale_linearly(self):
        """Doubling bet size should double expected profit and stddev."""
        p1 = variance_projection(1000, 1e9, GameParams())
        p2 = variance_projection(1000, 2e9, GameParams())
        assert pytest.approx(p2.expected_profit) == 2 * p1.expected_profit
        assert pytest.approx(p2.stddev) == 2 * p1.stddev


# ═══════════════════════════════════════════════════════════════
# Normal CDF (internal)
# ═══════════════════════════════════════════════════════════════

class TestNormalCDF:
    """Test the normal CDF approximation used internally."""

    def test_cdf_symmetry(self):
        assert pytest.approx(_normal_cdf(0)) == 0.5
        assert pytest.approx(_normal_cdf(1) + _normal_cdf(-1)) == 1.0
        assert pytest.approx(_normal_cdf(2) + _normal_cdf(-2)) == 1.0

    def test_cdf_bounds(self):
        assert _normal_cdf(-8) == 0.0
        assert _normal_cdf(8) == 1.0
        assert _normal_cdf(-100) == 0.0
        assert _normal_cdf(100) == 1.0

    def test_cdf_known_values(self):
        """Spot-check against standard normal table."""
        assert pytest.approx(_normal_cdf(1.0), abs=0.001) == 0.8413
        assert pytest.approx(_normal_cdf(1.96), abs=0.001) == 0.9750
        assert pytest.approx(_normal_cdf(2.58), abs=0.001) == 0.9951
        assert pytest.approx(_normal_cdf(-1.96), abs=0.001) == 0.0250


# ═══════════════════════════════════════════════════════════════
# Compute Full Risk Metrics (integration)
# ═══════════════════════════════════════════════════════════════

class TestComputeFullRiskMetrics:
    """Integration test: compute_full_risk_metrics combines all sub-calculations."""

    def test_100erg_bankroll_1erg_max_bet(self):
        """100 ERG bankroll, 1 ERG max bet = 100 bankroll units.
        
        Kelly ≈ 3.19% → max_bet_kelly ≈ 3.19 ERG
        RoR at 100 units ≈ exp(-6.378) ≈ 0.0017 (<0.2%)
        """
        metrics = compute_full_risk_metrics(100e9, 1e9)
        assert pytest.approx(metrics.kelly_fraction, rel=1e-3) == 0.0319
        assert pytest.approx(metrics.kelly_fraction_quarter, rel=1e-3) == 0.00798
        assert metrics.risk_of_ruin < 0.01  # <1% RoR
        assert metrics.bankroll_units == 100.0
        assert metrics.safety_ratio > 1.0  # Above minimum recommended
        assert metrics.max_bet_kelly > 3e9  # ~3.19 ERG
        assert metrics.max_bet_quarter_kelly < metrics.max_bet_kelly
        assert pytest.approx(metrics.expected_value_per_bet) == 0.03
        assert pytest.approx(metrics.variance_per_bet, rel=1e-4) == 0.9409

    def test_5erg_bankroll_1erg_max_bet(self):
        """5 ERG bankroll, 1 ERG max bet = 5 bankroll units.
        
        This is close to the ACTUAL current state (5.7 ERG).
        RoR should be very high (>50%).
        """
        metrics = compute_full_risk_metrics(5e9, 1e9)
        assert metrics.bankroll_units == 5.0
        assert metrics.risk_of_ruin > 0.5  # Very risky
        assert metrics.safety_ratio < 1.0  # Below recommended
        assert metrics.risk_of_ruin < 1.0  # But not certain ruin

    def test_zero_bankroll(self):
        """Zero bankroll → degenerate state."""
        metrics = compute_full_risk_metrics(0, 1e9)
        assert metrics.bankroll_units == 0.0
        assert metrics.risk_of_ruin == 1.0
        assert metrics.safety_ratio == 0.0

    def test_zero_max_bet(self):
        """Zero max bet → infinity units → effectively zero RoR."""
        metrics = compute_full_risk_metrics(100e9, 0)
        assert metrics.bankroll_units == float('inf')
        # With infinite bankroll units, RoR → 0 (can never go broke if you
        # never bet). The exp(-inf) clamp gives ~0.
        assert metrics.risk_of_ruin < 0.001

    def test_custom_game_params(self):
        """Custom params for a different game."""
        p = GameParams(p_house=0.5, payout_multiplier=1.96)  # 2% edge dice
        metrics = compute_full_risk_metrics(100e9, 1e9, params=p)
        assert metrics.kelly_fraction < 0.032  # Lower Kelly for lower edge

    def test_avg_bet_default_equals_max_bet(self):
        """When avg_bet not specified, defaults to max_single_bet."""
        m1 = compute_full_risk_metrics(100e9, 1e9)
        m2 = compute_full_risk_metrics(100e9, 1e9, avg_bet_nanoerg=1e9)
        assert m1.n_bets_for_1sigma == m2.n_bets_for_1sigma

    def test_all_fields_populated(self):
        """Every field in RiskMetrics should have a value."""
        metrics = compute_full_risk_metrics(100e9, 1e9)
        for field_name in RiskMetrics.__dataclass_fields__:
            val = getattr(metrics, field_name)
            assert val is not None, f"Field {field_name} is None"


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Boundary and edge case testing."""

    def test_extreme_house_edge_50pct(self):
        """50% house edge (loaded game)."""
        p = GameParams(p_house=0.75, payout_multiplier=1.34)
        ev = _expected_value(p)
        assert ev > 0.4  # Very profitable
        k = kelly_criterion(p)
        assert k > 0.3  # Aggressive betting justified

    def test_tiny_house_edge_0_1pct(self):
        """0.1% house edge (nearly fair)."""
        # EV = 0.5*1.0 - 0.5*0.998 = 0.001
        p = GameParams(p_house=0.5, payout_multiplier=1.998)
        ev = _expected_value(p)
        assert pytest.approx(ev, rel=1e-3) == 0.001
        k = kelly_criterion(p)
        assert k > 0
        assert k < 0.01  # Very small Kelly
        # Need many more bets for reliability
        n = n_bets_for_ev_exceeds_stddev(p)
        assert n > 900000  # Almost a million bets needed

    def test_projection_scaling(self):
        """Projection should scale linearly with bet size."""
        for bet in [0.1e9, 1e9, 10e9, 100e9]:
            proj = variance_projection(1000, bet, GameParams())
            assert proj.expected_profit > 0
            assert proj.stddev > 0
            assert proj.worst_case_3sigma < proj.expected_profit  # For 1000 bets


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
