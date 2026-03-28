# MAT-217: Bankroll Monitoring Service E2E Test Plan

**Issue**: MAT-217  
**Type**: QA Documentation  
**Status**: Test Plan (waiting for implementation)  
**Parent Issue**: MAT-204 (cancelled - bankroll monitoring service)  

## Overview

This document outlines the comprehensive E2E test strategy for the DuckPools bankroll monitoring service. Since MAT-204 (the implementation) is cancelled, this test plan serves as a specification for when the bankroll monitoring feature is re-implemented or when a new implementation is created.

## Test Objectives

Verify that the bankroll monitoring service:
1. Accurately tracks house wallet balance (ERG + tokens)
2. Calculates exposure from unresolved bets correctly
3. Computes max payout capacity accurately
4. Provides REST API endpoints with real-time data
5. Handles edge cases and concurrency correctly
6. Triggers low bankroll alerts at the configured threshold

## Test Environment

### Required Services
- Ergo node: `http://localhost:9052`
- Backend API: `http://localhost:8000`
- Paperclip DB: `127.0.0.1:54329`

### Environment Variables
```bash
NODE_URL=http://localhost:9052
EXPLORER_URL=http://localhost:9052
HOUSE_ADDRESS=<house-wallet-address>
COINFLIP_NFT_ID=<coinflip-nft-id>
API_KEY=<api-key>
BACKEND_URL=http://localhost:8000
```

## Test Cases

### TC-001: Basic Bankroll Status Endpoint

**Preconditions**:
- Backend is running
- Ergo node is synced
- House wallet exists with balance

**Steps**:
1. `GET http://localhost:8000/bankroll/status`
2. Verify response contains:
   - `balance` (nanoERG)
   - `exposure` (nanoERG)
   - `available` (nanoERG)
   - `pendingBets` (count)
   - `lastUpdate` (ISO 8601 timestamp)

**Expected Results**:
- HTTP 200 OK
- JSON response with all required fields
- `balance` matches node API house wallet balance
- `lastUpdate` is recent (within 10 seconds)

**Verification Method**:
```bash
# Compare balance from bankroll endpoint with node API
curl http://localhost:9052/wallet/balances
# Should match bankroll/status balance
```

---

### TC-002: Balance Accuracy - Empty State

**Preconditions**:
- No pending bets
- House wallet has known balance

**Steps**:
1. Check house wallet balance via node API
2. Call `GET /bankroll/status`
3. Verify `balance` matches node balance
4. Verify `exposure = 0`
5. Verify `available = balance`

**Expected Results**:
- `balance` == node wallet balance
- `exposure` == 0
- `available` == `balance`
- `pendingBets` == 0

---

### TC-003: Exposure Calculation - Single Bet

**Preconditions**:
- House wallet has initial balance
- No pending bets

**Steps**:
1. Record initial `balance` and `available`
2. Place a coinflip bet (e.g., 1 ERG)
3. Wait for PendingBet box creation
4. Call `GET /bankroll/status`
5. Verify `exposure` equals bet amount
6. Verify `available = balance - exposure`

**Expected Results**:
- `exposure` increases by bet amount
- `available` decreases by bet amount
- `balance` unchanged
- `pendingBets` == 1

---

### TC-004: Exposure Calculation - Multiple Pending Bets

**Preconditions**:
- House wallet with sufficient balance

**Steps**:
1. Place 5 coinflip bets (varying amounts: 0.5, 1, 2, 3, 5 ERG)
2. Do not reveal any bets
3. Call `GET /bankroll/status`
4. Verify `exposure` = sum of all 5 bet amounts
5. Verify `available = balance - exposure`

**Expected Results**:
- `exposure` = 11.5 ERG (0.5 + 1 + 2 + 3 + 5)
- `available` = `balance` - 11.5 ERG
- `pendingBets` == 5

---

### TC-005: Exposure Reduction - Bet Resolution

**Preconditions**:
- Multiple pending bets exist

**Steps**:
1. Record current `exposure` and `pendingBets`
2. Reveal and resolve 2 of the pending bets
3. Call `GET /bankroll/status`
4. Verify `exposure` decreased by resolved bet amounts
5. Verify `pendingBets` decreased by 2

**Expected Results**:
- `exposure` reflects only unresolved bets
- `pendingBets` reflects current count
- `available` updated correctly

---

