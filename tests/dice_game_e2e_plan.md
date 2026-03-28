# DuckPools Dice Game - E2E Test Plan

> **Version**: 1.0  
> **Date**: 2026-03-27  
> **Author**: QA Developer (e2f9759a)  
> **Issue**: MAT-136 / MAT-140  
> **Tracks**: MAT-14 (Implement dice game - fc0ca054)  
> **Status**: READY FOR EXECUTION (blocked on MAT-14 completion)

---

## 1. Overview

The dice game is DuckPools' second game, extending the proven commit-reveal architecture from coinflip. Unlike coinflip's binary 50/50 outcome, dice uses a **1-100 range** with **variable house edge** based on the player's chosen probability threshold.

**Key differences from coinflip:**
- Outcome range: 1-100 (vs 0/1 for coinflip)
- Variable house edge: 2% at 50/50, scaling up to ~5% for extreme probabilities
- Multiplier formula: `(1 - house_edge) / (target / 100)`
- RNG extraction: `rng_hash[0] % 100 + 1` (or equivalent byte range extraction)
- Register layout likely extended (R6 = target number instead of 0/1 choice)

**Shared with coinflip:**
- Commit-reveal protocol (SHA256 commitment)
- Block hash + player secret for RNG
- Timeout/refund mechanism
- Backend wallet signing for off-chain bot reveals
- Nautilus EIP-12 wallet integration

---

## 2. Pre-conditions Checklist

Before ANY test case execution:

- [ ] Ergo node running at `http://localhost:9052` and synced
  - `curl -s http://localhost:9052/info | jq .fullHeight` returns a height
- [ ] Backend API running at `http://localhost:8000`
  - `curl -s http://localhost:8000/health` returns `{"status":"ok"}`
- [ ] Frontend dev server running at `http://localhost:3000`
  - Page loads without console errors
- [ ] Nautilus wallet extension installed with test ERG balance (>1 ERG)
- [ ] Dice game contract deployed on testnet (verify via backend `/scripts` endpoint or direct query)
- [ ] Dice NFT ID configured in backend `.env`
- [ ] Off-chain bot running and monitoring for dice PendingBet boxes
- [ ] WebSocket endpoint active: `ws://localhost:8000/ws/bets?address={addr}`

---

## 3. Test Cases

### 3.1 Contract Layer (On-Chain Verification)

#### TC-001: Dice contract deployment verification
- **Priority**: P0 (Blocker)
- **Preconditions**: Dice contract deployed
- **Steps**:
  1. Query backend `/scripts` endpoint for dice game ErgoTree
  2. Decode the ErgoTree and verify spending paths:
     - Path 1: Reveal (house reveals, outcome computed)
     - Path 2: Refund (timeout exceeded)
  3. Verify NFT token requirement in the script
  4. Check register layout matches spec (R4=player tree, R5=commitment, R6=target, R7=secret, R8=bet_id, R9=timeout)
- **Expected**: All spending paths present, NFT check exists, registers match documented layout
- **Pass/Fail**: FAIL if any path missing or register layout differs

#### TC-002: Commitment hash correctness on-chain
- **Priority**: P0 (Blocker)
- **Preconditions**: Contract deployed, player has wallet
- **Steps**:
  1. Player generates secret (8 bytes) and target (1-100)
  2. Compute `commitment = SHA256(secret_bytes || target_byte)` client-side
  3. Place bet via frontend, signing transaction with Nautilus
  4. After tx confirms, query the PendingBet box from node: `GET /blockchain/box/byId/{boxId}`
  5. Verify R5 register (commitment) matches client-computed value
- **Expected**: R5 value == SHA256(secret || target) computed independently
- **Pass/Fail**: FAIL if commitment mismatch (indicates serialization or hashing bug)

