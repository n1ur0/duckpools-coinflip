# Phase 7 — End-to-End Integration Test Plan

**Priority:** CRITICAL
**Depends on:** Phase 6 audit completion
**Owner:** Hermes (Senior)
**Date:** 2026-03-31

---

## Objective

Build comprehensive end-to-end integration tests covering the full DuckPools stack: frontend, backend API, smart contracts, and Ergo node interactions. These tests validate that all components work together correctly before production deployment.

## Test Infrastructure

### Architecture

```
tests/e2e/
├── conftest.py              # Shared fixtures, mock ergo node, helpers
├── pyproject.toml           # pytest configuration
├── test_full_stack_coinflip.py  # Scenario 1: Complete bet flow
├── test_lp_pool_flow.py     # Scenario 2: LP deposit/withdraw lifecycle
├── test_concurrent_bets.py  # Scenario 3: Stress tests
├── test_edge_cases.py       # Scenario 4: Error conditions
├── test_api_contract.py     # Scenario 5: REST API contract validation
└── TEST_PLAN.md             # This file
```

### Key Fixtures

| Fixture | Scope | Description |
|---------|-------|-------------|
| `app_client` | session | AsyncClient wired to real FastAPI app via ASGI transport |
| `mock_node` | session | In-process mock Ergo node |
| `reset_bets` | autouse | Clears `_bets` list between tests |
| `unique_bet_id` | function | Generates unique bet ID per test |
| `player_client` | function | Pre-configured player client |

### Mock Ergo Node

The `MockErgoNode` class simulates:
- Node info endpoint (`/info`)
- Wallet status and balance
- Block hash generation for RNG
- Chain height advancement
- Box registration and spending
- Transaction submission

This allows tests to run without a real Ergo node, while still testing the full backend logic.

---

## Test Scenarios

### Scenario 1: Full Coinflip Flow (Wallet → Bet → Commit → Reveal → Payout)

**File:** `test_full_stack_coinflip.py`
**Tests:** 27 test cases

| ID | Test | What It Validates |
|----|------|-------------------|
| CF-01 | Contract info returns P2S address | Wallet can get contract address for tx building |
| CF-02 | Contract info returns ErgoTree hex | Wallet can verify contract code |
| CF-03 | Contract info register layout | Frontend knows R4-R9 register mapping |
| CF-04 | Place bet heads success | Commit phase works for heads |
| CF-05 | Place bet tails success | Commit phase works for tails |
| CF-06 | Place bet below minimum rejected | Amount validation floor |
| CF-07 | Place bet above maximum rejected | Amount validation ceiling |
| CF-08 | Boundary: exactly minimum | Boundary value accepted |
| CF-09 | Boundary: exactly maximum | Boundary value accepted |
| CF-10 | Commitment hash stored correctly | Commit-reveal commitment persisted |
| CF-11 | Choice 0 → heads, 1 → tails | Side mapping correct |
| CF-12 | Empty history for unknown address | No data leakage between addresses |
| CF-13 | Bet appears in history | History endpoint tracks placed bets |
| CF-14 | History is address-scoped | Player A can't see Player B's bets |
| CF-15 | History returns list type | Correct response type |
| CF-16 | Stats empty initially | Clean slate for new players |
| CF-17 | Stats pending count after bet | Pending bets counted |
| CF-18 | Stats total wagered | Wagered amount accumulates |
| CF-19 | Payout multiplier is 0.97 | 3% house edge enforced |
| CF-20 | Payout calculation correctness | Math matches expected formula |
| CF-21 | Leaderboard valid structure | API contract for leaderboard |
| CF-22 | Leaderboard initially empty | Clean state |
| CF-23 | Comp points empty initially | No phantom points |
| CF-24 | Comp points after wagering | Points accumulate at 1 per 0.01 ERG |
| CF-25 | Comp tier Bronze threshold | Tier logic correct |
| CF-26 | Complete coinflip flow | End-to-end: place → history → stats → comp |
| CF-27 | Multiple bets sequential | 5 bets tracked correctly |

### Scenario 2: LP Pool Flow (Deposit → Token Issuance → Withdrawal)

**File:** `test_lp_pool_flow.py`
**Tests:** 12 test cases

| ID | Test | What It Validates |
|----|------|-------------------|
| LP-01 | Pool state responds | Endpoint availability |
| LP-02 | Pool state has liquidity field | Correct data shape |
| LP-03 | LP price responds | Endpoint availability |
| LP-04 | LP price is numeric | Correct data type |
| LP-05 | LP APY responds | Endpoint availability |
| LP-06 | LP APY is percentage | Reasonable range |
| LP-07 | LP balance responds | Per-address balance |
| LP-08 | LP balance invalid address | Input validation |
| LP-09 | LP deposit endpoint exists | API contract |
| LP-10 | LP withdraw endpoint exists | API contract |
| LP-11 | LP scripts valid ErgoTree | Contract hex format |
| LP-12 | Pool endpoints consistent | Cross-endpoint consistency |

**Note:** LP endpoints may return 404 if not yet implemented. Tests gracefully handle this and will be expanded once MAT-394 (bankroll backend) merges.

### Scenario 3: Concurrent Bets Stress Test

