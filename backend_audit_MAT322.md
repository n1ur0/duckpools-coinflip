# [MAT-322] Backend API PoC Scope Violations Audit Report

## Executive Summary

This audit identifies multiple violations of the DuckPools CoinFlip Proof of Concept (PoC) scope in the backend API. The PoC is supposed to implement ONLY a coinflip game, but the current backend includes extensive non-coinflip functionality including LP/bankroll management, oracle services, and other game types.

## PoC Scope Rules (Reference)

1. **ONE game**: coinflip. No dice, plinko, crash, slots, roulette, or any other game.
2. **No bankroll management**, LP tokens, staking, or DeFi features.
3. **No SDK, public API, ecosystem, community, or marketing work.**
4. **No rate limiting, load testing, or enterprise security** — this is a PoC.

## Critical Violations Found

### 1. Dice Game Implementation (CRITICAL)

**File**: `backend/dice_routes.py`  
**Lines**: 1-43  
**Violation**: Explicit implementation of dice game functionality

**Details**:
- `/api/dice/health` endpoint
- `/api/dice/bet` endpoint for placing dice bets
- `/api/dice/state` endpoint with dice game state
- Dice-specific bet parameters (outcome, dice logic)

**Impact**: Direct violation of "ONE game: coinflip" rule
**Recommendation**: **REMOVE** - This entire file violates the PoC scope

---

### 2. Liquidity Pool (LP) Management System (CRITICAL)

**File**: `backend/lp_routes.py`  
**Lines**: 1-555  
**Violation**: Complete LP/bankroll management system

**Details**:
- Pool state queries (TVL, APY, price)
- Deposit/withdraw transaction building
- Withdrawal request management
- LP token balance checking
- APY calculations
- Transaction building for deposits and withdrawals
- LP token operations

**Endpoints**:
- `/api/lp/pool` - Pool state
- `/api/lp/price` - LP token price
- `/api/lp/apy` - APY calculations
- `/api/lp/balance/{address}` - LP balance check
- `/api/lp/estimate/deposit` - Deposit estimates
- `/api/lp/estimate/withdraw` - Withdrawal estimates
- `/api/lp/deposit` - Build deposit transactions
- `/api/lp/request-withdraw` - Withdrawal requests
- `/api/lp/execute-withdraw` - Execute withdrawals
- `/api/lp/cancel-withdraw` - Cancel withdrawals

**Impact**: Direct violation of "No bankroll management, LP tokens, staking, or DeFi features"
**Recommendation**: **REMOVE** - This entire file violates the PoC scope

---

### 3. Bankroll Management System (CRITICAL)

**File**: `backend/bankroll_routes.py`  
**Lines**: 1-381  
**Violation**: Complete bankroll risk management system

**Details**:
- Bankroll state monitoring
- Transaction history
- Risk alerts and metrics
- Auto-reload functionality
- Kelly criterion calculations
- Risk projections

**Endpoints**:
- `/bankroll/state` - Bankroll state
- `/bankroll/transactions` - Transaction history
- `/bankroll/alerts` - Risk alerts
- `/bankroll/risk` - Risk metrics
- `/bankroll/projection` - Risk projections
- `/bankroll/autoreload` - Auto-reload status

**Impact**: Direct violation of "No bankroll management, LP tokens, staking, or DeFi features"
**Recommendation**: **REMOVE** - This entire file violates the PoC scope

---

### 4. Oracle Price Feed System (CRITICAL)

**File**: `backend/oracle_routes.py`  
**Lines**: 1-360  
**Violation**: Complete oracle price feed management system

**Details**:
- Oracle health monitoring
- Oracle endpoint management
- Oracle feed configuration
- Price feed functionality
- On-chain oracle data retrieval

**Endpoints**:
- `/api/oracle/health` - Oracle health
- `/api/oracle/status` - Oracle status
- `/api/oracle/endpoints` - Oracle endpoints
- `/api/oracle/data/{oracle_box_id}` - Oracle data
- `/api/oracle/switch` - Switch oracle endpoints
- `/api/oracle/feeds` - Oracle feeds
- `/api/oracle/price/{base_asset}/{quote_asset}` - Price feeds

**Impact**: Violation of PoC scope - oracle features are not needed for a simple coinflip game
**Recommendation**: **REMOVE** - This entire file violates the PoC scope

---

### 5. Root Endpoint Advertising Non-Existent Features (HIGH)

**File**: `backend/api_server.py`  
**Lines**: 220-246  
**Violation**: Root "/" endpoint advertises LP and oracle features