#### TC-003: RNG outcome uses full byte range (no bias)
- **Priority**: P0 (Blocker)
- **Preconditions**: Dice bet placed and revealed
- **Steps**:
  1. After reveal, extract `block_hash` and `secret` from the reveal transaction
  2. Compute `rng_hash = SHA256(block_hash_utf8 || secret_bytes)`
  3. Determine how the outcome is extracted:
     - If `first_byte % 100 + 1`: check if values 1-56 appear more than 57-100 (byte mod bias)
     - If `first_two_bytes % 100 + 1`: check uniform distribution
  4. Run 1000 simulated outcomes with random secrets and a fixed block hash
  5. Verify the distribution is statistically uniform (chi-squared test, p > 0.05)
- **Expected**: Uniform distribution across 1-100. If using `byte % 100`, bias MUST be documented and mitigated (e.g., rejection sampling)
- **Pass/Fail**: FAIL if `byte % 100` used without bias mitigation (values 1-56 appear 1.27x more than 57-100)
- **Note**: This was flagged in MAT-140. The implementation MUST use at least 2 bytes: `(first_two_bytes % 100) + 1` or implement rejection sampling

#### TC-004: Variable house edge on-chain verification
- **Priority**: P0 (Blocker)
- **Contract ref**: Dice contract reveal spending path
- **Steps**:
  1. Place a dice bet with target=50 (50% win probability)
  2. Place a dice bet with target=10 (10% win probability)
  3. Place a dice bet with target=95 (95% win probability)
  4. For each, verify the reveal transaction payout:
     - Target 50: multiplier = (1 - 0.02) / 0.50 = 1.96x
     - Target 10: multiplier = (1 - 0.05) / 0.10 = 9.50x
     - Target 95: multiplier = (1 - 0.02) / 0.95 = 1.03x
  5. Check actual nanoERG payout in the reveal transaction output
- **Expected**: Payout matches expected multiplier within tolerance (±1 nanoERG for rounding)
- **Pass/Fail**: FAIL if payout deviates >1 nanoERG from expected

#### TC-005: Timeout refund path works for dice
- **Priority**: P0 (Blocker)
- **Contract ref**: Dice contract PATH 2 (timeout)
- **Steps**:
  1. Place a dice bet with a short timeout (e.g., 10 blocks)
  2. Wait until timeout height is reached
  3. Check `/bet/expired` endpoint lists the bet
  4. Submit refund transaction via `/bet/build-refund-tx` endpoint
  5. Verify the PendingBet box is consumed and player receives full bet amount
- **Expected**: Player gets exactly bet amount (no deductions). PendingBet box no longer exists.
- **Pass/Fail**: FAIL if refund amount differs or box still exists

---

### 3.2 Backend / API Layer

#### TC-006: Backend serves dice game scripts
- **Priority**: P1 (Critical)
- **Steps**:
  1. `GET /api/scripts` (or equivalent dice-specific endpoint)
  2. Verify response includes dice game ErgoTree (different from coinflip)
  3. Verify dice NFT ID is included
- **Expected**: Dice-specific script bytes returned, distinct from coinflip script
- **Pass/Fail**: FAIL if only coinflip script returned or dice script missing

#### TC-007: Backend place-bet endpoint accepts dice parameters
- **Priority**: P1 (Critical)
- **Steps**:
  1. `POST /api/place-bet` with body: `{"game": "dice", "amount": 10000000, "target": 50}`
  2. Verify response includes transaction ID and commitment
  3. Verify commitment = SHA256(secret || target) 
- **Expected**: 200 response, valid tx_id, correct commitment hash
- **Pass/Fail**: FAIL if 400/500 error or commitment mismatch

#### TC-008: Backend build-reveal-tx computes correct dice outcome
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place a dice bet with known secret and target=50
  2. After block inclusion, call `POST /api/build-reveal-tx` with the box ID
  3. Verify the response includes the computed RNG outcome (1-100)
  4. Manually compute: `SHA256(blockHash_utf8 || secret_bytes)[0:2] % 100 + 1`
  5. Verify the "win" determination: outcome <= target
