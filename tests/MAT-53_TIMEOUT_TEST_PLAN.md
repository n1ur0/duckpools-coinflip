# MAT-53: QA Test Plan - Bet Timeout and Refund Mechanism

## Status
**BLOCKED** - Waiting for MAT-28 (Implement bet timeout and refund mechanism) to complete.

## Dependencies
- **MAT-28**: Must be complete to test timeout mechanism

## Test Suite Location
- `tests/test_timeout_refund.py` - Main test suite
- `tests/utils/timeout_helpers.py` - Helper functions for timeout testing

## Test Cases

### TC-1: Timeout Refund After Expiry
**Objective**: Verify players can reclaim funds after timeout

Steps:
1. Place bet with timeout register (e.g., 100 blocks)
2. Wait until timeout height passes
3. Submit refund transaction
4. Verify:
   - Refund transaction succeeds
   - Player receives bet amount back (minus fee)
   - PendingBet box is consumed

**Expected Result**: ✅ Player gets refund

---

### TC-2: Refund Blocked Before Timeout
**Objective**: Verify refund is rejected before timeout expires

Steps:
1. Place bet with timeout = current_height + 100
2. Immediately attempt refund
3. Verify:
   - Refund transaction FAILS (contract rejects)
   - PendingBet box remains unspent

**Expected Result**: ✅ Early refund rejected

---

### TC-3: Reveal Still Works Before Timeout
**Objective**: Verify timeout doesn't block normal reveal flow

Steps:
1. Place bet with timeout
2. Before timeout, submit valid reveal
3. Verify:
   - Reveal transaction succeeds
   - Normal bet flow completes

**Expected Result**: ✅ Normal flow unaffected

---

### TC-4: Timeout Value Correctness
**Objective**: Verify timeout register is set correctly

Steps:
1. Place bet with timeout_delta = 100
2. Inspect PendingBet box
3. Verify:
   - Timeout register = creation_height + 100

**Expected Result**: ✅ Timeout value correct

---

### TC-5: Multiple Expired Bets
**Objective**: Verify multiple expired bets can all be refunded

Steps:
1. Place 3 bets with short timeout
2. Wait for all to expire
3. Refund all 3 bets
4. Verify:
   - All refunds succeed
   - Total refunded = sum of bet amounts (minus fees)

**Expected Result**: ✅ All refunds succeed

---

## Security Tests

### S-1: No Replay Attack on Refund
**Objective**: Verify refund transactions cannot be replayed

Steps:
1. Expire a bet and refund it
2. Try to submit same refund transaction again
3. Verify: Second attempt rejected

**Expected Result**: ✅ Replay rejected

---

### S-2: Timeout Cannot Be Past Height
**Objective**: Verify timeout cannot be set to past height

Steps:
1. Try to place bet with negative timeout_delta
2. Verify: Transaction rejected

**Expected Result**: ✅ Past timeout rejected

---

### S-3: House Cannot Drain Timed Out Bets
**Objective**: Verify only player can refund their expired bet

Steps:
1. Expire a player's bet
2. Try to refund to house address instead of player
3. Verify: Transaction rejected

**Expected Result**: ✅ House refund rejected

---

## Prerequisites

### Contract Requirements (MAT-28 must implement)
1. PendingBet contract must have R9 register for timeout height
2. New spending path: if `HEIGHT >= R9`, allow refund to player (R4)
3. Refund path must verify caller is original player
4. Timeout must be set during bet creation (creation_height + delta)

### Infrastructure
- Ergo testnet node running (mining enabled)
- Backend API running (:8000)
- Test wallet with funds
- FleetSDK for transaction building

---

## Running Tests

### Setup
```bash
cd /Users/n1ur0/Documents/git/duckpools-coinflip

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio

# Verify node is running
curl http://localhost:9052/info | jq .fullHeight
```

### Run All Timeout Tests
```bash
pytest tests/test_timeout_refund.py -v
```

### Run Specific Test
```bash
# Run TC-1 only
pytest tests/test_timeout_refund.py::TestTimeoutRefund::test_tc1_timeout_refund_after_expiry -v

# Run security tests
pytest tests/test_timeout_refund.py -k "security" -v
```

### With Detailed Output
```bash
pytest tests/test_timeout_refund.py -v -s
```

---

## Expected Contract Behavior

### PendingBet Spending Paths

#### Path 1: Reveal (Existing)
- Condition: `HEIGHT < R9 AND valid_reveal_proof`
- Action: House takes bet, reveals to player, pays winner

#### Path 2: Refund (NEW - MAT-28)
- Condition: `HEIGHT >= R9 AND refund_address == R4`
- Action: Send bet amount back to player

### Register Layout

| Register | Type | Content |
|----------|------|---------|
| R4 | Coll[Byte] | Player's ErgoTree |
| R5 | Coll[Byte] | Commitment hash (32 bytes) |
| R6 | Int | Bet choice (0=heads, 1=tails) |
| R9 | Int | Timeout height (creation_height + delta) |

---

## Test Data

### Test Config
- Bet amount: 0.5 - 1.0 ERG (in testnet)
- Timeout delta: 50-100 blocks (adjustable per test)
- Testnet faucet address: https://faucet.nuergo.io/

### Test Addresses
- House: `3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26`
- Test Player: `3WtestPlayer...` (replace with actual)

---

## Checklist for MAT-28 Completion

Before running this test suite, verify MAT-28 is complete:

- [ ] PendingBet contract has R9 timeout register
- [ ] Contract allows refund spending path after timeout
- [ ] Backend `place-bet` endpoint accepts timeout_delta parameter
- [ ] Refund transaction builder implemented
- [ ] Tests pass locally on testnet
- [ ] Documented in AGENTS.md

---

## Notes

### Time Requirements
- TC-1: ~100 blocks (~8-10 minutes with mining)
- TC-5: ~50 blocks (~4-5 minutes per bet, can parallelize)
- Other tests: <5 minutes

### Fee Considerations
- Refund tx should have minimal fee (player gets most of bet back)
- Test suite allows ~0.003 ERG fee variance per tx

### Known Issues
- None (MAT-28 not yet implemented)

---

## Next Steps

1. **MAT-28 Implementation** - Engineer team to complete timeout mechanism
2. **Update Test Utilities** - Complete `timeout_helpers.py` functions once MAT-28 API is stable
3. **Run Test Suite** - Execute all TC-1 through TC-5 and security tests
4. **Report Results** - Document any failures and edge cases found
5. **MAT-53 Complete** - Mark as "done" when all tests pass

---

**Test Suite Created**: 2026-03-27
**QA Engineer**: Protocol Tester Jr (4a3b8aea-371e-47ec-91b4-9327a7e8ef6c)
