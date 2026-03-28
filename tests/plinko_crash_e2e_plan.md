# MAT-164: E2E Test Plan - Plinko/Crash Game

## Status
**BLOCKED** - Waiting for MAT-17 (Add Plinko and/or crash game) to complete.

## Dependencies
- **MAT-17**: Must be complete before executing tests
- **MAT-14** (Dice): Should be complete; shared RNG infrastructure must be stable
- **Coinflip MVP**: Baseline for regression comparison

## Test Suite Location
- `tests/plinko_crash_e2e_plan.md` - This document (test plan)
- Execution: Manual via Chrome DevTools MCP + backend/node API verification
- Future automation: `tests/test_plinko_crash_e2e.py` (to be created when implementation is available)

---

## Pre-Conditions Checklist

Before running any test cases, verify ALL of the following:

- [ ] Ergo node running and synced: `curl -s http://localhost:9052/info | jq .fullHeight` returns a height > 0
- [ ] Node wallet unlocked: `curl -s http://localhost:9052/wallet/status -H "api_key: hello"` shows `"isUnlocked": true`
- [ ] Backend API healthy: `curl -s http://localhost:8000/health` returns 200 with node + wallet status
- [ ] Frontend running: `http://localhost:3000` loads without errors
- [ ] Nautilus wallet installed (Chrome extension) with test ERG balance > 1 ERG
- [ ] WebSocket connection functional (check via browser DevTools Network tab)
- [ ] Shared RNG commitment endpoint responding: `curl -s http://localhost:8000/commitment`

---

## Game Context

### Plinko (if implemented)
- Ball drops through a pegboard (typically 8-12 rows)
- Landing zone (slot at bottom) determines payout multiplier
- Higher-risk outer slots = higher multiplier, center slots = lower multiplier (near 1x)
- Player chooses number of rows (risk level) and bet amount
- Same SHA-256 commit-reveal RNG as coinflip/dice

### Crash (if implemented)
- Multiplier starts at 1.00x and climbs
- Player must cash out BEFORE the game "crashes"
- Crash point is predetermined via commit-reveal RNG
- Longer you wait = higher multiplier = more risk
- If crash happens before cash out = player loses entire bet

### Shared Infrastructure (both games)
- Commitment: `SHA256(secret_8_bytes || game_params)`
- RNG: `SHA256(blockHash_as_utf8 || secret_bytes)`, outcome from first bytes
- House edge: variable based on game parameters
- On-chain: PendingBet box with game-specific registers

---

## Test Cases

### PLINKO TESTS

---

#### TC-PLK-01: Page Load and Game Rendering
**Objective**: Verify Plinko game page renders correctly with all UI elements

**Preconditions**: Frontend running, wallet connected
**Steps**:
1. Navigate to Plinko game page (via game selector or direct URL)
2. Verify Plinko board renders with correct number of peg rows (default 8)
3. Verify ball drop animation area is visible
4. Verify bet amount input field is present
5. Verify rows selector (or risk level selector) is present
6. Verify "Drop Ball" or "Bet" button is present and enabled
7. Verify payout table/multiplier preview is visible
8. Open browser console, check for no JS errors

**Expected Result**: All UI elements render correctly, no console errors, board dimensions are proportional

**Pass/Fail Criteria**:
- PASS: All 8 checks pass, no console errors
- FAIL: Any element missing, rendering broken, or JS error present

---

#### TC-PLK-02: Bet Placement - Happy Path (Low Risk)
**Objective**: Verify placing a Plinko bet with default/low-risk settings

**Preconditions**: Wallet connected with >= 0.1 ERG, backend healthy
**Steps**:
1. Set bet amount to 0.01 ERG
2. Select low risk (e.g., 8 rows)
3. Click "Drop Ball"
4. Verify transaction prompt appears in Nautilus
5. Sign the transaction
6. Verify ball animation plays (drops through pegs)
7. Wait for ball to land in a slot
8. Verify result displayed (win/loss, multiplier, payout amount)
9. Check game history for the bet entry

**Expected Result**: Transaction succeeds, animation plays, result matches expected payout for landing slot, history updated

**Pass/Fail Criteria**:
- PASS: Full flow completes, result correct, history updated
- FAIL: Transaction fails, animation broken, or result mismatch

---

#### TC-PLK-03: Bet Placement - High Risk (Many Rows)
**Objective**: Verify Plinko with maximum rows (high risk, extreme multipliers)

