# E2E Test Plan: On-Chain Bet Flow (MAT-343)

## Overview
This test plan covers the end-to-end testing of the on-chain bet flow after MAT-343 (Wire SDK TransactionBuilder into CoinFlipGame) is implemented. The tests verify the complete user journey from wallet connection to bet resolution.

## Test Environment
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000  
- Ergo Node: http://localhost:9052 (api_key: hello)
- Nautilus Wallet: Chrome extension (incognito mode)
- Testnet ERG: Sufficient funds in test wallet

## Test Cases

### TC-1: Happy Path - Complete Bet Flow
**Objective:** Verify end-to-end successful bet placement and resolution
**Preconditions:** 
- User has Nautilus wallet with sufficient ERG balance
- DuckPools frontend is running
- Backend API is healthy

**Steps:**
1. Navigate to http://localhost:3000
2. Connect Nautilus wallet
3. Verify wallet address and balance display
4. Enter bet amount (e.g., 0.001 ERG)
5. Select heads or tails
6. Click "Place Bet"
7. Verify bet confirmation appears with transaction hash
8. Monitor bet status in Game History
9. Wait for bot to reveal (or trigger via API)
10. Verify result displayed (win/loss)
11. Verify ERG balance updated correctly

**Expected Results:**
- Wallet connects successfully
- Bet form validates input
- Transaction is created and broadcast
- Commitment phase shows correctly
- Reveal phase shows result
- Balance updates correctly (win: +1.94x, loss: -1x)
- No console errors

### TC-2: Insufficient Funds
**Objective:** Verify proper error handling for insufficient wallet balance
**Preconditions:** 
- User has Nautilus wallet with limited ERG balance

**Steps:**
1. Navigate to http://localhost:3000
2. Connect Nautilus wallet
3. Enter bet amount exceeding available balance
4. Click "Place Bet"

**Expected Results:**
- Error message displayed: "Insufficient funds for this bet"
- No transaction created
- Wallet balance unchanged
- User can adjust bet amount and retry

### TC-3: Rejected Transaction
**Objective:** Verify handling of rejected/failed transactions
**Preconditions:** 
- Network issues or invalid transaction parameters

**Steps:**
1. Navigate to http://localhost:3000
2. Connect Nautilus wallet
3. Enter valid bet amount
4. Select choice
5. Click "Place Bet"
6. Simulate transaction rejection (network error, invalid parameters)

**Expected Results:**
- Clear error message: "Transaction failed to broadcast"
- User can retry the bet
- No funds deducted from wallet
- Bet not recorded in history

### TC-4: Network Timeout
**Objective:** Verify timeout handling during transaction broadcast
**Preconditions:** 
- Slow network or high latency

**Steps:**
1. Navigate to http://localhost:3000
2. Connect Nautilus wallet
3. Enter bet amount
4. Select choice
5. Click "Place Bet"
6. Simulate network timeout during broadcast

**Expected Results:**
- Loading state with timeout indicator
- User can cancel or retry
- No funds deducted if timeout occurs
- Proper error recovery

### TC-5: Minimum Bet Validation
**Objective:** Verify minimum bet amount enforcement
**Preconditions:** 
- Standard test environment

**Steps:**
1. Navigate to http://localhost:3000
2. Connect Nautilus wallet
3. Enter amount below minimum (e.g., 0.0005 ERG)
4. Click "Place Bet"

**Expected Results:**
- Validation error: "Minimum bet is 0.001 ERG"
- Bet not placed
- User can increase amount and retry

### TC-6: Maximum Bet Validation  
**Objective:** Verify maximum bet amount enforcement
**Preconditions:** 
- Standard test environment

**Steps:**
1. Navigate to http://localhost:3000
2. Connect Nautilus wallet
3. Enter amount exceeding max bet (based on pool liquidity)
4. Click "Place Bet"

**Expected Results:**
- Validation error: "Maximum bet exceeded based on pool liquidity"
- Bet not placed
- User can reduce amount and retry

### TC-7: Session Persistence
**Objective:** Verify state persistence during bet flow
**Preconditions:** 
- Ongoing bet in commit phase

**Steps:**
1. Navigate to http://localhost:3000
2. Connect wallet and place bet
3. Refresh page during commit phase
4. Verify bet state is preserved
5. Complete bet flow

**Expected Results:**
- Bet state (commit phase) preserved after refresh
- User can continue with the same bet
- No duplicate bets created

### TC-8: Multiple Bets
**Objective:** Verify handling of multiple concurrent bets
**Preconditions:** 
- Sufficient wallet balance

**Steps:**
1. Navigate to http://localhost:3000
2. Connect wallet
3. Place first bet (heads, 0.001 ERG)
4. Place second bet (tails, 0.002 ERG)
5. Monitor both bets in history
6. Wait for resolution

**Expected Results:**
- Both bets placed successfully
- Separate transactions created
- Both bets resolve independently
- Correct balance updates

### TC-9: Zero Amount Bet
**Objective:** Verify zero amount bet rejection
**Preconditions:** 
- Standard test environment

**Steps:**
1. Navigate to http://localhost:3000
2. Connect wallet
3. Enter amount = 0
4. Click "Place Bet"

**Expected Results:**
- Validation error: "Amount must be positive"
- Bet not placed

### TC-10: Large Bet Amount
**Objective:** Verify large bet handling
**Preconditions:** 
- Sufficient wallet balance

**Steps:**
1. Navigate to http://localhost:3000
2. Connect wallet
3. Enter large valid amount (near max bet)
4. Place bet

**Expected Results:**
- Bet placed successfully
- Transaction created
- Proper handling of large amounts
- Correct balance updates

## Test Tools
- Chrome DevTools MCP (incognito mode)
- Terminal for API checks
- Network tab for transaction monitoring
- Console for error detection

## Success Criteria
- All test cases pass with expected results
- No critical bugs found
- Proper error handling and user feedback
- Smooth user experience throughout flow
- Consistent state management

## Reporting
- Document each test case with: PASS/FAIL, screenshots, error details
- File bug reports for any issues found
- Provide recommendations for improvements
- Mark test plan complete when all cases validated