- **Expected**: Backend outcome matches manual computation
- **Pass/Fail**: FAIL if outcome mismatch or wrong win/lose determination

#### TC-009: Backend reveal uses correct variable multiplier
- **Priority**: P1 (Critical)
- **Steps**:
  1. For a winning reveal with target=25 (25% win chance, ~4% edge):
     - Expected multiplier = (1 - 0.04) / 0.25 = 3.84x
  2. Verify the reveal transaction sends `bet_amount * 3.84` nanoERG to player
  3. For a losing reveal, verify full bet amount goes to house address
- **Expected**: Correct multiplier applied; losses go entirely to house
- **Pass/Fail**: FAIL if payout amount is incorrect

#### TC-010: Game history includes dice bets
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place several dice bets (different targets)
  2. `GET /api/history/{address}`
  3. Verify each bet appears with:
     - game_type: "dice" (or equivalent discriminator)
     - target number
     - actual outcome
     - multiplier applied
     - payout amount
- **Expected**: All dice bets in history with correct metadata
- **Pass/Fail**: FAIL if dice bets missing or metadata incorrect

#### TC-011: WebSocket broadcasts dice bet events
- **Priority**: P1 (Critical)
- **Steps**:
  1. Connect to `ws://localhost:8000/ws/bets?address={player_address}`
  2. Place a dice bet via frontend
  3. Listen for `bet_placed` event
  4. Wait for bot reveal
  5. Listen for `bet_revealed` and `bet_resolved` events
  6. Verify events include dice-specific data (target, outcome number)
- **Expected**: All three events received with correct dice data
- **Pass/Fail**: FAIL if events missing or missing dice-specific fields

#### TC-012: Expired bets endpoint lists dice bets
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place dice bet with short timeout
  2. Wait for timeout
  3. `GET /api/bet/expired`
  4. Verify the expired dice bet appears with correct box ID and bet ID
- **Expected**: Expired dice bet listed
- **Pass/Fail**: FAIL if not listed or wrong metadata

#### TC-013: Timeout info endpoint works for dice
- **Priority**: P2 (Important)
- **Steps**:
  1. Place a dice bet
  2. `GET /api/bet/timeout-info?boxId={boxId}`
  3. Verify response includes timeout_height and current_height
  4. Verify remaining blocks calculated correctly
- **Expected**: Accurate timeout information
- **Pass/Fail**: FAIL if timeout data missing or incorrect

---

### 3.3 Frontend / UI Layer

#### TC-014: Dice game UI renders correctly
- **Priority**: P0 (Blocker)
- **Steps**:
  1. Navigate to `http://localhost:3000` (or `/play/dice` if game selector exists)
  2. Verify dice game component renders:
     - Slider or number input for target selection (1-100)
     - Current multiplier display (updates as target changes)
     - House edge percentage display
     - Bet amount input
     - Place Bet button
     - Current wallet balance
  3. Verify no console errors
- **Expected**: All UI elements visible, no errors
- **Pass/Fail**: FAIL if any element missing or console errors present

#### TC-015: Multiplier updates in real-time based on target
- **Priority**: P0 (Blocker)
- **Steps**:
  1. Set target to 50 -> verify multiplier ≈ 1.96x
  2. Set target to 10 -> verify multiplier ≈ 9.50x
  3. Set target to 95 -> verify multiplier ≈ 1.03x
  4. Set target to 1 -> verify multiplier ≈ 98.00x (edge caps)
  5. Set target to 99 -> verify multiplier ≈ 1.01x
  6. Verify the multiplier updates IMMEDIATELY as slider moves (no lag)
- **Expected**: Multiplier formula `(1 - edge) / (target/100)` applied correctly in real-time
- **Pass/Fail**: FAIL if multiplier display incorrect or laggy