**Details**:
The root endpoint returns a list of all available endpoints, including:
- All LP endpoints (pool, price, apy, balance, etc.)
- All oracle endpoints (health, status, etc.)
- This creates false expectations about the PoC scope

**Impact**: Misleading documentation and potential confusion about PoC capabilities
**Recommendation**: **MODIFY** - Update root endpoint to only show coinflip-related endpoints

---

### 6. Application Description Violation (MEDIUM)

**File**: `backend/api_server.py`  
**Lines**: 178-179  
**Violation**: App description mentions "LP Liquidity Pool API"

**Current**: `"DuckPools Coinflip + LP Liquidity Pool API"`  
**Issue**: Explicitly includes LP features in the API description

**Recommendation**: **MODIFY** - Change to `"DuckPools Coinflip API"` (remove LP reference)

---

### 7. Optional Router Registration (MEDIUM)

**File**: `backend/api_server.py`  
**Lines**: 34-48, 212-215  
**Violation**: Registers LP, oracle, and bankroll routers

**Details**:
The API server conditionally registers routers for LP, oracle, and bankroll functionality:
```python
from lp_routes import router as lp_router
from oracle_routes import router as _oracle_router
from bankroll_routes import router as _bankroll_router

# Register routers
app.include_router(lp_router, prefix="/api")
if _oracle_router:
    app.include_router(_oracle_router)
if _bankroll_router:
    app.include_router(_bankroll_router)
```

**Recommendation**: **REMOVE** - Remove all router imports and registrations for non-coinflip features

---

### 8. Game Routes - Minor Issues (LOW)

**File**: `backend/game_routes.py`  
**Lines**: 30-44, 290-295  
**Violation**: References to non-coinflip features in models

**Details**:
1. GameChoice and GameOutcome models have fields for other games:
   - `rollTarget` (for dice)
   - `rows` (for plinko/slots)
   - `slot` (for slots)
   - `multiplier` (for multiple games)

2. Comp points benefits include marketing/community features:
   - "Tournaments"
   - "VIP tournaments"
   - "Early access"
   - "Dedicated support"

**Recommendation**: **MODIFY** - Remove non-coinflip fields from models and simplify comp points

---

### 9. Root Middleware Configuration (LOW)

**File**: `backend/api_server.py`  
**Lines**: 137-150  
**Violation**: Pool manager initialization

**Details**:
The lifespan function initializes a PoolStateManager, which is used for LP functionality. This creates unnecessary dependencies for a coinflip-only PoC.

**Recommendation**: **SIMPLIFY** - Remove PoolStateManager initialization if not needed for coinflip

---

## Summary of Required Actions

### Files to COMPLETELY REMOVE:
- `backend/dice_routes.py`
- `backend/lp_routes.py`
- `backend/bankroll_routes.py`
- `backend/oracle_routes.py`

### Files to MODIFY:
1. `backend/api_server.py`:
   - Update app description to remove LP reference
   - Remove non-coinflip router imports and registrations
   - Update root endpoint to only show coinflip features
   - Remove PoolStateManager if not needed for coinflip

2. `backend/game_routes.py`:
   - Remove non-coinflip fields from GameChoice and GameOutcome models
   - Simplify comp points benefits to remove marketing/community features

### Database Models to Consider:
The audit found database models for bankroll and LP functionality in `backend/app/models/`. These should also be removed if they exist:
- BankrollState
- BankrollTransaction
- BankrollAlert
- AutoReloadEvent
- RiskProjection

## Priority Ranking

1. **CRITICAL** (Immediate removal required):
   - Remove all non-coinflip route files
   - Remove router registrations
   - Update app description

2. **HIGH** (Fix in next commit):
   - Update root endpoint
   - Remove PoolStateManager if unused

3. **MEDIUM** (Fix in follow-up):
   - Clean up game route models
   - Remove unused database models

## Impact of Removal

Removing these features will:
- Simplify the codebase significantly
- Reduce attack surface
- Eliminate confusion about PoC scope
- Focus development on the core coinflip functionality
- Make the codebase easier to maintain and audit

## Verification

After implementing these changes:
1. The only active endpoints should be:
   - `/health` - System health check
   - `/game/` endpoints - Coinflip game functionality
   - `/ws/` endpoints - WebSocket for game updates

2. The root endpoint should only list coinflip-related features
3. No references to LP, oracle, bankroll, or other games should remain

---
**Audit Date**: 2026-03-28  
**Auditor**: Security Engineer Jr.  
**Issue**: MAT-322