**Preconditions**: Wallet connected with >= 0.1 ERG
**Steps**:
1. Set bet amount to 0.01 ERG
2. Select maximum risk (12 or 16 rows)
3. Verify multiplier table updates to show extreme payouts (up to 1000x+ for outermost slots)
4. Click "Drop Ball" and sign transaction
5. Verify ball animation handles increased rows smoothly
6. Verify result and payout

**Expected Result**: Animation remains smooth at max rows, multipliers are correct for the risk level, payout calculation accurate

**Pass/Fail Criteria**:
- PASS: Smooth animation, correct multipliers, accurate payout
- FAIL: Frame drops, wrong multipliers, or payout error

---

#### TC-PLK-04: Multiplier Table Accuracy
**Objective**: Verify displayed multipliers match the mathematical model

**Preconditions**: Frontend loaded on Plinko page
**Steps**:
1. For each risk level (rows count), record all displayed multipliers
2. Calculate expected multipliers using formula: `multiplier = (1 / probability) * (1 - house_edge)`
3. Verify each slot's multiplier matches expected within 0.01 tolerance
4. Verify house edge is consistent with the game's stated edge

**Expected Result**: All displayed multipliers match calculated values within tolerance

**Pass/Fail Criteria**:
- PASS: All multipliers within 0.01 of expected
- FAIL: Any multiplier deviates by more than 0.01

---

#### TC-PLK-05: On-Chain Transaction Verification
**Objective**: Verify Plinko bet appears correctly on Ergo blockchain

**Preconditions**: Successful bet placed, tx ID obtained
**Steps**:
1. Get transaction ID from the bet result
2. Query node: `GET /blockchain/transaction/byId/{txId}` with api_key
3. Verify transaction inputs include correct UTXOs
4. Verify outputs include a PendingBet box with:
   - Correct NFT (COINFLIP_NFT_ID or game-specific NFT)
   - R4: Player's ErgoTree
   - R5: Commitment hash (32 bytes)
   - R6: Game type identifier (e.g., "plinko" encoded)
   - R7: Game parameters (rows, target slot, etc.)
   - R8: Bet ID (32 bytes)
5. Verify via explorer URL: `https://testnet.ergoplatform.com/en/transactions/{txId}`

**Expected Result**: Transaction confirmed on-chain, PendingBet box has correct registers

**Pass/Fail Criteria**:
- PASS: All register values correct, transaction confirmed
- FAIL: Missing/wrong registers, unconfirmed, or transaction not found

---

#### TC-PLK-06: Provably-Fair Verification - Plinko
**Objective**: Verify Plinko uses the same commit-reveal scheme and outcome is verifiable

**Preconditions**: Completed bet with known secret
**Steps**:
1. Before bet: note the commitment hash displayed
2. After reveal: obtain the server's pre-commitment from `GET /commitment`
3. Verify commitment = `SHA256(player_secret || game_params)` using crypto.ts functions
4. Verify RNG: `SHA256(blockHash_utf8 || player_secret)` determines landing slot
5. Verify the mapping from RNG output to landing slot is correct
6. Compare displayed result with independently computed result

**Expected Result**: Commitment matches, RNG outcome determines correct slot, result is reproducible

**Pass/Fail Criteria**:
- PASS: Full verification chain passes, result reproducible
- FAIL: Any step of the verification chain fails

---

#### TC-PLK-07: Balance Updates After Win
**Objective**: Verify ERG balance increases correctly on Plinko win

**Preconditions**: Wallet connected, known balance before bet
**Steps**:
1. Record wallet ERG balance before bet (from Nautilus or backend API)
2. Place a Plinko bet for 0.01 ERG
3. Wait for result (win scenario - may require multiple attempts)
4. Record new balance
5. Verify: `new_balance >= old_balance - 0.01 + (0.01 * multiplier) - fees`
6. Verify fee deduction is reasonable (< 0.005 ERG)

**Expected Result**: Balance increases by approximately `bet_amount * multiplier`, minus fees

**Pass/Fail Criteria**:
- PASS: Balance change matches expected within fee tolerance
- FAIL: Balance change outside expected range

---

#### TC-PLK-08: Balance Updates After Loss
**Objective**: Verify ERG balance decreases by bet amount on loss