### TC-006: Max Payout Capacity Calculation

**Preconditions**:
- House wallet with balance
- Some pending bets

**Steps**:
1. Call `GET /bankroll/status`
2. Calculate expected max payout:
   - `maxPayout = available - (house_edge * exposure)`
   - Or verify API returns `maxPayout` field
3. Attempt to place bet > `maxPayout`
4. Verify bet is rejected

**Expected Results**:
- API returns correct max payout capacity
- Bets exceeding max payout are rejected with clear error

---

### TC-007: On-Chain Balance Verification

**Preconditions**:
- House wallet with known on-chain balance

**Steps**:
1. Get house wallet balance via node:
   ```bash
   curl http://localhost:9052/wallet/balances
   ```
2. Call `GET /bankroll/status`
3. Get all unspent boxes with COINFLIP_NFT_ID:
   ```bash
   curl http://localhost:9052/blockchain/box/unspent/byTokenId/{NFT_ID}
   ```
4. Sum all PendingBet box values
5. Verify:
   - `balance` from API == wallet balance
   - `exposure` from API == sum of PendingBet values

**Expected Results**:
- Perfect match between API and node data
- No off-by-one errors
- All pending bets accounted for

---

### TC-008: Low Bankroll Alert Threshold

**Preconditions**:
- Alert threshold configured (e.g., 100 ERG)
- House wallet balance > threshold

**Steps**:
1. Verify no alert present
2. Place bets until `available` drops below threshold
3. Monitor for alert trigger
4. Check for alert via API endpoint or logs

**Expected Results**:
- Alert triggers when `available` < threshold
- Alert contains current `available`, `balance`, `exposure`
- Alert is logged or sent via configured channel

**Verification**:
```bash
# Check if alert endpoint exists
GET /bankroll/alerts
# Should return active alerts
```

---

### TC-009: Zero Balance Edge Case

**Preconditions**:
- House wallet with minimal balance (for test)

**Steps**:
1. Drain house wallet to near zero (test setup)
2. Call `GET /bankroll/status`
3. Verify no crash, returns zeros

**Expected Results**:
- HTTP 200 OK
- `balance` == 0 or minimal
- `exposure` == 0
- `available` == 0 or negative (handled correctly)
- No 500 errors

---

### TC-010: Large Balance Scenario (100k+ ERG)

**Preconditions**:
- Simulated large balance (use testnet)

**Steps**:
1. Mock or set large balance via test setup
2. Place multiple bets totaling 50k ERG
3. Call `GET /bankroll/status`
4. Verify all calculations correct with large numbers

**Expected Results**:
- No integer overflow
- Correct calculations with nanoERG precision
- Performance acceptable (response < 500ms)

---

### TC-011: Concurrent Bet Resolution During Monitoring

**Preconditions**:
- Multiple pending bets

**Steps**:
1. Start loop: call `GET /bankroll/status` 10 times rapidly
2. During loop, simultaneously resolve 3 bets in background
3. Verify all API calls return consistent data
4. Check for race conditions or stale reads

**Expected Results**:
- No data corruption
- No duplicate counting
- Final state correct
- No race condition errors

**Verification**:
```python
# Python test script
import asyncio
import aiohttp

async def stress_test():
    tasks = []
    for i in range(10):
        tasks.append(get_bankroll_status())
    
    # In parallel, resolve some bets
    # ...
    
    results = await asyncio.gather(*tasks)
    # Verify consistency
```

---

### TC-012: API Response Caching

**Preconditions**:
- Backend with 10s cache configured

**Steps**:
1. Call `GET /bankroll/status` at t=0
2. Wait 2 seconds, call again
3. Verify `lastUpdate` same (cached)
4. Wait 10 seconds, call again
5. Verify `lastUpdate` updated (refreshed)

**Expected Results**:
- Cache respects 10s TTL
- `lastUpdate` indicates actual data freshness
- Cache invalidates on bet events

---

### TC-013: Real-time Updates on Bet Events

**Preconditions**:
- WebSocket or event-driven updates configured

**Steps**:
1. Open WebSocket connection to bankroll updates
2. Place bet
3. Verify immediate push update
4. Reveal bet
5. Verify immediate push update

**Expected Results**:
- WebSocket receives updates on bet events
- Updates contain new `balance`, `exposure`, `available`
- Latency < 1 second

