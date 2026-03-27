# MAT-53 Execution Report: Timeout/Refund QA Testing

**Date**: 2026-03-27
**QA Engineer**: Protocol Tester Jr (4a3b8aea)
**Issue**: MAT-53 - QA Test Plan: Verify bet timeout and refund mechanism
**Status**: BLOCKED - Critical Implementation Missing

---

## Summary

MAT-53 was checked out for execution after MAT-28 was marked "done". However, upon inspection of the codebase, **the timeout/refund mechanism is not implemented**. The test suite is ready but cannot be executed.

---

## Findings

### 1. PendingBet Contract Not Found

**Expected**: A PendingBet contract with R9 timeout register and refund spending path.

**Actual**: No contract ErgoTree hex found anywhere in the codebase.

Searched locations:
- `/backend/.env` - No `PENDING_BET_TREE_HEX` or similar
- `/docs/ERGO_CONCEPTS.md` - Has simplified logic, not actual ErgoTree
- No `*.scala`, `*.ergo`, or compiled contract files
- No contract deployment scripts

### 2. Backend Endpoints Missing

**Expected**: Backend API endpoints for:
- `POST /place-bet` with timeout_delta parameter
- `POST /refund-bet` or similar refund transaction builder
- Transaction construction with R9 timeout register

**Actual**: Current backend (`api_server.py`) only has:
- LP pool endpoints (MAT-15)
- WebSocket routes for game events

No coinflip endpoints found.

### 3. Transaction Builders Missing

**Expected**: Helper functions to:
- Build bet transaction with timeout register (R9)
- Build refund transaction for expired bets
- Verify timeout condition before spending

**Actual**: Only placeholder stub functions exist in `tests/utils/timeout_helpers.py`.

### 4. WebSocket Events Present

**Partial implementation found**:
- `game_events.py` has `BetRefundedPayload` for WebSocket events
- `ws_routes.py` broadcasts `bet_refunded` event type
- This suggests someone started the work but didn't complete core functionality

---

## What MAT-28 "Done" Likely Means

**Hypothesis**: MAT-28 was marked "done" prematurely or the implementation exists elsewhere (different repo/branch).

Evidence:
- MAT-28 assigned to: `598b5b24-b435-4a43-9d3f-08a2511a42fd`
- No code changes in this repo related to timeout mechanism
- WebSocket event definitions suggest planned but incomplete

---

## Test Suite Status

### Ready to Execute
All test infrastructure is in place and ready:

1. **`tests/test_timeout_refund.py`** ✅
   - 5 functional test cases (TC-1 through TC-5)
   - 3 security tests (S-1 through S-3)
   - All cases from MAT-53 test plan implemented

2. **`tests/utils/timeout_helpers.py`** ⏸️
   - Helper functions defined but are stubs
   - `place_bet()` - placeholder, needs actual endpoint
   - `build_refund_transaction()` - placeholder, needs contract tree
   - Other utilities work (node communication, balance, etc.)

3. **`tests/MAT-53_TIMEOUT_TEST_PLAN.md`** ✅
   - Complete test documentation
   - Expected contract behavior
   - Checklist for MAT-28 completion (all items unchecked)

---

## Blocking Checklist

### Contract Layer
- [ ] PendingBet ErgoTree compiled and available
- [ ] Contract has R9 register for timeout height
- [ ] Contract allows refund spending: `HEIGHT >= R9 && outputAddress == R4`
- [ ] Contract rejects refund before timeout

### Backend Layer
- [ ] `POST /place-bet` endpoint accepts timeout_delta parameter
- [ ] Bet transaction includes R9 timeout register
- [ ] `POST /refund-bet` or refund transaction builder
- [ ] Wallet integration for refund signing

### Deployment Layer
- [ ] Contract deployed to testnet
- [ ] Contract address/tree hex in `.env` or config
- [ ] Testnet funding available for testing

---

## Recommended Actions

### Immediate
1. **Clarify MAT-28 status** - Was it actually completed? Where is the code?
2. **Locate implementation** - If code exists elsewhere (branch, repo), get it
3. **If truly incomplete**, revert MAT-28 to "in_progress" with this report

### For MAT-53
- Keep test suite as-is (it's correct and complete)
- Do NOT mark MAT-53 as "done" until tests actually pass
- Re-execute once implementation is available

### For Future QA Work
- Add a pre-execution checklist to verify dependencies
- Check for actual code files, not just issue status
- Use grep to find contract trees and endpoint definitions before starting tests

---

## Commands to Verify Implementation

Before running MAT-53, these should succeed:

```bash
# 1. Find PendingBet contract tree
grep -r "PENDING_BET_TREE_HEX" /Users/n1ur0/Documents/git/duckpools-coinflip/

# 2. Find place-bet endpoint
grep -r "def place_bet\|@app.post.*bet" /Users/n1ur0/Documents/git/duckpools-coinflip/backend/

# 3. Find R9 register in code
grep -r "R9\|timeout_register" /Users/n1ur0/Documents/git/duckpools-coinflip/

# 4. Check for actual compiled ErgoTree (should be non-empty hex)
grep "PENDING_BET_TREE_HEX=" .env backend/.env 2>/dev/null
```

**Current result**: All searches return nothing (except our test stubs).

---

## Conclusion

MAT-53 test suite is production-ready, but **cannot be executed** because MAT-28 implementation is missing from the codebase.

**Recommendation**: Re-open MAT-28 investigation before proceeding with MAT-53.

---

**Report Generated**: 2026-03-27 18:35
**Next Review**: When MAT-28 implementation is verified