**Preconditions**: Wallet connected, known balance before bet
**Steps**:
1. Record wallet ERG balance before bet
2. Place Plinko bet for 0.01 ERG
3. Wait for result (loss scenario)
4. Record new balance
5. Verify: `old_balance - new_balance ≈ 0.01 + fees`

**Expected Result**: Balance decreases by bet amount + transaction fees

**Pass/Fail Criteria**:
- PASS: Deduction matches bet + reasonable fees
- FAIL: Deduction significantly more or less than expected

---

#### TC-PLK-09: Invalid Bet Amount Handling
**Objective**: Verify edge cases for bet amount input

**Preconditions**: Wallet connected
**Steps**:
1. Try bet amount = 0 (or empty): verify button disabled or error shown
2. Try bet amount > wallet balance: verify error message displayed
3. Try negative amount: verify input rejected
4. Try non-numeric input: verify input sanitized/rejected
5. Try extremely large number (1e18 ERG): verify handled gracefully
6. Try bet amount = 0.000000001 ERG (below dust limit): verify rejected

**Expected Result**: All invalid inputs are rejected with clear error messages, no crashes

**Pass/Fail Criteria**:
- PASS: All 6 invalid inputs handled gracefully
- FAIL: Any invalid input causes crash or is accepted

---

#### TC-PLK-10: Multiple Rapid Bets (Concurrency)
**Objective**: Verify system handles rapid sequential Plinko bets

**Preconditions**: Wallet connected with >= 0.5 ERG
**Steps**:
1. Place 5 bets in quick succession (as fast as Nautilus allows signing)
2. Verify all 5 transactions are submitted
3. Verify all 5 appear in game history
4. Verify on-chain: all 5 PendingBet boxes created (before reveals)
5. Verify no duplicate bet IDs
6. Verify no transaction failures due to UTXO double-spend

**Expected Result**: All 5 bets succeed, unique IDs, no conflicts

**Pass/Fail Criteria**:
- PASS: All 5 bets process correctly
- FAIL: Any bet fails, duplicate ID, or UTXO conflict

---

### CRASH TESTS

---

#### TC-CRS-01: Page Load and Game Rendering
**Objective**: Verify Crash game page renders correctly

**Preconditions**: Frontend running, wallet connected
**Steps**:
1. Navigate to Crash game page
2. Verify multiplier display (starts at 1.00x) is visible and prominent
3. Verify bet amount input is present
4. Verify "Place Bet" / "Cash Out" button is present
5. Verify game history/graph of recent crashes is visible
6. Verify auto-cash-out input field is present (if feature implemented)
7. Open browser console, check for no JS errors

**Expected Result**: All UI elements render, multiplier display is prominent, no console errors

**Pass/Fail Criteria**:
- PASS: All checks pass, clean console
- FAIL: Missing elements, broken rendering, or JS errors

---

#### TC-CRS-02: Bet Placement - Happy Path
**Objective**: Verify placing a Crash bet and the game lifecycle

**Preconditions**: Wallet connected with >= 0.1 ERG
**Steps**:
1. Set bet amount to 0.01 ERG
2. Click "Place Bet"
3. Verify Nautilus signing prompt appears
4. Sign transaction
5. Verify multiplier starts climbing (1.00x -> increasing)
6. Verify "Cash Out" button becomes active during the round
7. Click "Cash Out" at some multiplier (e.g., 1.5x)
8. Verify payout = bet_amount * cashout_multiplier
9. Verify result displayed: "Cashed out at 1.5x"
10. Check game history for the entry

**Expected Result**: Full lifecycle completes, payout correct, history updated

**Pass/Fail Criteria**:
- PASS: Complete flow works, payout accurate
- FAIL: Any step fails, wrong payout, or crash

---

#### TC-CRS-03: Crash Before Cash Out (Loss)
**Objective**: Verify player loses bet when game crashes before cashing out

**Preconditions**: Wallet connected with >= 0.1 ERG
**Steps**:
1. Place bet for 0.01 ERG
2. Do NOT cash out - let the multiplier climb
3. Wait for crash to occur (may take several rounds)
4. Verify display shows "Crashed at X.XXx"
5. Verify bet amount is lost (balance decreases by bet + fees)
6. Verify game history shows loss

**Expected Result**: Crash event displays, player loses bet amount, history correct

**Pass/Fail Criteria**:
- PASS: Loss scenario works correctly
- FAIL: Crash doesn't trigger, wrong display, or balance incorrect

---

