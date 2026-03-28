"""
DuckPools - Bankroll Risk Model

Mathematical models for bankroll sizing, risk-of-ruin, and variance analysis
for the DuckPools coinflip protocol.

Based on:
- Kelly Criterion (optimal bet sizing)
- Gambler's Ruin / Risk-of-Ruin (probability of depleting bankroll)
- Central Limit Theorem (variance / drawdown estimates)

MAT-184: Design bankroll sizing model and variance analysis
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("duckpools.bankroll_risk")


# ─── Game Parameters ──────────────────────────────────────────────

# The coinflip RNG (first_byte % 2) is a true 50/50 split.
# The 3% house edge is embedded entirely in the payout multiplier:
#   Player bets A. On win: receives 1.94*A (instead of fair 2*A).
#   House edge = 1 - 0.5 * 1.94 = 0.03

DEFAULT_P_HOUSE = 0.5         # Probability house wins per round
DEFAULT_PAYOUT_MULTIPLIER = 1.94  # Player receives this x on win
DEFAULT_HOUSE_EDGE = 0.03     # 3% house edge


# ─── Data Classes ──────────────────────────────────────────────────

@dataclass
class GameParams:
    """Parameters describing the game's probability structure."""
    p_house: float = DEFAULT_P_HOUSE       # P(house wins) per round
    p_player: float = 1.0 - DEFAULT_P_HOUSE  # P(player wins) per round
    payout_multiplier: float = DEFAULT_PAYOUT_MULTIPLIER  # Player payout on win
    house_edge: float = DEFAULT_HOUSE_EDGE  # Expected profit per unit bet

    # Derived per-unit-bet statistics (from house perspective)
    profit_on_win: float = 1.0       # House keeps the bet
    loss_on_loss: float = payout_multiplier - 1.0  # House pays net

    def __post_init__(self):
        """Recalculate derived values if params change."""
        self.p_player = 1.0 - self.p_house
        self.loss_on_loss = self.payout_multiplier - 1.0


@dataclass
class RiskMetrics:
    """Computed risk metrics for the current bankroll state."""
    kelly_fraction: float = 0.0          # Optimal fraction of bankroll per bet
    kelly_fraction_quarter: float = 0.0  # 1/4 Kelly (conservative)
    risk_of_ruin: float = 0.0            # Current RoR
    min_bankroll_1pct: float = 0.0       # Min bankroll for <1% RoR
    min_bankroll_0_1pct: float = 0.0     # Min bankroll for <0.1% RoR
    max_bet_kelly: float = 0.0           # Max bet at full Kelly
    max_bet_quarter_kelly: float = 0.0   # Max bet at 1/4 Kelly
    bankroll_units: float = 0.0          # bankroll / max_single_bet
    safety_ratio: float = 0.0            # bankroll / min_recommended_bankroll
    expected_value_per_bet: float = 0.0  # House EV per unit bet
    variance_per_bet: float = 0.0        # Variance per unit bet
    stddev_per_bet: float = 0.0          # Std dev per unit bet
    n_bets_for_1sigma: float = 0.0       # Bets needed for EV > 1 std dev


@dataclass
class VarianceProjection:
    """Variance analysis over N bet rounds."""
    n_rounds: int = 0
    expected_profit: float = 0.0
    stddev: float = 0.0
    profit_1sigma_range: tuple = (0.0, 0.0)
    profit_2sigma_range: tuple = (0.0, 0.0)
    worst_case_3sigma: float = 0.0
    prob_profitable: float = 0.0  # Approx probability of being profitable


# ─── Core Calculations ────────────────────────────────────────────

def kelly_criterion(params: GameParams) -> float:
    """
    Calculate the Kelly Criterion optimal bet fraction.

    For a bet where:
      - Win (prob p): profit = W per unit wagered
      - Lose (prob q): loss = L per unit wagered

    Generalized Kelly:
      f* = (p*W - q*L) / (W*L)

    For DuckPools coinflip (house perspective):
      - Win (p=0.5): profit = +1.0 (keep the bet)
      - Lose (p=0.5): loss = -0.94 (pay 1.94x, received 1x)

      f* = (0.5 * 1.0 - 0.5 * 0.94) / (1.0 * 0.94)
         = 0.03 / 0.94
         = ~0.0319 (3.19%)

    This is very close to the house edge (3%) which is expected
    for a near-even game with small edge.
    """
    p = params.p_house
    q = params.p_player
    W = params.profit_on_win
    L = params.loss_on_loss

    if W * L <= 0:
        return 0.0

    f_star = (p * W - q * L) / (W * L)
    # Cap at 1.0: Kelly > 1 means "bet more than your entire bankroll" which is
    # nonsensical for bankroll management. This occurs with very high edge games.
    return min(1.0, max(0.0, f_star))