**File:** `test_concurrent_bets.py`
**Tests:** 7 test cases
**Markers:** `@pytest.mark.concurrent`

| ID | Test | What It Validates |
|----|------|-------------------|
| ST-01 | 10 concurrent bets all succeed | Basic concurrency |
| ST-02 | 50 concurrent bets | Medium load |
| ST-03 | 100 concurrent bets | High load |
| ST-04 | Reads during writes | No read-write conflicts |
| ST-05 | Stats reads consistent | Concurrent reads return same data |
| ST-06 | Duplicate betId rejected concurrently | Dedup under race conditions |
| ST-07 | Unique betIds all succeed concurrently | Correct concurrent behavior |

### Scenario 4: Edge Cases

**File:** `test_edge_cases.py`
**Tests:** 40 test cases

| Category | Tests | Coverage |
|----------|-------|----------|
| Malformed commitments | 7 | Short, long, non-hex, empty, null, all-zeros, all-FF |
| Invalid amounts | 9 | Zero, negative, float, scientific, text, overflow, nano, boundaries |
| Invalid choices | 6 | Negative, 2, large, float, string, null |
| Invalid addresses | 6 | Short, empty, Bitcoin, Ethereum, SQL injection, XSS |
| Missing/extra fields | 7 | Each required field missing + extra fields ignored |
| Bet deduplication | 2 | Same ID rejected, different IDs accepted |
| Timeout expiry | 1 | Pending status until on-chain resolution |
| Input sanitization | 4 | Special chars, long strings, whitespace, case normalization |

### Scenario 5: REST API Endpoint Contract

**File:** `test_api_contract.py`
**Tests:** 42 test cases

| Category | Tests | Coverage |
|----------|-------|----------|
| Root endpoint | 5 | Status, JSON, name, version, endpoint list |
| Health endpoint | 5 | Status, JSON, status field, node field, URL format |
| Contract info | 3 | Status, JSON, required fields |
| Place bet | 3 | JSON, required fields, success structure |
| History | 5 | JSON, list type, record structure, field types |
| Player stats | 4 | JSON, structure, field types |
| Player comp | 5 | JSON, structure, field types, benefits |
| Leaderboard | 3 | JSON, structure, field types |
| Security headers | 6 | All endpoints have security headers |
| Error format | 3 | 404, 422, 405 consistent format |
| HTTP methods | 5 | Only allowed methods work |
| Response time | 3 | Health < 100ms, root < 50ms, bet < 100ms |

---

## Test Counts Summary

| Scenario | File | Tests |
|----------|------|-------|
| 1. Full Coinflip Flow | test_full_stack_coinflip.py | 27 |
| 2. LP Pool Flow | test_lp_pool_flow.py | 12 |
| 3. Concurrent Stress | test_concurrent_bets.py | 7 |
| 4. Edge Cases | test_edge_cases.py | 40 |
| 5. API Contract | test_api_contract.py | 42 |
| **Total** | | **128** |

---

## Running Tests

### Prerequisites
```bash
cd /Users/n1ur0/worktrees/agent/Hermes/phase7-e2e-integration-tests
pip install -r backend/requirements.txt
pip install pytest-asyncio httpx
```

### Run All E2E Tests
```bash
cd tests/e2e
python -m pytest -v
```

### Run by Scenario
```bash
python -m pytest test_full_stack_coinflip.py -v    # Scenario 1
python -m pytest test_lp_pool_flow.py -v           # Scenario 2
python -m pytest test_concurrent_bets.py -v        # Scenario 3
python -m pytest test_edge_cases.py -v             # Scenario 4
python -m pytest test_api_contract.py -v           # Scenario 5
```

### Run with Coverage
```bash
python -m pytest --cov=../../backend --cov-report=html -v
```

### Run Specific Test
```bash
python -m pytest test_full_stack_coinflip.py::TestFullBetFlow::test_complete_coinflip_flow -v
```

---

## Post-Phase 6 Expansion

After the Phase 6 security audit completes, these additional tests should be added:

1. **On-chain verification tests** — Use real Ergo node (Lithos testnet) to verify:
   - Commit box appears on-chain after bet placement
   - Reveal transaction spends commit box correctly
   - Refund works after timeout height
   - Payout amounts match contract constraints

2. **WebSocket tests** — Real-time bet updates via `/ws`:
   - Connection establishment
   - Bet event broadcasting
   - Reveal event broadcasting
   - Disconnection handling

3. **Frontend E2E with Playwright** — Full browser tests:
   - Wallet connection flow (with Nautilus mock)
   - Bet form submission → confirmation → result display
   - History page rendering
   - Stats dashboard accuracy

4. **Security regression tests** — From Phase 6 audit findings:
   - One test per audit finding
   - Must pass before any release

---

## Exit Criteria

- [x] Test infrastructure created (conftest.py, fixtures, mock node)
- [x] Scenario 1: 27 tests written
- [x] Scenario 2: 12 tests written
- [x] Scenario 3: 7 stress tests written
- [x] Scenario 4: 40 edge case tests written
- [x] Scenario 5: 42 API contract tests written
- [ ] All 128 tests pass against current main branch
- [ ] Tests integrated into CI pipeline
- [ ] Post-Phase 6 expansion tests added
