# DuckPools Test Suite

Quick reference for running tests.

## Test Files

| Test File | Purpose | Status |
|-----------|---------|--------|
| `test_smart_contract.py` | Core contract validation | ✅ PASSING |
| `test_bot_logic.py` | Off-chain bot logic | ✅ PASSING |
| `test_rng_security.py` | RNG security properties | ✅ PASSING |
| `test_timeout_refund.py` | Timeout/refund mechanism | ⏸️ BLOCKED (MAT-28) |

## Quick Start

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_smart_contract.py -v

# Run with detailed output
pytest tests/ -v -s

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## Test Status Dashboard

### Core Tests (Unblocked)
- [x] Smart Contract Tests - All passing
- [x] Bot Logic Tests - All passing
- [x] RNG Security Tests - All passing

### Blocked Tests (Critical Issue Found)
- [ ] Timeout/Refund Tests (MAT-53) - **BLOCKED: MAT-28 implementation missing**

**CRITICAL FINDING (2026-03-27)**:
- MAT-28 marked "done" but no code found in repository
- Missing: PendingBet contract with R9 timeout register
- Missing: Backend endpoints for placing/refunding bets with timeout
- See: `tests/MAT-53_EXECUTION_REPORT.md` for full details

## Environment Variables

```bash
# From root .env
NODE_URL=http://localhost:9052
EXPLORER_URL=http://localhost:9052
HOUSE_ADDRESS=3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26
WALLET_PASS=1231231230
COINFLIP_NFT_ID=b0a111d06ccf32fa10c6b36f615233212bc725d8707575ccacc0c02267b27332
API_KEY=hello
```

## Utilities

| Utility | Purpose |
|---------|---------|
| `tests/utils/timeout_helpers.py` | Timeout/refund test helpers |
| `tests/utils/crypto.py` | Hash and RNG utilities |
| `tests/conftest.py` | Pytest fixtures and config |

## For MAT-53 (Timeout Tests)

See `tests/MAT-53_TIMEOUT_TEST_PLAN.md` for detailed test plan.

**Prerequisites:**
- MAT-28 must be complete
- Timeout mechanism implemented in PendingBet contract
- Refund transaction builder implemented

**Run timeout tests:**
```bash
pytest tests/test_timeout_refund.py -v
```