def risk_of_ruin_continuous(
    bankroll_units: float,
    params: GameParams,
) -> float:
    """
    Risk-of-ruin using continuous approximation (Brownian motion).

    For a biased random walk with drift mu and variance sigma^2,
    starting at position B, probability of hitting 0 before infinity:

      RoR ≈ exp(-2 * mu * B / sigma^2)

    This is the standard formula used in quantitative finance and
    professional gambling bankroll management.

    Per unit bet (house perspective):
      mu = E[profit] = p*W - q*L = 0.5*1.0 - 0.5*0.94 = 0.03
      sigma^2 = E[X^2] - mu^2
              = p*W^2 + q*L^2 - mu^2
              = 0.5*1.0 + 0.5*0.8836 - 0.0009
              = 0.9409

      RoR = exp(-2 * 0.03 * B / 0.9409) = exp(-0.06378 * B)
    """
    mu = _expected_value(params)
    sigma_sq = _variance(params)

    if sigma_sq <= 0 or bankroll_units <= 0:
        return 1.0  # Certain ruin

    exponent = -2.0 * mu * bankroll_units / sigma_sq
    return math.exp(max(exponent, -100))  # Clamp to avoid underflow


def min_bankroll_for_ror(
    target_ror: float,
    max_bet: float,
    params: GameParams,
) -> float:
    """
    Calculate minimum bankroll needed for a target risk-of-ruin.

    Solves: target_ror = exp(-2 * mu * B / sigma^2)
    for B:

      B = -sigma^2 * ln(target_ror) / (2 * mu)

    Returns bankroll in same units as max_bet.
    """
    if target_ror >= 1.0 or target_ror <= 0.0:
        return float('inf')

    mu = _expected_value(params)
    sigma_sq = _variance(params)

    if mu <= 0:
        return float('inf')  # No edge = can't guarantee survival

    # Solve for bankroll_units first
    bankroll_units = -sigma_sq * math.log(target_ror) / (2.0 * mu)

    # Convert to absolute units
    return bankroll_units * max_bet


def n_bets_for_ev_exceeds_stddev(params: GameParams) -> float:
    """
    Number of bets needed for the expected cumulative profit to
    exceed one standard deviation of cumulative P&L.

    After N bets:
      E[P&L] = N * mu
      Std[P&L] = sqrt(N) * sigma

    E[P&L] > Std[P&L] when:
      N * mu > sqrt(N) * sigma
      sqrt(N) > sigma / mu
      N > (sigma / mu)^2

    For DuckPools: sigma=0.970, mu=0.03 => N > (0.970/0.03)^2 = 1045 bets
    This is the "break-even" point where the edge becomes statistically reliable.
    """
    mu = _expected_value(params)
    sigma = math.sqrt(_variance(params))

    if mu <= 0:
        return float('inf')

    return (sigma / mu) ** 2


def variance_projection(
    n_rounds: int,
    avg_bet_size: float,
    params: GameParams,
) -> VarianceProjection:
    """
    Project variance and drawdown statistics over N bet rounds.

    Uses CLT approximation for large N:
      E[P&L] = N * mu * avg_bet_size
      Std[P&L] = sqrt(N) * sigma * avg_bet_size
    """
    mu = _expected_value(params)
    sigma = math.sqrt(_variance(params))

    expected = n_rounds * mu * avg_bet_size
    stddev = math.sqrt(n_rounds) * sigma * avg_bet_size

    return VarianceProjection(
        n_rounds=n_rounds,
        expected_profit=expected,
        stddev=stddev,
        profit_1sigma_range=(
            expected - stddev,
            expected + stddev,
        ),
        profit_2sigma_range=(
            expected - 2 * stddev,
            expected + 2 * stddev,
        ),
        worst_case_3sigma=expected - 3 * stddev,
        prob_profitable=_approx_prob_profitable(
            n_rounds, mu, sigma, avg_bet_size
        ),
    )