#### TC-CRS-04: Auto Cash Out
**Objective**: Verify auto cash out feature (if implemented)

**Preconditions**: Wallet connected, auto cash out feature available
**Steps**:
1. Set bet amount to 0.01 ERG
2. Set auto cash out to 2.00x
3. Place bet
4. Do NOT manually cash out
5. Verify game automatically cashes out when multiplier hits 2.00x
6. Verify payout = 0.01 * 2.00 = 0.02 ERG (minus house edge)
7. Verify "Auto cashed out at 2.00x" displayed

**Expected Result**: Auto cash out triggers at correct multiplier, payout accurate

**Pass/Fail Criteria**:
- PASS: Auto cash out works at target multiplier
- FAIL: Doesn't trigger, triggers at wrong time, or wrong payout

---

#### TC-CRS-05: Auto Cash Out Above Crash Point
**Objective**: Verify auto cash out doesn't trigger if crash happens first

**Preconditions**: Wallet connected
**Steps**:
1. Set auto cash out to 100x (very high, unlikely to reach)
2. Place bet
3. Wait for crash (should happen well before 100x)
4. Verify auto cash out did NOT trigger
5. Verify player lost the bet

**Expected Result**: Crash occurs before auto cash out, player loses

**Pass/Fail Criteria**:
- PASS: Crash beats auto cash out correctly
- FAIL: Auto cash out triggers after crash or other error

---

#### TC-CRS-06: Crash Point Distribution
**Objective**: Verify crash points follow expected distribution (no manipulation)