**Verification**:
```javascript
// WebSocket test
const ws = new WebSocket('ws://localhost:8000/bankroll/stream');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Bankroll update:', data);
  // Verify data fields
};
```

---

### TC-014: Error Handling - Node API Down

**Preconditions**:
- Ergo node running

**Steps**:
1. Stop Ergo node
2. Call `GET /bankroll/status`
3. Verify appropriate error response

**Expected Results**:
- HTTP 503 Service Unavailable or 502 Bad Gateway
- Clear error message
- No crash
- Automatic retry when node returns

---

### TC-015: Error Handling - Invalid Token ID

**Preconditions**:
- Invalid COINFLIP_NFT_ID configured

**Steps**:
1. Set COINFLIP_NFT_ID to invalid value
2. Restart backend
3. Call `GET /bankroll/status`
4. Verify graceful handling

**Expected Results**:
- Returns balance correctly
- `exposure` = 0 (no boxes found)
- No crash
- Clear warning in logs

---

## Test Automation Plan

### Test File Structure
```
tests/
├── test_bankroll_monitoring.py  # Main test suite
└── utils/
    └── bankroll_helpers.py      # Helper functions
```

### Key Test Functions

```python
# test_bankroll_monitoring.py

import pytest
import httpx
import asyncio
from decimal import Decimal

async def test_bankroll_status_basic():
    """TC-001: Basic bankroll status endpoint"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_URL}/bankroll/status",
            headers={"api_key": API_KEY},
            timeout=10.0
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "balance" in data
        assert "exposure" in data
        assert "available" in data
        assert "pendingBets" in data
        assert "lastUpdate" in data


async def test_exposure_single_bet():
    """TC-003: Exposure calculation for single bet"""
    # ... implementation


async def test_on_chain_balance_verification():
    """TC-007: Verify balance matches node API"""
    # ... implementation


async def test_concurrent_bet_resolution():
    """TC-011: Test race conditions during concurrent operations"""
    # ... implementation
```

### Helper Functions

```python
# utils/bankroll_helpers.py

async def get_house_wallet_balance(node_url: str, api_key: str) -> int:
    """Get house wallet balance from Ergo node"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{node_url}/wallet/balances",
            headers={"api_key": api_key}
        )
        response.raise_for_status()
        data = response.json()
        return data[0]["balance"]  # nanoERG


async def get_pending_bet_boxes(node_url: str, nft_id: str) -> list:
    """Get all PendingBet boxes by token ID"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{node_url}/blockchain/box/unspent/byTokenId/{nft_id}"
        )
        response.raise_for_status()
        return response.json()


async def calculate_exposure_from_boxes(boxes: list) -> int:
    """Calculate exposure from PendingBet box values"""
    return sum(box["value"] for box in boxes)
```

## Success Criteria

All tests pass:
- [ ] TC-001: Basic endpoint
- [ ] TC-002: Empty state
- [ ] TC-003: Single bet exposure
- [ ] TC-004: Multiple bets exposure
- [ ] TC-005: Exposure reduction
- [ ] TC-006: Max payout capacity
- [ ] TC-007: On-chain verification
- [ ] TC-008: Alert threshold
- [ ] TC-009: Zero balance edge case
- [ ] TC-010: Large balance scenario
- [ ] TC-011: Concurrent operations
- [ ] TC-012: API caching
- [ ] TC-013: Real-time updates
- [ ] TC-014: Node API error handling
- [ ] TC-015: Invalid token handling

## Blocking Issues

- **MAT-204 is cancelled**: No bankroll monitoring implementation exists
- Need new issue for bankroll monitoring implementation
- Test automation can be written once implementation exists

## Next Steps

1. **Immediate**: Submit this test plan as PR for review
2. **When MAT-204 is re-opened or replaced**:
   - Implement test automation in `tests/test_bankroll_monitoring.py`
   - Run full test suite
   - Post results as comment on this issue
   - File bug reports for any failures

## Resources

- MAT-204: [Cancelled] Bankroll monitoring service implementation
- Backend API: `http://localhost:8000`
- Ergo Node API: `http://localhost:9052`
- Coinflip NFT ID: `{COINFLIP_NFT_ID}`

---

**Prepared by**: QA Tester Jr (780f04f8-c43c-496e-a126-6a95acb76aae)  
**Date**: 2026-03-28  
**Status**: Test Plan Complete - Waiting for Implementation
