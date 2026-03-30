# DuckPools Bankroll & Liquidity Protocol Architecture (v2.0)

**Author:** DeFi Architect Sr
**Date:** 2026-03-30
**Status:** DESIGN (pre-implementation)
**Issues:** MAT-12 (House bankroll management), MAT-15 (Tokenized bankroll + LP)
**Priority:** HIGH -- MAT-15 is critical and in_progress with no clear team ownership

---

## 1. Executive Summary

This document defines the architecture for transforming DuckPools from a simple gambling app into a DeFi protocol. The core innovation: **external ERG holders provide liquidity to the house bankroll, receive LP tokens, and earn yield from the house edge**.

This is the system that makes DuckPools economically viable at scale -- the house bankroll is no longer a single operator's capital but a community-funded, tokenized pool with transparent risk metrics.

## 2. Current State

### 2.1 What Exists
- Working coinflip game on Ergo testnet (commit-reveal, coinflip_v2.es)
- Dice and Plinko contracts (dice_v1.es, plinko_v1.es)
- FastAPI backend with game routes (game_routes.py, ws_routes.py)
- PostgreSQL async ORM (app/db/__init__.py)
- LP Pool Design doc (docs/LP_POOL_DESIGN.md) -- initial ErgoScript draft
- Bankroll ORM models (in worktree, NOT on main): BankrollState, BankrollTransaction, BankrollAlert, AutoReloadEvent, RiskProjection
- Bankroll Architecture Decision Record (docs/BANKROLL_ARCHITECTURE.md)

### 2.2 What's Missing (This Design Addresses)
- **No on-chain LP pool contract** deployed or compiled
- **No lp_routes.py** in the backend
- **No bankroll services** (monitor, autoreload, risk calculation engine)
- **No bankroll_routes.py** for operator monitoring
- **No oracle integration** for ERG/USD pricing
- **Bankroll ORM models not on main branch**
- **No APY calculation** or yield tracking
- **No game-aware max bet sizing** (MAT-194 bug: max bet exceeds pool liquidity)

---

## 3. Protocol Architecture

### 3.1 Two-Layer Design

```
+========================================================+
|                    ON-CHAIN LAYER                        |
|                    (ErgoTree contracts)                   |
|                                                           |
|  +---------------+  +-----------------+  +------------+ |
|  | BankrollPool  |  | WithdrawRequest |  | OracleBox  | |
|  | (Singleton)   |  | (per-request)   |  | (ERG/USD)  | |
|  +---------------+  +-----------------+  +------------+ |
|         ^                     |                    ^     |
+---------|---------------------|--------------------|-----+
          |                     |                    |
+=========|====================|====================|=====+
          |         OFF-CHAIN LAYER (FastAPI)        |
          |                     |                    |
+---------|---------------------|--------------------|-----+
|  +------|--------+  +--------|--------+  +--------|----+ |
|  | lp_routes.py  |  | bankroll_      |  | oracle_     | |
|  | (LP API)      |  | routes.py      |  | service.py  | |
|  +---------------+  | (Operator API) |  +-------------+ |
|                     +----------------+                    |
|  +---------------+  +----------------+  +-------------+  |
|  | bankroll_     |  | bankroll_      |  | bankroll_   |  |
|  | manager.py    |  | monitor.py     |  | risk.py     |  |
|  | (facade)      |  | (chain poller) |  | (math)      |  |
|  +---------------+  +----------------+  +-------------+  |
|                     +----------------+                    |
|  +---------------+  +----------------+  +-------------+  |
|  | bankroll.py   |  | bankroll_      |  | PostgreSQL  |  |
|  | (ORM models)  |  | autoreload.py  |  | (state)     |  |
|  +---------------+  +----------------+  +-------------+  |
+========================================================+
```

### 3.2 On-Chain: Three-Contract System

#### Contract 1: BankrollPool (Singleton)

The central contract. Identified by a unique Pool NFT. Holds the house bankroll.