**Preconditions**: Backend healthy, time for 20+ rounds
**Steps**:
1. Place 20+ small bets (0.001 ERG each) with no cash out
2. Record all 20+ crash points
3. Calculate statistics: mean, median, min, max
4. Verify distribution matches expected house edge model
5. Verify no crash point below 1.00x (shouldn't be possible)
6. Verify occasional high crash points (> 10x) appear (1/x distribution)
7. Test for uniformity: apply chi-squared test against expected exponential distribution

**Expected Result**: Crash points follow ~1/x distribution, consistent with house edge, no obvious manipulation

**Pass/Fail Criteria**:
- PASS: Distribution consistent with expected model (p > 0.05 on chi-squared)
- FAIL: Distribution significantly deviates, suggesting manipulation or bug

---

#### TC-CRS-07: Provably-Fair Verification - Crash
**Objective**: Verify Crash RNG is verifiable via commit-reveal

**Preconditions**: Completed crash round with known bet
**Steps**:
1. Record the commitment hash before the round
2. After crash: obtain server pre-commitment from `GET /commitment`
3. Verify commitment = `SHA256(player_secret || game_params)`
4. Verify crash point derivation from `SHA256(blockHash_utf8 || player_secret)`
5. Verify crash point formula matches displayed value
6. Compare: independently computed crash point vs displayed crash point

**Expected Result**: Full verification chain passes, crash point reproducible

**Pass/Fail Criteria**:
- PASS: Crash point verifiable and reproducible
- FAIL: Verification fails at any step

---

#### TC-CRS-08: On-Chain Verification - Crash
**Objective**: Verify Crash bet appears correctly on Ergo blockchain

**Preconditions**: Completed crash bet
**Steps**:
1. Get transaction ID
2. Query node: `GET /blockchain/transaction/byId/{txId}` with api_key
3. Verify PendingBet box with:
   - Correct NFT
   - R4: Player's ErgoTree
   - R5: Commitment hash
   - R6: Game type ("crash" encoded)
   - R7: Cash out multiplier (0 if no cash out)
   - R8: Bet ID
4. Verify settlement transaction sends correct amount based on outcome

**Expected Result**: On-chain data matches game state

**Pass/Fail Criteria**:
- PASS: All registers correct
- FAIL: Any register mismatch

---

### SHARED / CROSS-GAME TESTS

---

#### TC-SHR-01: Game Selector Navigation
**Objective**: Verify game selector allows switching between Coinflip, Dice, and Plinko/Crash

**Preconditions**: Frontend running with game selector (MAT-158)
**Steps**:
1. From coinflip, navigate to Plinko/Crash via game selector
2. Verify URL updates to correct route
3. Verify wallet connection persists across game switches
4. Navigate back to coinflip
5. Verify previous game state is not lost
6. Navigate to Dice, then to Plinko/Crash
7. Verify no full page reload (wallet stays connected)

**Expected Result**: Smooth navigation, wallet persists, no reload

**Pass/Fail Criteria**:
- PASS: All navigation works, wallet stable
- FAIL: Wallet disconnects, page reloads, or navigation broken

---

#### TC-SHR-02: WebSocket Real-Time Updates
**Objective**: Verify Plinko/Crash bet events stream via WebSocket

**Preconditions**: Frontend running, WebSocket endpoint available
**Steps**:
1. Open browser DevTools -> Network -> WS tab
2. Connect to WebSocket: `ws://localhost:8000/ws/bets?address={playerAddress}`
3. Place a Plinko/Crash bet in another tab or window
4. Verify WebSocket receives:
   - "placed" event with bet details
   - "revealed" event when game resolves
   - "resolved" event with final outcome
5. Verify event payloads contain correct bet_id, game_type, amount, outcome

**Expected Result**: All three event types received with correct data

**Pass/Fail Criteria**:
- PASS: All events received within 2 seconds
- FAIL: Missing events, wrong data, or connection drops

---

#### TC-SHR-03: Game History Filtering by Game Type
**Objective**: Verify game history shows Plinko/Crash bets and can filter

**Preconditions**: At least 1 coinflip and 1 plinko/crash bet played
**Steps**:
1. Open game history component
2. Verify both coinflip and plinko/crash bets appear
3. Use filter to show only Plinko bets
4. Verify only Plinko bets displayed
5. Use filter to show only Crash bets (if both implemented)
6. Verify "All Games" filter shows everything
7. Verify each entry shows: game type icon, amount, outcome, timestamp

**Expected Result**: Filtering works, correct bets shown per filter

**Pass/Fail Criteria**:
- PASS: All filters work correctly
- FAIL: Wrong bets shown, filter broken, or missing game type labels

---

#### TC-SHR-04: Leaderboard Integration
**Objective**: Verify Plinko/Crash bets contribute to leaderboard

**Preconditions**: Plinko/Crash bets completed
**Steps**:
1. Place several Plinko/Crash bets
2. Open leaderboard
3. Verify your address appears with correct total volume (includes all game types)
4. Verify win/loss counts are accurate across all game types
5. Verify sorting is correct (by volume or wins)

**Expected Result**: Leaderboard reflects cross-game activity

**Pass/Fail Criteria**:
- PASS: Leaderboard accurate across all game types
- FAIL: Plinko/Crash bets missing from leaderboard

---

#### TC-SHR-05: Player Stats Cross-Game
**Objective**: Verify player stats include Plinko/Crash data

**Preconditions**: Plinko/Crash bets completed
**Steps**:
1. Open player stats dashboard
2. Verify "Games Played" count includes Plinko/Crash
3. Verify "Total Volume" includes all game types
4. Verify "Win Rate" is calculated across all games
5. Verify per-game breakdown is shown (coinflip vs dice vs plinko/crash)

**Expected Result**: Stats comprehensive across all game types

**Pass/Fail Criteria**:
- PASS: All stats include Plinko/Crash data
- FAIL: Plinko/Crash data missing or incorrect

---

#### TC-SHR-06: Mobile Responsiveness
**Objective**: Verify Plinko/Crash renders correctly on mobile viewports

**Preconditions**: Frontend running
**Steps**:
1. Open Chrome DevTools, toggle device toolbar
2. Test at 375px (iPhone SE):
   - Plinko: verify board scales, bet controls accessible
   - Crash: verify multiplier display readable, cash out button reachable
3. Test at 768px (iPad):
   - Verify comfortable layout, no horizontal scroll
4. Test at 390px (iPhone 14):
   - Verify touch targets are at least 44px
5. Verify no layout shift during bet placement
6. Verify animations don't cause jank on mobile

**Expected Result**: Usable on all tested viewports, no horizontal scroll, touch-friendly

**Pass/Fail Criteria**:
- PASS: All 3 viewports work correctly
- FAIL: Broken layout, horizontal scroll, or unusable touch targets

---

#### TC-SHR-07: Performance Under Load
**Objective**: Verify no performance degradation during active Plinko/Crash sessions

**Preconditions**: Frontend running, wallet connected
**Steps**:
1. Open Chrome DevTools -> Performance tab
2. Start recording
3. Place 5 Plinko bets in rapid succession (if possible with animation overlap)
4. Or: let Crash run for 10 rounds
5. Stop recording
6. Check: FPS stays above 30 throughout
7. Check: no memory leaks (heap size stable)
8. Check: no layout thrashing in flame chart
9. Verify animation frame budget respected (16ms per frame)

**Expected Result**: Smooth performance, no jank, stable memory

**Pass/Fail Criteria**:
- PASS: FPS > 30, stable memory, no frame drops > 50ms
- FAIL: FPS drops below 30, memory leak, or significant jank

---

#### TC-SHR-08: Error Handling - Transaction Failed
**Objective**: Verify graceful handling when on-chain transaction fails

**Preconditions**: Wallet connected
**Steps**:
1. Place a bet but reject/deny the Nautilus signing prompt
2. Verify error message displayed to user (not a crash)
3. Verify UI returns to ready state (can place another bet)
4. If possible: simulate a node rejection (e.g., insufficient funds mid-bet)
5. Verify appropriate error message
6. Verify no orphaned game state

**Expected Result**: All failure modes handled gracefully with user-friendly messages

**Pass/Fail Criteria**:
- PASS: All 4 failure modes handled without crash
- FAIL: Any failure causes UI crash or stuck state

---

#### TC-SHR-09: Compensation Points for Plinko/Crash
**Objective**: Verify Plinko/Crash bets earn compensation points

**Preconditions**: Comp points system active, wallet connected
**Steps**:
1. Record current comp points balance
2. Place a Plinko/Crash bet
3. Wait for resolution
4. Verify comp points increased
5. Verify points awarded proportional to bet amount (same rate as coinflip/dice)
6. Check via API: `GET /player/comp/{address}`

**Expected Result**: Comp points awarded at consistent rate across all games

**Pass/Fail Criteria**:
- PASS: Points awarded correctly
- FAIL: No points awarded or wrong amount

---

## Security Tests

---

#### SEC-01: Cannot Manipulate Crash Point Client-Side
**Objective**: Verify crash point is determined server-side and cannot be tampered with

**Preconditions**: Crash game running
**Steps**:
1. Open browser DevTools -> Sources
2. Search for crash point calculation in frontend JS
3. Verify crash point is NOT calculated client-side
4. Verify crash point comes from on-chain reveal transaction
5. Attempt to modify WebSocket messages (if any) - verify server rejects tampered data
6. Verify commitment is published BEFORE bet placement (server can't change outcome after seeing bet)

**Expected Result**: Crash point is trustless and determined by commit-reveal, not client-side

**Pass/Fail Criteria**:
- PASS: No client-side manipulation possible
- FAIL: Crash point calculated client-side or commitment timing vulnerable

---

#### SEC-02: Cannot Predict Plinko Landing Slot
**Objective**: Verify Plinko outcome is not predictable

**Preconditions**: Plinko game running
**Steps**:
1. Place a bet and observe the commitment hash
2. Verify commitment is published before ball drop animation starts
3. Attempt to precompute outcome from commitment alone (should be impossible without secret)
4. Verify secret is only revealed during on-chain settlement

**Expected Result**: Outcome cannot be predicted before reveal

**Pass/Fail Criteria**:
- PASS: Full commit-before-reveal chain verified
- FAIL: Outcome predictable or commitment timing vulnerable

---

#### SEC-03: Double Spend Prevention
**Objective**: Verify cannot double-spend a single bet across games

**Preconditions**: Wallet connected
**Steps**:
1. Place a Plinko bet - get PendingBet box ID
2. Try to reference the same box in a coinflip bet transaction
3. Verify the second transaction fails (box already spent)
4. Verify no way to "cancel" a Plinko bet and reuse funds for coinflip simultaneously

**Expected Result**: Each UTXO can only be spent once

**Pass/Fail Criteria**:
- PASS: Double spend impossible
- FAIL: Double spend possible (CRITICAL bug)

---

## Regression Tests (Post-Integration)

These tests verify that existing coinflip/dice functionality is NOT broken by Plinko/Crash integration.

---

#### REG-01: Coinflip Still Works After Integration
**Objective**: Verify coinflip bet flow is unaffected

**Steps**:
1. Navigate to coinflip game
2. Place a standard coinflip bet (heads, 0.01 ERG)
3. Verify full commit-reveal flow works
4. Verify payout correct (1.94x for win)
5. Verify game history shows coinflip bet with correct type label

**Expected Result**: Coinflip identical to pre-integration behavior

---

#### REG-02: Dice Still Works After Integration
**Objective**: Verify dice bet flow is unaffected

**Steps**:
1. Navigate to dice game
2. Place a dice bet (roll under 50, 0.01 ERG)
3. Verify full flow works
4. Verify variable edge still correct
5. Verify game history shows dice bet correctly

**Expected Result**: Dice identical to pre-integration behavior

---

#### REG-03: LP Pool Unaffected
**Objective**: Verify LP pool operations still work

**Steps**:
1. Navigate to LP pool
2. Check pool state loads correctly
3. Verify TVL includes all game types
4. Verify deposit/withdraw buttons functional (if testing with real funds)

**Expected Result**: LP pool unchanged

---

## Tools Required

| Tool | Purpose |
|------|---------|
| Chrome DevTools MCP | UI testing, animations, console errors, network tab |
| Backend API (`localhost:8000`) | Health check, commitment, game history, pool state |
| Ergo Node API (`localhost:9052`) | Transaction verification, box inspection, balance checks |
| Nautilus Wallet (Chrome) | Transaction signing, balance verification |
| Explorer (`testnet.ergoplatform.com`) | Visual on-chain verification |
| WebSocket client | Real-time event verification |
| Python + pytest | Backend logic tests (if automated) |

## API Endpoints for Verification

```bash
# Health check
curl -s http://localhost:8000/health

# RNG commitment
curl -s http://localhost:8000/commitment

# Player stats (should include plinko/crash)
curl -s http://localhost:8000/player/stats/{address}

# Game history (should show plinko/crash bets)
curl -s http://localhost:8000/history/{address}

# Leaderboard
curl -s http://localhost:8000/leaderboard

# Comp points
curl -s http://localhost:8000/player/comp/{address}

# Pool state
curl -s http://localhost:8000/pool/state

# LP state
curl -s http://localhost:8000/lp/state

# On-chain transaction
curl -s http://localhost:9052/blockchain/transaction/byId/{txId} -H "api_key: hello"

# Unconfirmed transaction
curl -s http://localhost:9052/transactions/unconfirmed/byTransactionId/{txId} -H "api_key: hello"

# Box by ID
curl -s http://localhost:9052/blockchain/box/byId/{boxId} -H "api_key: hello"
```

## Test Data

| Parameter | Value |
|-----------|-------|
| Test bet amount | 0.01 ERG |
| Concurrency test amount | 0.001 ERG x 5 |
| Distribution test amount | 0.001 ERG x 20 |
| House edge range | 1% - 5% (variable by risk) |
| Min bet (expected) | 0.001 ERG |
| Max bet (expected) | 100 ERG or pool-dependent |
| Plinko rows | 8 (low risk) to 12/16 (high risk) |
| Crash auto cash out test | 2.00x |
| Crash impossible target | 100x |

## Known Risks and Considerations

1. **Animation Performance**: Plinko ball physics and Crash multiplier climbing require smooth 60fps animation. Test on low-end devices.

2. **RNG Timing**: If crash game requires real-time revelation (not block-based), the commit-reveal scheme may need adaptation. Verify timing is reasonable.

3. **House Edge for Plinko**: Multiplier distribution depends on pin physics (Gaussian). Verify the house edge is correctly applied to the Gaussian probability of each slot, not a uniform distribution.

4. **Crash Cash Out Timing**: If cash out is on-chain, there may be latency between clicking "Cash Out" and the transaction being confirmed. The displayed multiplier may differ from the actual on-chain multiplier. Verify UX handles this gracefully.

5. **Shared NFT**: Plinko/Crash may use the same NFT as coinflip (COINFLIP_NFT_ID) or a new game-specific NFT. Verify contract distinguishes game types.

## Execution Priority

1. **P0 (Must pass before launch)**: TC-PLK-01 through 08, TC-CRS-01 through 05, TC-SHR-01 through 03, SEC-01 through 03
2. **P1 (Should pass)**: TC-PLK-09 through 10, TC-CRS-06 through 08, TC-SHR-04 through 06, REG-01 through 03
3. **P2 (Nice to have)**: TC-SHR-07 through 09

---

**Test Plan Created**: 2026-03-27
**QA Developer**: QA Developer (e2f9759a-313d-46ab-a8a4-bb51dfac5c9b)
**Tracks**: MAT-17 (ee144dcd) - Add Plinko and/or crash game
**Template Based On**: MAT-53 timeout test plan format, MAT-140 dice test plan scope
