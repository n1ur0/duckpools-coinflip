# DuckPools Bankroll Risk Model

**Document version:** 1.0
**Author:** DeFi Architect Sr
**Issue:** MAT-184
**Last updated:** 2026-03-27

---

## 1. Overview

This document specifies the mathematical model used by DuckPools to assess bankroll risk, determine optimal bet sizing, and ensure protocol solvency. The model is implemented in `backend/services/bankroll_risk.py` and exposed via the `/api/bankroll/risk` and `/api/bankroll/projection` endpoints.

All calculations are from the **house perspective** (i.e., the protocol's bankroll).

---

## 2. Game Parameters

| Parameter              | Value  | Notes                                     |
|------------------------|--------|-------------------------------------------|
| P(house wins)          | 0.50   | Fair coin flip (first_byte % 2)           |
| P(player wins)         | 0.50   |                                           |
| Payout multiplier      | 1.94x  | Player receives 1.94x their bet on win    |
| House edge             | 3%     | 1 - 0.5 * 1.94 = 0.03                     |

The house edge is embedded entirely in the payout multiplier. On-chain, when the player wins, the contract sends 0.97 * (bet_amount) as profit (total returned = bet + 0.97 * bet = 1.97x... no, let me recalculate).

**Correction:** The payout multiplier is 1.94x total return. If a player bets `B` ERG:
- **Player wins:** receives `1.94 * B` ERG (net profit: `0.94 * B` ERG)
- **Player loses:** receives 0 ERG (net loss: `B` ERG)
- **House perspective:** Win = keep `B` ERG (+1.0). Loss = pay out `0.94 * B` net (-0.94).
- **House edge:** E[profit] = 0.5 * 1.0 - 0.5 * 0.94 = 0.03 (3%)

---

## 3. Kelly Criterion

### 3.1 Formula

For a bet with two outcomes, the generalized Kelly Criterion is:

```
f* = (p * W - q * L) / (W * L)
```

Where:
- `p` = probability of winning (house perspective)
- `q` = probability of losing = 1 - p
- `W` = profit per unit wagered on win
- `L` = loss per unit wagered on loss

### 3.2 Calculation for DuckPools Coinflip

```
p = 0.50, q = 0.50, W = 1.0, L = 0.94

f* = (0.50 * 1.0 - 0.50 * 0.94) / (1.0 * 0.94)
   = (0.50 - 0.47) / 0.94
   = 0.03 / 0.94
   ≈ 0.03191 (3.191%)
```

### 3.3 Interpretation

The Kelly Criterion says the house should wager approximately **3.19%** of its bankroll per bet to maximize long-term growth rate. This is very close to the 3% house edge, which is expected for a near-even game with a small edge.

### 3.4 Practical Usage

Full Kelly is aggressive for a gambling protocol. We use **quarter-Kelly** (f*/4 ≈ 0.80%) as the practical recommendation:
- Reduces variance significantly while retaining 75% of Kelly's geometric growth rate
- Provides a buffer against model uncertainty (e.g., correlated bets, adversarial play)
- Standard practice in quantitative finance and professional bankroll management

---

## 4. Risk of Ruin

### 4.1 Continuous Approximation (Brownian Motion)

We use the standard continuous approximation from quantitative finance. For a biased random walk with drift `mu` and variance `sigma^2`, starting at position `B` (bankroll in units of max bet), the probability of hitting zero before infinity:

```
RoR ≈ exp(-2 * mu * B / sigma^2)
```

### 4.2 Parameter Calculation

**Expected value per unit bet (house):**
```
mu = p * W - q * L
   = 0.50 * 1.0 - 0.50 * 0.94
   = 0.03
```

**Variance per unit bet (house):**
```
sigma^2 = E[X^2] - mu^2
        = p * W^2 + q * L^2 - mu^2
        = 0.50 * 1.00 + 0.50 * 0.8836 - 0.0009
        = 0.5000 + 0.4418 - 0.0009
        = 0.9409
```

**Standard deviation per unit bet:**
```
sigma = sqrt(0.9409) ≈ 0.9700
```

### 4.3 Risk-of-Ruin Formula

```
RoR = exp(-2 * 0.03 * B / 0.9409)
   = exp(-0.06378 * B)
```

Where `B` = bankroll / max_single_bet.

### 4.4 Tabulated Values

| Bankroll Units (B) | Risk of Ruin        | Assessment      |
|---------------------|---------------------|-----------------|
| 50                  | 4.04%               | Dangerous       |
| 72                  | 1.00%               | Minimum viable  |
| 100                 | 0.14%               | Safe            |
| 144                 | 0.01%               | Very safe       |
| 200                 | 0.0004%             | Extremely safe  |

### 4.5 Minimum Bankroll Recommendation

Solving for B given target RoR:

```
B = -sigma^2 * ln(RoR_target) / (2 * mu)
```

For **<1% RoR:**
```
B = -0.9409 * ln(0.01) / (2 * 0.03)
  = -0.9409 * (-4.605) / 0.06
  = 4.332 / 0.06
  ≈ 72.2 bankroll units
```

For **<0.1% RoR:**
```
B = -0.9409 * ln(0.001) / (2 * 0.03)
  = -0.9409 * (-6.908) / 0.06
  = 6.499 / 0.06
  ≈ 108.3 bankroll units
```

**Recommendation:** The protocol should maintain a bankroll of at least **72x the maximum single bet** to keep risk of ruin below 1%. For production, we recommend **144x** (0.1% RoR) as the target.

---

## 5. Variance Analysis

### 5.1 Central Limit Theorem Projection

After `N` independent bets of average size `avg_bet`:

```
E[cumulative P&L] = N * mu * avg_bet
Std[cumulative P&L] = sqrt(N) * sigma * avg_bet
```

### 5.2 Break-Even Analysis

The "break-even point" is when expected cumulative profit exceeds one standard deviation of cumulative P&L:

```
N * mu > sqrt(N) * sigma
sqrt(N) > sigma / mu
N > (sigma / mu)^2
```

For DuckPools:
```
N > (0.970 / 0.03)^2 = (32.33)^2 ≈ 1,045 bets
```

After approximately **1,045 bets**, the protocol's cumulative profit will exceed one standard deviation, meaning the house edge becomes statistically reliable.

### 5.3 Example Projections (1 ERG average bet)

| Rounds | Expected Profit | Std Dev | 3-sigma Worst Case | P(profitable) |
|--------|-----------------|---------|-------------------|---------------|
| 100    | 3.00 ERG        | 9.70 ERG| -26.1 ERG         | 62.2%         |
| 500    | 15.0 ERG        | 21.7 ERG| -50.1 ERG         | 75.6%         |
| 1,000  | 30.0 ERG        | 30.7 ERG| -62.0 ERG         | 83.7%         |
| 5,000  | 150 ERG         | 68.6 ERG| -55.7 ERG         | 98.6%         |
| 10,000 | 300 ERG         | 97.0 ERG| +9.0 ERG          | 99.9%         |

Note: After ~10,000 bets, even the 3-sigma worst case is positive.

---

## 6. API Endpoints

### 6.1 GET `/api/bankroll/risk`

Returns comprehensive risk metrics for the current bankroll state.

**Query parameters:**
| Parameter          | Type   | Default | Description                           |
|--------------------|--------|---------|---------------------------------------|
| `bankroll_nanoerg` | int    | (pool)  | Override bankroll (nanoERG)           |
| `max_bet_nanoerg`  | int    | 1e9     | Max single bet size (nanoERG)         |

**Response fields:**
| Field                         | Type  | Description                              |
|-------------------------------|-------|------------------------------------------|
| `kelly_fraction`              | float | Optimal Kelly fraction (3.19%)           |
| `kelly_fraction_quarter`      | float | 1/4 Kelly (0.80%)                        |
| `risk_of_ruin`                | float | Current RoR probability                  |
| `safety_ratio`                | float | bankroll / min_recommended (1% RoR)      |
| `bankroll_units`              | float | bankroll / max_bet                       |
| `min_bankroll_1pct_erg`       | str   | Min bankroll for <1% RoR                 |
| `min_bankroll_0_1pct_erg`     | str   | Min bankroll for <0.1% RoR               |
| `max_bet_kelly_erg`           | str   | Max single bet at full Kelly             |
| `max_bet_quarter_kelly_erg`   | str   | Max single bet at 1/4 Kelly             |
| `expected_value_per_bet`      | float | House EV per unit bet (0.03)             |
| `variance_per_bet`            | float | Variance per unit bet (0.9409)           |
| `stddev_per_bet`              | float | Std dev per unit bet (0.970)             |
| `n_bets_for_reliability`      | float | Bets until EV > 1 stddev (~1045)         |

### 6.2 GET `/api/bankroll/projection`

Returns variance projection over N bet rounds.

**Query parameters:**
| Parameter          | Type   | Default | Description                      |
|--------------------|--------|---------|----------------------------------|
| `n_rounds`         | int    | 1000    | Number of bet rounds (1 to 10M)  |
| `avg_bet_nanoerg`  | int    | 1e9     | Average bet size (nanoERG)       |

**Response fields:**
| Field                      | Type  | Description                        |
|----------------------------|-------|------------------------------------|
| `n_rounds`                 | int   | Rounds projected                   |
| `expected_profit_erg`      | str   | Expected cumulative profit         |
| `stddev_erg`               | str   | Standard deviation of P&L          |
| `profit_1sigma_low_nanoerg`| float | Lower bound (68% confidence)       |
| `profit_1sigma_high_nanoerg`|float | Upper bound (68% confidence)       |
| `profit_2sigma_low_nanoerg`| float | Lower bound (95% confidence)       |
| `profit_2sigma_high_nanoerg`|float | Upper bound (95% confidence)       |
| `worst_case_3sigma_erg`    | str   | Worst case (99.7% confidence)      |
| `prob_profitable`          | float | Probability of being profitable    |

---

## 7. Implementation Notes

### 7.1 Normal CDF

The probability-of-profitability calculation uses the Abramowitz & Stegun 26.2.17 rational approximation for the standard normal CDF, with maximum error of 7.5e-8. This is sufficient for risk management purposes and avoids importing scipy as a dependency.

### 7.2 Edge Cases

- **Zero bankroll:** Returns RoR = 1.0 (certain ruin), all minimum bankroll values = infinity
- **Zero max bet:** Returns bankroll_units = infinity, RoR = 0.0
- **Negative Kelly:** Returns 0.0 (house has no edge, should not bet)
- **Underflow protection:** RoR exponent clamped to -100 to prevent floating-point underflow

### 7.3 Pool Integration

The `/api/bankroll/risk` endpoint can read bankroll directly from the pool manager (`app.state.pool_manager`) when available, or accept a manual override via query parameter. This allows:
- Real-time risk monitoring during production
- What-if analysis with hypothetical bankroll values
- Integration with LP deposit/withdraw flows

---

## 8. References

- Kelly, J. L. (1956). "A New Interpretation of Information Rate." *Bell System Technical Journal*, 35(4), 917-926.
- Thorp, E. O. (2006). "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market." *Handbook of Asset and Liability Management*, Vol. 1.
- Feller, W. (1968). *An Introduction to Probability Theory and Its Applications*, Vol. I, 3rd ed. Wiley.
- Abramowitz, M. & Stegun, I. (1964). *Handbook of Mathematical Functions*. Dover.