**Tokens:**
| Index | Token | Description |
|-------|-------|-------------|
| 0 | Pool NFT | Singleton identifier (exactly 1 unit) |
| 1 | LP Token | EIP-4 token, total supply = outstanding shares |

**Registers:**
| Register | Type | Content |
|----------|------|---------|
| R4 | Coll[Byte] | House operator compressed PK (33 bytes) |
| R5 | Long | Minimum deposit (nanoERG) |
| R6 | Int | Withdrawal cooldown (blocks, e.g. 720 = ~12h) |
| R7 | Int | House edge basis points (300 = 3%) |

**Spend Paths:**

1. **Deposit** (anyone): LP tokens minted, ERG added to pool
   - NFT preserved in output
   - LP supply increases (minted)
   - Output ERG > SELF.value
   - All registers preserved
   - Minted shares = floor(depositERG * currentSupply / currentERG)

2. **Withdraw** (LP holder): LP tokens burned, ERG removed from pool
   - NFT preserved in output
   - LP supply decreases (burned)
   - Output ERG < SELF.value
   - Output ERG >= minDeposit (can't drain below min)
   - MUST spend a valid WithdrawRequest box (BP-01 security fix)
   - Withdrawn ERG = floor(burnShares * currentERG / currentSupply)

3. **Profit Collection** (house only): No token change, ERG increases
   - NFT preserved
   - LP supply unchanged
   - ERG increases (house edge profits deposited)
   - Requires proveDlog(housePk)

4. **Parameter Update** (house only): No value change, registers updated
   - ERG unchanged
   - LP supply unchanged
   - Requires proveDlog(housePk)

#### Contract 2: WithdrawRequest (Per-Request)

Created when an LP holder wants to withdraw. Enforces the cooldown period.

**Tokens:**
| Index | Token | Description |
|-------|-------|-------------|
| 0 | LP Token | LP tokens to be burned on execution |

**Registers:**
| Register | Type | Content |
|----------|------|---------|
| R4 | Coll[Byte] | LP holder's compressed PK (33 bytes) |
| R5 | Long | Requested ERG withdrawal amount (nanoERG) |
| R6 | Int | Request creation height |
| R7 | Int | Cooldown delta (copied from pool at request time) |

**Spend Paths:**

1. **Execute** (after cooldown): HEIGHT >= R6 + R7
   - BankrollPool box spent in same transaction
   - LP tokens burned, ERG sent to holder

2. **Cancel** (any time, holder only):
   - LP tokens returned to holder (no ERG from pool)
   - Requires proveDlog(holderPk)

#### Contract 3: OracleBox (Price Feed)

Stores the ERG/USD price for APY display and risk calculations.

**Registers:**
| Register | Type | Content |
|----------|------|---------|
| R4 | Long | ERG price in USD (scaled by 1e6) |
| R5 | Int | Last update timestamp |

Updated periodically by the oracle bot. The backend reads this box for price data.
NOTE: Since we're a single-asset ERG pool, the oracle is NOT enforced on-chain for deposit/withdraw amounts. It's for off-chain display only.

### 3.3 Security Properties

1. **No flash-loan risk**: Single-asset pool + withdrawal cooldown prevents manipulation
2. **Singleton guarantee**: Pool NFT ensures exactly one pool exists. NFT burn = pool dissolution
3. **Withdrawal safety**: Bankroll cannot drop below minDeposit after any withdrawal
4. **Cooldown prevents griefing**: Mass withdrawal during high-variance events requires waiting
5. **No reentrancy**: Ergo's eUTXO model prevents reentrancy by design
6. **No oracle dependency for core operations**: Pool math is purely on-chain (ERG ratios)
7. **House-only admin**: Parameter updates and profit collection require house signature

### 3.4 Identified Security Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Bankroll variance (LPs lose money if players win streaks) | MEDIUM | Transparent RoR display, cooldown prevents panic exits |
| Rounding errors in share calculation | LOW | Always round down (floor), favor existing LPs |
| Dust deposits | LOW | Minimum deposit threshold |
| House operator misbehavior | HIGH (trusted) | Production: multi-sig house key, governance |
| Oracle manipulation | LOW | Off-chain only, doesn't affect pool operations |

---

## 4. Off-Chain Architecture

### 4.1 File Structure (Target)

```
backend/
  lp_routes.py                 -- LP-facing API endpoints
  bankroll_routes.py           -- Operator monitoring API endpoints
  services/
    bankroll_manager.py        -- Facade: orchestrates deposit/withdraw/monitoring
    bankroll_monitor.py        -- Polls chain state, updates ORM, triggers alerts
    bankroll_autoreload.py     -- Auto-reload when balance drops below threshold
    oracle_service.py          -- ERG/USD price fetching, caching, history
  bankroll_risk.py             -- Pure math: Kelly, RoR, variance (no DB deps)
  app/models/bankroll.py       -- ORM models (BankrollState, Transactions, Alerts, RiskProjection)
  app/db/__init__.py           -- Async DB session management (existing)
```

### 4.2 API Design

#### LP-Facing Endpoints (lp_routes.py)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /lp/pool | Pool state: TVL, APY, ERG/share, LP supply | None |
| GET | /lp/price | Current LP token price (ERG per share) | None |
| GET | /lp/balance/{addr} | LP token balance + ERG value | None |
| POST | /lp/deposit | Build unsigned deposit tx for user signing | None |
| POST | /lp/request-withdraw | Create on-chain withdrawal request | None |
| GET | /lp/withdrawals/{addr} | List pending/completed withdrawals | None |
| POST | /lp/cancel-withdraw | Cancel pending withdrawal request | None |

#### Operator-Facing Endpoints (bankroll_routes.py)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /bankroll/status | Balance, TVL, LP pool size, utilization | API Key |
| GET | /bankroll/metrics | P&L, win/loss ratio, volume, active bets | API Key |
| GET | /bankroll/risk | RoR, Kelly fraction, max bet, percentiles | API Key |
| GET | /bankroll/alerts | Active alerts (low balance, unusual loss) | API Key |
| GET | /bankroll/history | Transaction history with pagination | API Key |
| POST | /bankroll/reload | Manual bankroll reload | API Key + Signature |

### 4.3 Service Layer Design

#### bankroll_manager.py (Facade)
```python
class BankrollManager:
    """Central facade for all bankroll operations."""
    
    async def get_pool_state() -> PoolState
    async def build_deposit_tx(address, amount_nanoerg) -> UnsignedTx
    async def request_withdrawal(address, lp_amount) -> TxId
    async def execute_mature_withdrawals() -> list[TxId]
    async def collect_house_profits(tx_hash, amount) -> TxId
    async def get_pool_price() -> Decimal  # ERG per LP share
    async def get_trailing_apy(days=30) -> Decimal
```

#### bankroll_monitor.py (Chain Poller)
```python
class BankrollMonitor:
    """Polls chain state and updates ORM."""
    
    async def poll_bankroll_box() -> None  # Updates BankrollState
    async def check_alerts() -> list[Alert]  # Triggers alerts
    async def track_exposure() -> None  # Sum of pending bets
```

#### bankroll_autoreload.py (Auto-Reload)
```python
class BankrollAutoReload:
    """Reloads bankroll when below threshold."""
    
    async def check_and_reload() -> bool
    async def get_reload_cooldown_remaining() -> int  # seconds
```

#### oracle_service.py (Price Feed)
```python
class OracleService:
    """ERG/USD price fetching with caching."""
    
    async def get_price() -> Decimal  # Current price
    async def get_price_history(days=30) -> list[PricePoint]
    async def health_check() -> bool
```

---

## 5. Financial Model

### 5.1 LP Share Price

```
totalValue = bankrollBox.ERG + sum(pendingBets.ERG) - sum(pendingPayouts.ERG)
totalSupply = bankrollBox.LP_tokens
pricePerShare = totalValue / totalSupply  # in nanoERG
```

For first deposit: 1 LP share = 1 nanoERG (1:1 ratio).

### 5.2 Deposit Math

```
newShares = floor(depositERG * currentSupply / currentValue)
```

Rounds down to prevent share inflation. Small rounding loss favors existing LPs.

### 5.3 Withdrawal Math

```
withdrawERG = floor(burnShares * currentValue / currentSupply)
```

Same rounding: rounds down. LP loses at most 1 nanoERG per withdrawal to rounding.

### 5.4 APY Calculation

**Theoretical APY** (steady-state):
```
expectedAPY = (house_edge * avgBetSize * betsPerDay * 365) / totalBankroll
```

**Trailing APY** (from actual data):
```
profit_30d = currentTVL - TVL_30_days_ago - net_deposits_30d
trailingAPY = (profit_30d / avgBankroll_30d) * (365 / 30)
```

**Example:**
```
house_edge = 3%
avgBetSize = 10 ERG
betsPerDay = 100
totalBankroll = 10,000 ERG

expectedAPY = (0.03 * 10 * 100 * 365) / 10000 = 109.5%

Note: This is EXPECTED. Actual APY has very high variance.
In bad weeks, APY can be deeply negative (LPs lose money).
```

### 5.5 Risk Model

#### Risk of Ruin (RoR)
Probability the bankroll hits zero from a series of player wins:

```
RoR = ((1 - edge) / (1 + edge)) ^ (bankroll / maxBet)

For coinflip (edge = 3%):
  bankroll/maxBet = 100 (1% max bet):  RoR = (0.97/1.03)^100  = 0.42%
  bankroll/maxBet = 50  (2% max bet):  RoR = (0.97/1.03)^50   = 6.5%
  bankroll/maxBet = 10  (10% max bet): RoR = (0.97/1.03)^10   = 42.1%
```

**Rule: Max bet should NEVER exceed 2% of bankroll** for acceptable RoR.

#### Kelly Criterion (Optimal Bet Sizing)
```
Kelly fraction = (edge * (1 + payoutMultiplier)) / payoutMultiplier

For coinflip (edge=3%, payout=1.94x):
  Kelly = (0.03 * 2.94) / 1.94 = 4.55%
  
  Meaning: With 1000 ERG bankroll, optimal max bet = 45.5 ERG
  We use 50% Kelly (conservative): max bet = 22.7 ERG ≈ 2.3% of bankroll
```

#### Game-Aware Max Bet Sizing

```python
def get_max_bet(game_type, bankroll_erg, params):
    if game_type == "plinko":
        # Plinko has extreme multipliers (up to 79x for 16 rows)
        max_mult = get_plinko_max_multiplier(params.rows)
        return int(bankroll_erg / max_mult)  # Survive worst case
    elif game_type == "dice":
        # Dice: win prob varies, payout = (99/winProb)%
        return int(bankroll_erg * 0.02)  # 2% of bankroll
    else:  # coinflip
        return int(bankroll_erg * 0.02)  # 2% of bankroll
```

#### Percentile Projections (Monte Carlo)
Run 10,000 simulations of N bets, track bankroll at each percentile:

| Percentile | Meaning |
|-----------|---------|
| P1 | Worst 1% outcome -- "catastrophic loss" scenario |
| P5 | Bad day |
| P25 | Below average |
| P50 | Median (most likely) |
| P75 | Above average |
| P95 | Good day |
| P99 | Best 1% -- "lucky streak" for house |

---

## 6. Transaction Flows

### 6.1 Deposit Flow

```
1. User calls POST /lp/deposit { amount: "10.0", address: "..." }
2. Backend queries BankrollPool box (ERG value, LP supply)
3. Backend calculates: newShares = floor(amount_nano * supply / erg_value)
4. Backend builds unsigned tx:
   Inputs:  [userBox(ERG), bankrollPoolBox]
   Outputs: [poolOut(ERG + deposit, LP supply + newShares, NFT preserved),
             userOut(LP tokens = newShares)]
5. Returns unsigned tx to user
6. User signs with Nautilus wallet
7. User broadcasts signed tx
8. Backend detects new pool state, updates ORM
```

### 6.2 Withdraw Flow (Two-Step)

```
Step 1 - Request:
1. User calls POST /lp/request-withdraw { lp_amount: "500", address: "..." }
2. Backend calculates: withdrawERG = floor(500 * currentValue / currentSupply)
3. Backend builds tx creating WithdrawRequest box:
   Inputs:  [userBox(LP tokens)]
   Outputs: [withdrawRequestBox(LP tokens locked, cooldown starts)]
4. User signs and broadcasts
5. Backend tracks the request in ORM

Step 2 - Execute (after cooldown):
1. Bot detects matured WithdrawRequest boxes (HEIGHT >= creationHeight + cooldown)
2. Backend builds tx:
   Inputs:  [withdrawRequestBox, bankrollPoolBox]
   Outputs: [poolOut(ERG - withdrawERG, LP supply - burned, NFT preserved),
             userOut(ERG = withdrawERG)]
3. Backend submits tx (operator action)
4. Backend updates ORM

Alternative - Cancel:
1. User calls POST /lp/cancel-withdraw { request_id: "..." }
2. Backend builds tx:
   Inputs:  [withdrawRequestBox]
   Outputs: [userBox(LP tokens returned)]
3. User signs and broadcasts
```

### 6.3 Profit Collection Flow

```
1. House wins bets → ERG accumulates in game contract boxes
2. House bot collects winnings and deposits into BankrollPool
3. Calls POST /bankroll/collect (or automated)
4. Backend builds tx:
   Inputs:  [bankrollPoolBox, houseBox(ERG profits)]
   Outputs: [poolOut(ERG + profits, LP supply unchanged, NFT preserved)]
5. Requires house signature (proveDlog)
6. LP share price naturally increases (more ERG per share)
```

---

## 7. Task Breakdown

### Phase 1: Foundation (Week 1-2)

| Task | Owner | Deliverable | Branch |
|------|-------|-------------|--------|
| LP Pool Contracts | LP Contract Developer Jr | bankroll_pool.es, withdraw_request.es | agent/LP-Contract-Developer-Jr/MAT-15-bankroll-pool-contracts |
| Yield Math Engine | Yield Engineer Jr | bankroll_risk.py (APY, share price, deposit/withdraw math) | agent/Yield-Engineer-Jr/MAT-15-yield-engine |
| Risk Engine | Risk Analyst Jr | bankroll_risk_service.py (RoR, Kelly, Monte Carlo, max bet) | agent/Risk-Analyst-Jr/MAT-15-risk-engine |
| Oracle Service | Oracle Engineer Jr | oracle_service.py (price fetch, cache, history) | agent/Oracle-Engineer-Jr/MAT-15-oracle-service |

### Phase 2: Backend Integration (Week 2-3)

| Task | Owner | Deliverable | Branch |
|------|-------|-------------|--------|
| LP Routes | DeFi Architect Sr | lp_routes.py with all 7 endpoints | agent/DeFi-Architect-Sr/MAT-15-lp-routes |
| Bankroll Monitor | Bankroll Backend Developer Sr | bankroll_monitor.py (chain poller → ORM) | agent/Bankroll-Backend-Dev-Sr/MAT-15-monitor |
| Bankroll Manager | Bankroll Backend Developer Sr | bankroll_manager.py (facade combining all services) | agent/Bankroll-Backend-Dev-Sr/MAT-15-manager |
| Bankroll Routes | Bankroll Backend Developer Sr | bankroll_routes.py (operator monitoring API) | agent/Bankroll-Backend-Dev-Sr/MAT-15-bankroll-routes |

### Phase 3: Integration & Testing (Week 3-4)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Wire routes in api_server.py | Bankroll Backend Developer Sr | Register lp_routes + bankroll_routes |
| End-to-end deposit/withdraw test | DeFi Architect Sr | Full flow test on testnet |
| ORM migration for bankroll tables | Bankroll Backend Developer Sr | Alembic migration |
| BNK-1 fix (exposure tracking) | Risk Analyst Jr | Status mismatch in exposure calculation |
| BNK-2 fix (threading.RLock) | Yield Engineer Jr | Replace with asyncio.Lock |

---

## 8. Key Design Principles

1. **Single-asset simplicity**: ERG only. No impermanent loss, no multi-token complexity. The complexity is in risk management, not token mechanics.

2. **Trust assumptions are explicit**: The house operator is trusted (single key). Production would use multi-sig or governance. Document this clearly.

3. **Off-chain computation, on-chain enforcement**: Complex math (APY, RoR, share price) computed by backend. Simple rules (cooldown, min balance, house auth) enforced on-chain.

4. **eUTXO-native**: Leverage Ergo's state model. Each box has clear ownership and spending rules. No global state mutations.

5. **LP risk transparency**: Every LP should see RoR, trailing APY, and bankroll health before depositing. This is a gambling bankroll -- variance is the product.

6. **Progressive decentralization**: Start centralized (house operator), move to multi-sig, then governance. Architecture supports this evolution.

---

## 9. Open Questions (for EM/CEO Decision)

1. **Initial bankroll seeding**: Who provides the first ERG? Recommended: House operator seeds with 1000 ERG testnet.

2. **Cooldown period**: 720 blocks (~12h) default. Too long annoys LPs. Too short risks bankroll drain during variance. Suggest starting at 720, adjustable.

3. **Minimum deposit**: 0.1 ERG (100,000,000 nanoERG) prevents dust. Good default?

4. **Auto-reload for bankroll**: Should the protocol auto-reload from a house reserve wallet? (Design supports it, needs approval.)

5. **LP token name/symbol**: "DuckPools LP" (DPLP)? Needs EIP-4 token registration.

---

## Appendix A: Numerical Examples

### A.1 Deposit Example
```
Pool state: 10,000 ERG bankroll, 10,000 LP shares (1:1 ratio)
User deposits: 1,000 ERG

newShares = floor(1,000 * 10,000 / 10,000) = 1,000 shares

New state: 11,000 ERG, 11,000 shares. Still 1:1.
User holds: 1,000/11,000 = 9.09% of pool
```

### A.2 Withdrawal Example (After Profit)
```
Pool state: 10,500 ERG bankroll, 10,000 shares (house won 500 ERG)
User withdraws: 1,000 shares

withdrawERG = floor(1,000 * 10,500 / 10,000) = 1,050 ERG

User deposited 1,000 ERG worth of shares, withdrew 1,050 ERG.
Profit: 50 ERG (from house edge earnings while they were an LP)
```

### A.3 Withdrawal Example (After Loss)
```
Pool state: 9,500 ERG bankroll, 10,000 shares (players won 500 ERG)
User withdraws: 1,000 shares

withdrawERG = floor(1,000 * 9,500 / 10,000) = 950 ERG

User deposited 1,000 ERG worth of shares, withdrew 950 ERG.
Loss: 50 ERG (from player winnings while they were an LP)
```

### A.4 Risk Example
```
Bankroll: 10,000 ERG
House edge: 3%
Max bet (2% rule): 200 ERG

A lucky player wins 10 bets in a row at max:
Loss = 10 * (200 * 1.94 - 200) = 10 * 188 = 1,880 ERG
Remaining bankroll: 8,120 ERG (-18.8%)

Risk of Ruin with 2% max bet:
RoR = (0.97/1.03)^50 = 0.065 = 6.5%

Translation: ~1 in 15 chance the bankroll eventually hits zero
(without new deposits or profit accumulation)
```