#### TC-016: Dice bet placement flow via Nautilus
- **Priority**: P0 (Blocker)
- **Steps**:
  1. Connect Nautilus wallet
  2. Set target to 50, bet amount to 0.1 ERG
  3. Click "Place Bet"
  4. Verify Nautilus popup appears with transaction preview:
     - Correct bet amount
     - Dice game ErgoTree as output script
     - Commitment in R5, target in R6, secret in R7
  5. Sign transaction
  6. Verify frontend shows "Bet Placed" or pending state
  7. Verify commitment hash displayed
- **Expected**: Smooth bet placement, Nautilus signs correct transaction
- **Pass/Fail**: FAIL if Nautilus doesn't popup, wrong tx data, or error

#### TC-017: Win result display and animation
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place a dice bet
  2. Wait for reveal (bot processes)
  3. On win, verify:
     - Dice roll animation plays (or number display)
     - Win amount displayed with correct multiplier
     - Balance updates to reflect payout
     - Green color theme (#00ff88) applied
     - Confetti animation if implemented
  4. Verify the outcome number is displayed and <= target
- **Expected**: Clear win indication with correct payout
- **Pass/Fail**: FAIL if wrong payout shown or no visual feedback

#### TC-018: Loss result display
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place a dice bet
  2. Wait for reveal
  3. On loss, verify:
     - Outcome number displayed and > target
     - Loss amount shown
     - Red color theme (#ef4444) applied
     - Shake animation if implemented
     - Balance decreases by bet amount
- **Expected**: Clear loss indication
- **Pass/Fail**: FAIL if wrong outcome or no visual feedback

#### TC-019: Bet history shows dice bets with correct details
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place multiple dice bets with different targets
  2. Navigate to Game History component
  3. Verify each dice bet shows:
     - Game type indicator (dice icon/label)
     - Target number chosen
     - Outcome number rolled
     - Multiplier at time of bet
     - Win/loss status
     - Payout amount
     - Timestamp
- **Expected**: All dice bet details visible in history
- **Pass/Fail**: FAIL if details missing or incorrect

#### TC-020: Mobile responsive dice UI
- **Priority**: P1 (Critical)
- **Steps**:
  1. Open Chrome DevTools, set viewport to 375x667 (iPhone SE)
  2. Navigate to dice game
  3. Verify:
     - Slider/input usable with touch
     - Multiplier display visible
     - Bet amount input accessible
     - Place Bet button tappable (min 44x44px)
     - No horizontal scroll
     - Results display readable
  4. Repeat at 768x1024 (tablet)
- **Expected**: Fully usable on mobile and tablet
- **Pass/Fail**: FAIL if elements overlap, cut off, or untappable

#### TC-021: Wallet connection persists across game switching
- **Priority**: P2 (Important)
- **Steps**:
  1. Connect Nautilus wallet on coinflip page
  2. Navigate to dice game (via game selector or URL)
  3. Verify wallet still connected (address displayed, balance shown)
  4. Place a dice bet
  5. Navigate back to coinflip
  6. Verify wallet still connected
- **Expected**: Single wallet connection persists across all games
- **Pass/Fail**: FAIL if reconnection required when switching

---

### 3.4 Edge Cases

#### TC-022: Minimum bet enforcement
- **Priority**: P1 (Critical)
- **Steps**:
  1. Attempt to place a bet with amount below minimum (e.g., 0.0001 ERG)
  2. Verify frontend disables button or shows error
  3. If button enabled, attempt submission
  4. Verify backend returns 400 with clear error message
- **Expected**: Bet rejected before transaction creation
- **Pass/Fail**: FAIL if dust bet reaches blockchain

#### TC-023: Maximum bet enforcement
- **Priority**: P1 (Critical)
- **Steps**:
  1. Attempt to place a bet exceeding max (e.g., 1000 ERG or pool capacity)
  2. Verify appropriate error message
  3. Verify no transaction is created
- **Expected**: Bet rejected with clear message about max limit
- **Pass/Fail**: FAIL if oversized bet accepted

#### TC-024: Invalid target values rejected
- **Priority**: P1 (Critical)
- **Steps**:
  1. Attempt target = 0 (out of range)
  2. Attempt target = 101 (out of range)
  3. Attempt target = -1 (negative)
  4. Attempt target = 0.5 (non-integer)
  5. Verify each is rejected with appropriate error
- **Expected**: All invalid targets rejected before bet placement
- **Pass/Fail**: FAIL if any invalid target accepted

#### TC-025: Target = 1 and Target = 100 extreme multipliers
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place bet with target=1 (1% win chance)
  2. Verify multiplier displayed ≈ 98x (with ~2% edge: (1-0.02)/0.01 = 98)
  3. Place bet with target=100 (100% win chance)
  4. Verify multiplier displayed ≈ 0.98x (effectively guaranteed loss of edge)
  5. Verify backend accepts both bets
- **Expected**: Extreme targets handled correctly with proper multipliers
- **Pass/Fail**: FAIL if extreme targets rejected or wrong multipliers

#### TC-026: Double-bet prevention (same commitment)
- **Priority**: P2 (Important)
- **Steps**:
  1. Generate a commitment hash
  2. Attempt to place two bets with the same commitment
  3. Verify the second bet is rejected (by frontend validation or backend)
- **Expected**: Duplicate commitment rejected
- **Pass/Fail**: FAIL if duplicate commitment accepted (replay attack vector)

#### TC-027: Concurrent dice bets
- **Priority**: P2 (Important)
- **Steps**:
  1. Place two dice bets in quick succession (before first is revealed)
  2. Verify both PendingBet boxes are created with unique NFT instances
  3. Verify both are revealed independently
  4. Verify payouts are independent
- **Expected**: Multiple simultaneous bets work correctly
- **Pass/Fail**: FAIL if second bet overwrites first or causes errors

#### TC-028: Bet during wallet disconnection
- **Priority**: P2 (Important)
- **Steps**:
  1. Disconnect Nautilus wallet (lock it)
  2. Attempt to place a bet
  3. Verify clear error message: "Wallet not connected"
  4. Verify no transaction is attempted
- **Expected**: Graceful error handling
- **Pass/Fail**: FAIL if silent failure or confusing error

#### TC-029: Insufficient balance handling
- **Priority**: P2 (Important)
- **Steps**:
  1. Set bet amount higher than wallet balance
  2. Click Place Bet
  3. Verify frontend shows error before Nautilus popup
  4. OR verify Nautilus rejects with clear message
- **Expected**: User informed of insufficient balance
- **Pass/Fail**: FAIL if no error shown

#### TC-030: Network error during bet placement
- **Priority**: P2 (Important)
- **Steps**:
  1. Start bet placement
  2. Simulate network disconnect (disable network in DevTools)
  3. Verify error state displayed
  4. Reconnect network
  5. Verify user can retry without page refresh
- **Expected**: Graceful degradation and recovery
- **Pass/Fail**: FAIL if page crashes or stuck in loading state

---

### 3.5 Integration / Cross-Game

#### TC-031: Shared RNG infrastructure with coinflip
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place a coinflip bet and a dice bet with the SAME secret
  2. Wait for both to be revealed (same block)
  3. Verify both use `SHA256(blockHash_utf8 || secret_bytes)` for RNG
  4. Verify coinflip outcome = `hash[0] % 2`
  5. Verify dice outcome = dice-specific extraction from same hash
  6. Confirm both outcomes are deterministic given same inputs
- **Expected**: Same RNG infrastructure, different extraction methods
- **Pass/Fail**: FAIL if different hash algorithms or inputs used

#### TC-032: Pool balance reflects dice game activity
- **Priority**: P2 (Important)
- **Steps**:
  1. Note current pool bankroll via `/api/lp/pool`
  2. Place and resolve several dice bets (mix of wins and losses)
  3. Check pool bankroll again
  4. Verify net change equals sum of (house_edge * losing_bets - edge * winning_bets_payouts)
- **Expected**: Pool balance changes correctly
- **Pass/Fail**: FAIL if pool balance doesn't reflect dice activity

#### TC-033: Leaderboard includes dice game wins
- **Priority**: P2 (Important)
- **Steps**:
  1. Place winning dice bets from a specific address
  2. Check `/api/leaderboard` endpoint
  3. Verify the player's stats include dice game volume
- **Expected**: Dice game activity reflected in leaderboard
- **Pass/Fail**: FAIL if dice activity not counted

---

### 3.6 Security

#### TC-034: Commitment hiding - target not predictable from commitment
- **Priority**: P1 (Critical)
- **Steps**:
  1. Place 10 dice bets with known targets and secrets
  2. Record all (commitment, target) pairs
  3. Verify that for any commitment, the target cannot be determined without the secret
  4. Verify SHA256 preimage resistance: given commitment alone, cannot find matching (secret, target)
- **Expected**: Commitment reveals no information about target
- **Pass/Fail**: FAIL if any pattern in commitments correlates with targets

#### TC-035: Secret stored on-chain does not compromise fairness
- **Priority**: P2 (Important)
- **Steps**:
  1. Read R7 (secret) from a PendingBet box on chain
  2. Read R5 (commitment) and R6 (target)
  3. With knowledge of the secret, verify outcome is STILL unpredictable:
     - Outcome requires future block hash (unknown at bet time)
     - `SHA256(future_blockHash || known_secret)` is still unpredictable
- **Expected**: Knowing the secret does NOT allow predicting the outcome
- **Pass/Fail**: FAIL if secret exposure before reveal compromises fairness

#### TC-036: On-chain payout verification (no backend trust required for wins)
- **Priority**: P1 (Critical)
- **Contract ref**: Dice contract reveal path
- **Steps**:
  1. For a winning reveal, trace the transaction outputs:
     - Player output amount = bet_amount * multiplier
     - House output = remaining ERG (if any)
  2. Verify the contract SCRIPT enforces the payout (not just the backend)
  3. Confirm the payout calculation is part of the ErgoScript, not just a convention
- **Expected**: Payout math enforced on-chain in the contract script
- **Pass/Fail**: FAIL if payout is only determined by the backend bot (trust required)

---

## 4. Variable House Edge Reference Table

| Target | Win Prob | Expected Edge | Expected Multiplier | Example Bet (0.1 ERG) | Expected Payout |
|--------|----------|---------------|---------------------|----------------------|-----------------|
| 5      | 5%       | ~5%           | (0.95 / 0.05) = 19.0x | 0.1 ERG | 1.90 ERG |
| 10     | 10%      | ~5%           | (0.95 / 0.10) = 9.5x  | 0.1 ERG | 0.95 ERG |
| 25     | 25%      | ~4%           | (0.96 / 0.25) = 3.84x | 0.1 ERG | 0.384 ERG |
| 33     | 33%      | ~3%           | (0.97 / 0.33) = 2.94x | 0.1 ERG | 0.294 ERG |
| 50     | 50%      | ~2%           | (0.98 / 0.50) = 1.96x | 0.1 ERG | 0.196 ERG |
| 75     | 75%      | ~2%           | (0.98 / 0.75) = 1.31x | 0.1 ERG | 0.131 ERG |
| 95     | 95%      | ~2%           | (0.98 / 0.95) = 1.03x | 0.1 ERG | 0.103 ERG |

**Note**: Exact edge values depend on the implementation's edge schedule. This table uses the expected tiered model. Verify actual implementation against these values.

---

## 5. RNG Extraction Method (Critical Decision Point)

The RNG outcome extraction method MUST be verified in the dice contract:

**Option A (BIASED - REJECT):** `SHA256(blockHash || secret)[0] % 100 + 1`
- Byte range: 0-255, mod 100 produces values 0-99 (+1 = 1-100)
- Values 1-56 appear with probability 3/256 = 1.172%
- Values 57-100 appear with probability 2/256 = 0.781%
- Bias ratio: 1.56 to 1 (UNFAIR to players betting on high targets)

**Option B (ACCEPTABLE):** `SHA256(blockHash || secret)[0:2] as uint16 % 100 + 1`
- Two-byte range: 0-65535, mod 100 produces uniform 0-99
- Each value appears with probability ~65.536 or 65.537 / 65536
- Bias ratio: 1.000015 to 1 (NEGLIGIBLE)

**Option C (PERFECT):** Rejection sampling
- Take first byte, if >= 200, reject and use next byte
- Remaining 0-199 maps to 1-100 uniformly
- Requires worst-case 2-3 hash evaluations per outcome
- PERFECT uniformity but higher computational cost

**Recommendation**: Option B. Option C only if provable fairness is a marketing requirement.

---

## 6. Test Execution Priority

Execute in this order:

1. **P0 Blockers** (TC-001 through TC-005, TC-014 through TC-016): Contract correctness + basic UI
2. **P1 Critical** (TC-006 through TC-013, TC-017 through TC-020, TC-022 through TC-025, TC-031, TC-034, TC-036): Backend, UI polish, edge cases
3. **P2 Important** (TC-021, TC-026 through TC-030, TC-032, TC-033, TC-035): Integration, secondary edge cases

**Stop criteria**: Any P0 failure blocks dice game launch. Document and escalate immediately.

---

## 7. Tools & Commands Reference

```bash
# Node health
curl -s http://localhost:9052/info -H "api_key: hello" | jq .fullHeight

# Backend health
curl -s http://localhost:8000/health | python3 -m json.tool

# Get box by ID (full registers)
curl -s "http://localhost:9052/blockchain/box/byId/{boxId}" -H "api_key: hello" | python3 -m json.tool

# Unconfirmed tx check
curl -s "http://localhost:9052/transactions/unconfirmed/byTransactionId/{txId}" -H "api_key: hello"

# Game history
curl -s "http://localhost:8000/api/history/{address}"

# WebSocket (using websocat or wscat)
wscat -c "ws://localhost:8000/ws/bets?address={addr}"

# Manual RNG computation (Python)
python3 -c "
import hashlib
block_hash = '...'  # from node
secret = '...'      # 16 hex chars
rng = hashlib.sha256((block_hash).encode('utf-8') + bytes.fromhex(secret)).digest()
outcome = (rng[0] << 8 | rng[1]) % 100 + 1  # Option B
print(f'Outcome: {outcome}')
"

# Manual commitment verification
python3 -c "
import hashlib
secret = bytes.fromhex('...')  # 8 bytes
target = 50
commitment = hashlib.sha256(secret + bytes([target])).hexdigest()
print(f'Commitment: {commitment}')
"
```

---

## 8. Coordination Notes

- **Protocol Tester Jr (4a3b8aea)**: Assign on-chain verification tests (TC-001 through TC-005, TC-036) for independent review
- **Frontend Engineer (29913ee2)**: Assign UI test verification (TC-014 through TC-021) after implementation
- **Backend Engineer (b5ebae02)**: Assign API test verification (TC-006 through TC-013) after implementation
- **MAT-14 (fc0ca054)**: This test plan is BLOCKED on dice game implementation completion

---

## 9. Known Issues & Risks

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| R-01 | RNG bias if single-byte mod 100 used | HIGH | Verify implementation uses 2+ bytes |
| R-02 | Variable edge schedule not yet finalized | MEDIUM | Update reference table once confirmed |
| R-03 | Dice contract may not exist yet | HIGH | This plan is blocked on MAT-14 |
| R-04 | Off-chain bot may not support dice reveals yet | HIGH | Verify bot code before test execution |
| R-05 | No frontend dice component exists yet | HIGH | UI tests blocked on frontend implementation |

---

*End of test plan. Total: 36 test cases (7 P0, 17 P1, 12 P2).*