def compute_full_risk_metrics(
    bankroll_nanoerg: int,
    max_single_bet_nanoerg: int,
    avg_bet_nanoerg: Optional[int] = None,
    params: Optional[GameParams] = None,
) -> RiskMetrics:
    """
    Compute all risk metrics for the current bankroll state.

    Args:
        bankroll_nanoerg: Current bankroll in nanoERG
        max_single_bet_nanoerg: Maximum allowed single bet in nanoERG
        avg_bet_nanoerg: Average bet size (defaults to max_single_bet)
        params: Game parameters (defaults to coinflip defaults)

    Returns:
        RiskMetrics with all computed values
    """
    if params is None:
        params = GameParams()
    if avg_bet_nanoerg is None:
        avg_bet_nanoerg = max_single_bet_nanoerg

    kelly = kelly_criterion(params)
    kelly_quarter = kelly / 4.0

    # Bankroll in units of max bet
    bankroll_units = (
        bankroll_nanoerg / max_single_bet_nanoerg
        if max_single_bet_nanoerg > 0
        else float('inf')
    )

    # Risk of ruin
    ror = risk_of_ruin_continuous(bankroll_units, params)

    # Min bankroll recommendations
    min_bank_1pct = min_bankroll_for_ror(0.01, max_single_bet_nanoerg, params)
    min_bank_0_1pct = min_bankroll_for_ror(0.001, max_single_bet_nanoerg, params)

    # Max bet sizes
    max_bet_kelly = kelly * bankroll_nanoerg
    max_bet_quarter = kelly_quarter * bankroll_nanoerg

    # Safety ratio (how much above the 1% RoR threshold)
    safety_ratio = (
        bankroll_nanoerg / min_bank_1pct
        if min_bank_1pct > 0
        else float('inf')
    )

    # Per-bet statistics
    ev = _expected_value(params)
    var = _variance(params)
    n_break_even = n_bets_for_ev_exceeds_stddev(params)

    return RiskMetrics(
        kelly_fraction=kelly,
        kelly_fraction_quarter=kelly_quarter,
        risk_of_ruin=ror,
        min_bankroll_1pct=min_bank_1pct,
        min_bankroll_0_1pct=min_bank_0_1pct,
        max_bet_kelly=max_bet_kelly,
        max_bet_quarter_kelly=max_bet_quarter,
        bankroll_units=bankroll_units,
        safety_ratio=safety_ratio,
        expected_value_per_bet=ev,
        variance_per_bet=var,
        stddev_per_bet=math.sqrt(var),
        n_bets_for_1sigma=n_break_even,
    )


# ─── Internal Helpers ─────────────────────────────────────────────

def _expected_value(params: GameParams) -> float:
    """Expected profit per unit bet (house perspective)."""
    return params.p_house * params.profit_on_win - params.p_player * params.loss_on_loss


def _variance(params: GameParams) -> float:
    """Variance per unit bet (house perspective)."""
    mu = _expected_value(params)
    W = params.profit_on_win
    L = params.loss_on_loss
    return (
        params.p_house * W * W
        + params.p_player * L * L
        - mu * mu
    )


def _approx_prob_profitable(
    n_rounds: int, mu: float, sigma: float, avg_bet: float
) -> float:
    """
    Approximate probability of being profitable after N rounds.

    Uses CLT: P(P&L > 0) ≈ 1 - Phi(-E[P&L] / Std[P&L])
    where Phi is the standard normal CDF.
    """
    if n_rounds <= 0 or sigma <= 0:
        return 0.5

    expected = n_rounds * mu * avg_bet
    stddev = math.sqrt(n_rounds) * sigma * avg_bet

    if stddev <= 0:
        return 1.0 if expected > 0 else 0.0

    z = expected / stddev
    return _normal_cdf(z)


def _normal_cdf(x: float) -> float:
    """
    Standard normal CDF approximation (Abramowitz & Stegun 26.2.17).
    Maximum error: 7.5e-8. Good enough for bankroll risk calculations.
    """
    if x <= -6:
        return 0.0
    if x >= 6:
        return 1.0

    # Rational approximation (Abramowitz & Stegun 26.2.17)
    # Maximum error: 7.5e-8.
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    p = d * math.exp(-x * x / 2.0) * (
        0.319381530 * t
        + -0.356563782 * t * t
        + 1.781477937 * t * t * t
        + -1.821255978 * t * t * t * t
        + 1.330274429 * t * t * t * t * t
    )
    return 1.0 - p if x >= 0 else p
