# Bankroll Architecture Decision Record

**Date:** 2026-03-28
**Author:** Bankroll Backend Lead (Senior)
**Status:** PROPOSED
**Related PRs:** #160 (MAT-272), #163

---

## Problem

PR #160 (MAT-272) introduced new bankroll files that **duplicate and conflict** with the existing codebase architecture:

| Concern | Existing (on main) | New in PR #160 |
|---------|-------------------|----------------|
| Data models | `app/models/bankroll.py` (SQLAlchemy ORM) | None (in-memory dataclasses) |
| Routes | `lp_routes.py` (pool state, deposits, withdrawals) | `bankroll_routes.py` (status, history, metrics, risk) |
| Monitoring | None (service layer missing) | `services/bankroll_monitor.py` |
| Risk model | `app/models/bankroll.py` RiskProjection (schema) | `bankroll_risk.py` (calculation engine) |
| Auto-reload | `app/models/bankroll.py` AutoReloadEvent (schema) | `services/bankroll_autoreload.py` (in-memory impl) |
| Manager facade | None | `services/bankroll_manager.py` |

## Decision

### 1. Keep BOTH route files (separate concerns)

- **`lp_routes.py`**: LP-facing operations (deposit, withdraw, share price, APY)
- **`bankroll_routes.py`**: Operator-facing monitoring (status, P&L, risk, alerts)

These serve different audiences. Register both in `api_server.py`.

### 2. Reject PR #160's in-memory implementations

PR #160's `bankroll_monitor.py` and `bankroll_autoreload.py` use in-memory lists (`deque`, `List`) instead of the existing ORM models. This is wrong for production:

- No persistence across restarts
- No audit trail
- No multi-process safety
- Duplicates existing schema design

**Instead:** Build service layers that USE the existing ORM models:

```
app/models/bankroll.py (ORM schemas)  ← KEEP AS-IS
    ↓ used by
services/bankroll_monitor.py (service) ← REWRITE to use ORM
services/bankroll_autoreload.py (service) ← REWRITE to use ORM
services/bankroll_manager.py (facade)  ← KEEP, wire to ORM-backed services
```

### 3. Keep `bankroll_risk.py` (calculation engine)

PR #160's `bankroll_risk.py` is pure math (Kelly, RoR, variance). No database dependency. This is correctly separated from the ORM layer. **Keep it**, but extend `GameParams` to support multi-game distributions:

```python
@dataclass
class GameParams:
    game_type: str = "coinflip"  # "coinflip", "dice", "plinko"
    # Coinflip-specific
    p_house: float = 0.5
    payout_multiplier: float = 1.94
    # Plinko-specific (used when game_type="plinko")
    rows: int = 12
    # Dice-specific (used when game_type="dice")
    win_probability: float = 0.5
```

### 4. Fix Plinko-specific bankroll risk

Plinko's payout distribution is fundamentally different from coinflip:
- Coinflip: Bernoulli (win 1.94x or lose 1x)
- Plinko: Multi-modal (79x, 19x, 7x, 3x, 1.8x, 1.2x, 0.88x, 0.74x, 0.70x)

The Kelly criterion for coinflip (simple two-outcome) doesn't apply to Plinko. Need a generalized Kelly that works with arbitrary payout distributions.

### 5. Add game-aware max bet validation

Current: `max_single_bet = available_capacity // 10` (10% of capacity)
Problem: Plinko 16-row edge multiplier is 79.158x. A 100 ERG bet could require 7,915 ERG payout.

Fix:
```python
def get_max_bet(game_type: str, rows: int = 0, available: int) -> int:
    if game_type == "plinko":
        max_mult = get_multiplier_table(rows)[0]  # Edge slot = highest multiplier
        return int(available / max_mult)
    else:
        return available // 10  # 10% for coinflip/dice
```

---

## Target File Structure (Post-Decision)

```
backend/
├── app/
│   ├── models/
│   │   └── bankroll.py          # ORM models (existing, no changes)
│   └── db/
│       └── ...                  # Database session management (existing)
├── services/
│   ├── bankroll_monitor.py      # Service: polls node, writes to ORM
│   ├── bankroll_autoreload.py   # Service: reads thresholds from ORM, executes reloads
│   └── bankroll_manager.py      # Facade: combines monitor + risk + autoreload
├── bankroll_risk.py             # Pure math: Kelly, RoR, variance (extend for multi-game)
├── bankroll_routes.py           # Operator endpoints: /bankroll/status, /metrics, /risk
├── lp_routes.py                 # LP endpoints: /pool/state, /deposit, /withdraw (existing)
└── src/core/
    └── plinko_logic.py          # Plinko math (from PR #160, keep)
```

---

## Action Items

| # | Task | Owner | Priority |
|---|------|-------|----------|
| 1 | Split PR #160 into focused PRs | EM | P0 |
| 2 | Rewrite bankroll_monitor.py to use ORM | Senior (me) | P1 |
| 3 | Rewrite bankroll_autoreload.py to use ORM | Senior (me) | P1 |
| 4 | Extend GameParams for multi-game | Risk Analyst Jr | P2 |
| 5 | Add game-aware max bet validation | Risk Analyst Jr 2 | P2 |
| 6 | Register bankroll_routes in api_server.py | Risk Analyst Jr | P1 |
| 7 | Fix test_plinko_multiplier_symmetry.py imports | Risk Analyst Jr | P2 |
| 8 | Create Plinko backend bet endpoint | Yield Engineer Jr | P1 |
| 9 | Update ARCHITECTURE.md | Documentation | P3 |
