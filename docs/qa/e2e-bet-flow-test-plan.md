# E2E Test Plan: On-Chain Coinflip Bet Flow

> **Issue**: MAT-343 (Wire SDK TransactionBuilder into CoinFlipGame)
> **Author**: QA Tester Jr
> **Date**: 2026-03-29
> **Status**: Ready for execution (blocked on MAT-343 merge + MAT-344 contract deploy)

## Prerequisites

Before running ANY test case, these must be true:

1. `VITE_CONTRACT_P2S_ADDRESS` is set in `.env.local` (contract compiled, MAT-344 done)
2. `VITE_HOUSE_PUB_KEY` is set in `.env.local` (house wallet public key)
3. Ergo node running at `http://127.0.0.1:9052` (healthy, mining enabled)
4. Nautilus wallet extension installed with test ERG (Lithos testnet)
5. Frontend dev server running: `cd frontend && npm run dev`
6. Backend dev server running: `cd backend && python api_server.py`

### Pre-flight Checks

```bash
# Node health
curl -s http://127.0.0.1:9052/info | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Height: {d[\"bestHeight\"]}')"

# Wallet unlocked
curl -s -H "api_key: hello" http://127.0.0.1:9052/wallet/status | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Unlocked: {d[\"isUnlocked\"]}')"

# Contract address configured (grep .env.local)
grep VITE_CONTRACT_P2S_ADDRESS frontend/.env.local

# Frontend builds without errors
cd frontend && npm run build 2>&1 | tail -5
```

## Test Categories

| Category | ID Range | Count |
|----------|----------|-------|
| TC-1xx: Wallet Connection | 100-109 | 10 |
| TC-2xx: Commit (Place Bet) | 200-219 | 20 |
| TC-3xx: Reveal | 300-309 | 10 |
| TC-4xx: Refund | 400-409 | 10 |
| TC-5xx: State Transitions | 500-509 | 10 |
| TC-6xx: Error Cases | 600-619 | 20 |
| TC-7xx: Security | 700-709 | 10 |
| TC-8xx: Edge Cases | 800-809 | 10 |

---

## TC-1xx: Wallet Connection

### TC-101: Connect Nautilus wallet
- **Steps**: Open http://localhost:3000 -> click "Connect Wallet" -> approve in Nautilus
- **Expected**: Wallet address displayed, ERG balance shown, "Connect Wallet" button gone
- **Verify**: `isConnected === true`, `walletAddress` is a valid base58 Ergo address (starts with 3 or 9)
- **Pass criteria**: Address displayed in UI, balance > 0

### TC-102: Disconnect wallet
- **Steps**: Connected -> click disconnect (or Nautilus revoke)
- **Expected**: UI shows "Connect Wallet" prompt, no address/balance shown
- **Pass criteria**: `isConnected === false`, CoinFlipGame shows connect prompt

### TC-103: Reconnect after disconnect
- **Steps**: Disconnect -> click "Connect Wallet" again -> approve
- **Expected**: Same address shown, balance refreshes
- **Pass criteria**: Address matches previous session

### TC-104: Page refresh preserves connection
- **Steps**: Connected -> refresh page (F5)
- **Expected**: Wallet still connected (EIP-12 session persists), address shown
- **Pass criteria**: No need to re-approve in Nautilus

### TC-105: No wallet extension installed
- **Steps**: Disable Nautilus extension -> open page
- **Expected**: "Connect Wallet" button visible but wallet detection fails gracefully
- **Pass criteria**: No console errors, UI degrades gracefully

### TC-106: Wallet with zero ERG balance
- **Steps**: Connect wallet with 0 ERG -> try to place bet
- **Expected**: Can see the game UI, but bet submission should fail with "insufficient balance" error
- **Pass criteria**: Error message displayed, no transaction attempted

### TC-107: getUtxos returns empty array
- **Steps**: Wallet has ERG but no UTXOs (all spent) -> try to place bet
- **Expected**: Error: "No UTXOs available in wallet. Fund your wallet first."
- **Pass criteria**: Error message matches, no signTransaction called

### TC-108: getCurrentHeight fails (node down)
- **Steps**: Stop ergo node -> try to place bet
- **Expected**: Error caught gracefully, "Signing..." spinner stops
- **Pass criteria**: Error displayed, no broken state

### TC-109: getChangeAddress returns null
- **Steps**: Edge case where wallet returns no change address
- **Expected**: Error: "Could not get change address from wallet"
- **Pass criteria**: Error displayed, bet not placed

---

## TC-2xx: Commit (Place Bet) — THE CRITICAL FLOW

### TC-200: Happy path — full on-chain commit
- **Steps**:
  1. Connect wallet
  2. Enter bet amount: 1 ERG
  3. Select "Heads"
  4. Click "Flip!"
  5. **Nautilus popup appears** (sign_tx)
  6. Approve transaction in Nautilus
  7. Transaction broadcasts
- **Expected**:
  - Step 5: Nautilus popup with unsigned tx details (output to P2S address, correct registers)
  - Step 6: Signed transaction returned
  - Step 7: Non-empty txId returned, explorer link shown
  - UI shows "Bet Placed — Awaiting On-Chain Reveal" with txId
- **Verify**:
  ```bash
  # txId should be a valid 64-char hex string
  # Check on explorer: https://explorer.ergoplatform.com/en/transactions/<txId>
  # Check on node: POST /transactions/check (with signed tx)
  ```
- **Pass criteria**: Nautilus popup fires, txId non-empty, explorer shows the tx

### TC-201: signTransaction is called (code path verification)
- **Static analysis** (run before browser test):
  ```bash
  grep -rn 'signTransaction' frontend/src/components/games/CoinFlipGame.tsx
  # MUST return results (line 199)
  grep -rn 'from.*coinflipService' frontend/src/components/games/CoinFlipGame.tsx
  # MUST return results (line 9)
  grep -rn 'Math\.random' frontend/src/components/games/CoinFlipGame.tsx
  # MUST return 0 results
  ```
- **Pass criteria**: All 3 grep checks pass

### TC-202: submitTransaction is called
- **Steps**: Same as TC-200 but reject in Nautilus
- **Expected**: Error "Transaction signing was rejected or failed", no txId
- **Pass criteria**: No broadcast attempted after rejection

### TC-203: Correct register layout in commit box
- **Steps**: Place bet -> get txId -> inspect the output box on the node
- **Expected registers**:
  - R4: Coll[Byte] — house public key (33 bytes)
  - R5: Coll[Byte] — player public key (33 bytes)
  - R6: Coll[Byte] — blake2b256(secret || choice) (32 bytes)
  - R7: Int — 0 (heads) or 1 (tails)
  - R8: Int — timeoutHeight (currentHeight + 100)
  - R9: Coll[Byte] — player secret (8+ bytes)
- **Verify**: `curl http://127.0.0.1:9052/utxo/byBoxId/<boxId>`
- **Pass criteria**: All registers match expected layout

### TC-204: Commitment hash is correct
- **Steps**: After placing bet, extract R6 commitment and verify offline
- **Expected**: `blake2b256(R9_secret ++ R7_choice_byte) == R6_commitment`
- **Verify**: Python or JS script to recompute hash from registers
- **Pass criteria**: Hash matches

### TC-205: Bet amount is correct in output box
- **Steps**: Place bet with 1 ERG -> check output box value
- **Expected**: Box value = 1,000,000,000 nanoERG (exactly)
- **Pass criteria**: Node returns correct value

### TC-206: Heads choice (choice = 0)
- **Steps**: Select Heads, place bet
- **Expected**: R7 register = 0 (Int encoding of 0)
- **Pass criteria**: R7 decodes to 0

### TC-207: Tails choice (choice = 1)
- **Steps**: Select Tails, place bet
- **Expected**: R7 register = 1 (Int encoding of 1)
- **Pass criteria**: R7 decodes to 1

### TC-208: Various bet amounts
- **Sub-cases**:
  - 0.001 ERG (minimum viable, 1M nanoERG)
  - 0.1 ERG
  - 1 ERG
  - 5 ERG
  - 10 ERG
- **Expected**: All produce valid transactions, correct box values
- **Pass criteria**: All amounts work, no validation errors

### TC-209: Quick pick buttons work
- **Steps**: Click "0.1 ERG" quick pick -> amount field shows 0.1
- **Expected**: Input field updates, canSubmit becomes true (with choice selected)
- **Pass criteria**: All 4 quick picks (0.1, 0.5, 1, 5) set correct amounts

### TC-210: Timeout height is set correctly
- **Steps**: Get current height from node -> place bet -> check R8
- **Expected**: R8 = currentHeight + 100 (TIMEOUT_DELTA)
- **Verify**: `curl -s http://127.0.0.1:9052/info | python3 -c "...bestHeight..."`
- **Pass criteria**: R8 is exactly 100 blocks above current height

### TC-211: Change address receives leftover ERG
- **Steps**: Place bet with 2 ERG (from a UTXO with 5 ERG) -> check outputs
- **Expected**: One output is the commit box (2 ERG), another is change (3 ERG - fee)
- **Pass criteria**: Wallet balance decreases by bet amount + fee, not the full UTXO

### TC-212: Payout preview calculation
- **Steps**: Enter 1 ERG -> check "Potential payout" display
- **Expected**: Shows "0.9700 ERG" (1 * 0.97)
- **Pass criteria**: Payout = amount * (1 - HOUSE_EDGE)

### TC-213: Multiple sequential bets
- **Steps**: Place bet #1 -> wait for tx -> place bet #2
- **Expected**: Both bets create separate commit boxes, both txIds are different
- **Pass criteria**: No state leakage between bets

### TC-214: Submit button disabled during signing
- **Steps**: Click "Flip!" -> while Nautilus popup is open
- **Expected**: Button shows "Signing..." and is disabled
- **Pass criteria**: Cannot double-submit

### TC-215: Form reset after successful bet
- **Steps**: Place bet successfully -> check form state
- **Expected**: Amount cleared, choice cleared, error cleared
- **Pass criteria**: Ready for next bet immediately

### TC-216: Non-P2PK wallet (e.g., multisig)
- **Steps**: Connect wallet with non-P2PK UTXO (not starting with 0008cd)
- **Expected**: Error "Could not determine player public key"
- **Pass criteria**: Graceful failure, no broken tx built

### TC-217: On-chain mode disabled (no contract configured)
- **Steps**: Remove VITE_CONTRACT_P2S_ADDRESS from .env -> restart dev server
- **Expected**: Off-chain banner shown, bet goes to backend (no Nautilus popup)
- **Pass criteria**: Falls back to off-chain mode gracefully

### TC-218: Node rejects the transaction
- **Steps**: Build a malformed tx (e.g., register type mismatch) -> submit
- **Expected**: Node returns error, UI shows error message
- **Pass criteria**: Error caught and displayed, not a silent failure

### TC-219: Network timeout during submit
- **Steps**: Place bet -> throttle network to 56kbps -> submit
- **Expected**: Either succeeds slowly or shows timeout error
- **Pass criteria**: No hanging spinner, eventual resolution

---

## TC-3xx: Reveal

### TC-300: House reveals — player wins
- **Steps**:
  1. Player places bet (heads, 1 ERG)
  2. House calls buildRevealTx() with commit box details
  3. House signs and broadcasts reveal tx
- **Expected**:
  - Commit box spent
  - Player receives 1.94 ERG (winPayout = betAmount * 97 / 50)
  - RNG outcome matches on-chain calculation
- **Verify**: `blake2b256(prevBlockHash ++ playerSecret)[0] % 2 == playerChoice`
- **Pass criteria**: Player balance increases by ~1.94 ERG

### TC-301: House reveals — player loses
- **Steps**: Same as TC-300 but RNG lands on wrong side
- **Expected**: House receives betAmount (1 ERG), player gets nothing
- **Pass criteria**: House balance increases, commit box spent

### TC-302: RNG uses block hash (not Math.random)
- **Static analysis**:
  ```bash
  grep -rn 'Math\.random' frontend/src/services/coinflipService.ts
  # MUST return 0 results
  grep -rn 'CONTEXT.preHeader.parentId' smart-contracts/coinflip_v2.es
  # MUST return results
  ```
- **Pass criteria**: RNG comes from on-chain block hash

### TC-303: Reveal verifies commitment on-chain
- **Steps**: Modify R6 (commitment hash) in commit box (impossible on-chain, but test via contract logic)
- **Expected**: Contract rejects reveal if commitment doesn't match
- **Pass criteria**: Contract guard `commitmentOk` must be true

### TC-304: Reveal tx output goes to correct party
- **Steps**: Player wins -> check OUTPUTS(0) of reveal tx
- **Expected**: OUTPUTS(0).propositionBytes == playerProp.propBytes
- **Pass criteria**: On-chain verification via node

### TC-305: Win payout is exactly 1.94x
- **Steps**: Bet 1 ERG -> player wins -> check output value
- **Expected**: OUTPUTS(0).value >= 1,940,000,000 nanoERG (betAmount * 97 / 50)
- **Pass criteria**: Exact on-chain calculation matches

### TC-306: Reveal with NFT in commit box
- **Steps**: Commit box has game NFT -> house reveals
- **Expected**: NFT passes to OUTPUTS(0) (winner gets the NFT)
- **Pass criteria**: NFT not burned during reveal

### TC-307: House has no UTXOs for reveal fee
- **Steps**: Player places bet -> house wallet has 0 UTXOs
- **Expected**: buildRevealTx throws "House wallet has no UTXOs to pay the reveal transaction fee"
- **Pass criteria**: Error caught before building tx

### TC-308: Commit box already spent (double-reveal)
- **Steps**: House reveals -> tries to reveal same box again
- **Expected**: Node rejects second transaction (box already spent)
- **Pass criteria**: No double-payout possible

### TC-309: Reveal before timeout (normal flow)
- **Steps**: Reveal at currentHeight < timeoutHeight
- **Expected**: Reveal path succeeds (canReveal guard passes)
- **Pass criteria**: Transaction accepted by node

---

## TC-4xx: Refund

### TC-400: Player refunds after timeout
- **Steps**:
  1. Player places bet
  2. Wait until HEIGHT >= timeoutHeight (mine 100+ blocks or reduce TIMEOUT_DELTA)
  3. Player calls buildRefundTx() -> signs -> broadcasts
- **Expected**:
  - Commit box spent
  - Player receives refundAmount = betAmount - betAmount/50 (98% of bet)
  - 2% fee burned (goes to miners)
- **Pass criteria**: Player balance increases by ~0.98 ERG (for 1 ERG bet)

### TC-401: Refund before timeout (should fail)
- **Steps**: Try to refund at HEIGHT < timeoutHeight
- **Expected**: Node rejects transaction (contract guard `HEIGHT >= timeoutHeight` fails)
- **Pass criteria**: Transaction not included in any block

### TC-402: Refund amount is exactly 98%
- **Steps**: Bet 1 ERG -> timeout -> refund -> check output
- **Expected**: OUTPUTS(0).value >= 980,000,000 nanoERG (1 ERG - 1/50 ERG)
- **Pass criteria**: Exact calculation: betAmount - betAmount/50

### TC-403: Refund with NFT in commit box
- **Steps**: Timeout with NFT in box -> player refunds
- **Expected**: NFT passes to player's OUTPUTS(0)
- **Pass criteria**: NFT not burned during refund

### TC-404: House tries to refund (should fail)
- **Steps**: House wallet signs refund tx instead of player
- **Expected**: Node rejects (contract requires playerProp, not houseProp)
- **Pass criteria**: Transaction rejected by node

### TC-405: Player refunds with no fee UTXOs
- **Steps**: Player has commit box but no other UTXOs for fee
- **Expected**: buildRefundTx throws "Insufficient UTXOs to pay the refund transaction fee"
- **Pass criteria**: Error before building tx

### TC-406: Refund after reveal (box already spent)
- **Steps**: House reveals -> player tries to refund
- **Expected**: Node rejects (box already spent by reveal)
- **Pass criteria**: No double-spend

### TC-407: Refund is player-initiated (player signs)
- **Steps**: Player calls signTransaction with refund tx
- **Expected**: Nautilus popup fires for player (not house)
- **Pass criteria**: Player wallet signs, not house

### TC-408: Minimum viable bet refund
- **Steps**: Bet 0.001 ERG -> timeout -> refund
- **Expected**: Player gets 0.00098 ERG back (98% of minimum)
- **Pass criteria**: No underflow errors

### TC-409: Large bet refund
- **Steps**: Bet 100 ERG -> timeout -> refund
- **Expected**: Player gets 98 ERG back
- **Pass criteria**: No overflow in BigInt calculation

---

## TC-5xx: State Transitions

### TC-500: Idle -> Committing -> Pending
- **Steps**: Click "Flip!" -> observe state changes
- **Expected**:
  - Idle: form visible, no pending display
  - Committing: "Signing..." button, spinner
  - Pending: "Bet Placed — Awaiting On-Chain Reveal" with bet details
- **Pass criteria**: Clean state transitions, no intermediate broken states

### TC-501: Pending -> Revealed (win)
- **Steps**: Pending bet -> house reveals -> player wins
- **Expected**: Result display shows outcome, "Flip Again" button visible
- **Pass criteria**: Win state with payout amount shown

### TC-502: Pending -> Revealed (loss)
- **Steps**: Pending bet -> house reveals -> player loses
- **Expected**: Result display shows loss, "Flip Again" button visible
- **Pass criteria**: Loss state clearly different from win

### TC-503: Pending -> Refunded
- **Steps**: Pending bet -> timeout -> player refunds
- **Expected**: Shows refund amount received
- **Pass criteria**: Refund state distinct from win/loss

### TC-504: Page refresh during pending state
- **Steps**: Bet placed (pending) -> refresh page
- **Expected**: Bet is on-chain (box exists) but UI state is lost (no localStorage persistence yet)
- **Known limitation**: UI does not persist pending state across refreshes
- **Pass criteria**: No crash on refresh, can place new bet

### TC-505: Error -> Idle recovery
- **Steps**: Trigger error (e.g., reject Nautilus signing) -> try again
- **Expected**: Error message shown, can place new bet after dismissing
- **Pass criteria**: No stuck in error state

### TC-506: Flip Again resets all state
- **Steps**: Win/loss result -> click "Flip Again"
- **Expected**: Amount cleared, choice cleared, result hidden
- **Pass criteria**: Clean slate for next bet

### TC-507: Place Another Bet from pending
- **Steps**: Pending bet -> click "Place Another Bet"
- **Expected**: Returns to form, previous bet still on-chain
- **Pass criteria**: Can place multiple concurrent bets

### TC-508: Concurrent bets (multiple pending)
- **Steps**: Place bet #1 -> Place Another Bet -> Place bet #2
- **Expected**: Two separate commit boxes on-chain, two pending states
- **Pass criteria**: No interference between bets

### TC-509: Off-chain banner visibility
- **Steps**: With/without VITE_CONTRACT_P2S_ADDRESS set
- **Expected**: Banner shown when off-chain, hidden when on-chain
- **Pass criteria**: Correct mode indication

---

## TC-6xx: Error Cases

### TC-600: Nautilus popup rejected
- **Steps**: Click "Flip!" -> reject in Nautilus
- **Expected**: Error "Transaction signing was rejected or failed"
- **Pass criteria**: Error shown, bet not placed, form still populated

### TC-601: Nautilus not installed
- **Steps**: Uninstall Nautilus -> try to connect
- **Expected**: Wallet detection fails, connect button shows error
- **Pass criteria**: Graceful degradation

### TC-602: Node unreachable during commit
- **Steps**: Stop node -> try to place bet
- **Expected**: Error when fetching block height or submitting tx
- **Pass criteria**: Error message, not hanging

### TC-603: Invalid bet amount (0)
- **Steps**: Enter "0" -> try to submit
- **Expected**: Button disabled (canSubmit = false)
- **Pass criteria**: Cannot submit zero bet

### TC-604: Invalid bet amount (negative)
- **Steps**: Enter "-1" -> try to submit
- **Expected**: Input rejected (regex doesn't allow minus)
- **Pass criteria**: Amount field shows empty or error

### TC-605: Invalid bet amount (text)
- **Steps**: Enter "abc" -> try to submit
- **Expected**: Input rejected (regex only allows digits and decimal)
- **Pass criteria**: Only numeric input accepted

### TC-606: Bet exceeds wallet balance
- **Steps**: Enter amount larger than wallet balance -> try to submit
- **Expected**: BoxSelector throws "Insufficient ERG balance" or Nautilus shows insufficient funds
- **Pass criteria**: Clear error about insufficient funds

### TC-607: No choice selected
- **Steps**: Enter amount but don't pick heads/tails -> try to submit
- **Expected**: Button disabled (canSubmit = false, choice === null)
- **Pass criteria**: Cannot submit without choice

### TC-608: Backend /place-bet returns error (off-chain mode)
- **Steps**: Off-chain mode -> backend returns 500
- **Expected**: Error displayed from response body
- **Pass criteria**: Server error message shown

### TC-609: Double-click submit
- **Steps**: Click "Flip!" twice rapidly
- **Expected**: Only one transaction built (isSubmitting guard)
- **Pass criteria**: No duplicate bets

### TC-610: signTransaction returns null
- **Steps**: Wallet returns null from sign_tx
- **Expected**: Error "Transaction signing was rejected or failed"
- **Pass criteria**: Handled like rejection

### TC-611: submitTransaction returns empty string
- **Steps**: Broadcast succeeds but returns empty txId
- **Expected**: Error "Transaction broadcast failed"
- **Pass criteria**: No false positive "success" state

### TC-612: Transaction valid but not included in block (mempool)
- **Steps**: Submit tx -> check mempool before inclusion
- **Expected**: Tx shows as pending in explorer, not confirmed
- **Pass criteria**: Correct pending behavior

### TC-613: Wrong contract address in env
- **Steps**: Set VITE_CONTRACT_P2S_ADDRESS to random address -> try to place bet
- **Expected**: Node may accept but box is locked by wrong contract
- **Pass criteria**: Detected during reveal (commitment verification fails)

### TC-614: Wrong house public key
- **Steps**: Set VITE_HOUSE_PUB_KEY to wrong key -> place bet
- **Expected**: R4 contains wrong key, house cannot reveal
- **Pass criteria**: Reveal fails because houseProp doesn't match

### TC-615: Amount field with excessive decimals
- **Steps**: Enter "0.12345678901234567890"
- **Expected**: Accepted or truncated to nanoERG precision
- **Pass criteria**: No crash, reasonable behavior

### TC-616: Empty amount field
- **Steps**: Leave amount empty -> try to submit
- **Expected**: Button disabled
- **Pass criteria**: canSubmit = false

### TC-617: Commitment verification sanity check fails
- **Steps**: Mock verifyCommitment to return false
- **Expected**: Error "Commitment verification failed — internal error"
- **Pass criteria**: Should never happen in practice, but caught

### TC-618: Explorer link is correct
- **Steps**: Place bet -> click txId link
- **Expected**: Opens explorer.ergoplatform.com with correct txId
- **Pass criteria**: Link format: `https://explorer.ergoplatform.com/en/transactions/<txId>`

### TC-619: Touch gesture bet adjustment (mobile)
- **Steps**: Swipe up/down on bet amount area (mobile viewport)
- **Expected**: Amount increases (swipe up) or decreases (swipe down)
- **Pass criteria**: Gesture recognized within 300ms and 50px threshold

---

## TC-7xx: Security

### TC-700: No Math.random in game flow
- **Static analysis**:
  ```bash
  grep -rn 'Math\.random' frontend/src/components/games/ --include="*.tsx"
  grep -rn 'Math\.random' frontend/src/services/ --include="*.ts"
  grep -rn 'Math\.random' frontend/src/utils/ --include="*.ts"
  ```
- **Pass criteria**: ALL return 0 results

### TC-701: Secret is generated with crypto.getRandomValues
- **Static analysis**:
  ```bash
  grep -rn 'getRandomValues\|crypto\.random' frontend/src/utils/crypto.ts
  ```
- **Pass criteria**: Secret uses CSPRNG, not Math.random

### TC-702: Commitment uses blake2b256 (not SHA-256 or other)
- **Static analysis**: Check CoinFlipGame.tsx generateCommitment() and coinflipService.ts
- **Pass criteria**: blake2b256 used consistently (matches contract)

### TC-703: Secret not sent to backend
- **Static analysis**:
  ```bash
  grep -rn 'secret' frontend/src/components/games/CoinFlipGame.tsx | grep -i 'fetch\|axios\|api'
  ```
- **Pass criteria**: Secret only used client-side, never in API calls

### TC-704: Player choice not sent in cleartext to backend
- **Steps**: Inspect network tab during bet placement (on-chain mode)
- **Expected**: No API call to backend with player choice
- **Pass criteria**: Choice only exists in registers (on-chain), not in backend requests

### TC-705: House cannot fake RNG outcome
- **Analysis**: Review contract — RNG uses CONTEXT.preHeader.parentId which is set by the node at execution time, not by the transaction builder
- **Known risk**: House can choose WHEN to reveal (block hash grinding)
- **Mitigation**: Timeout mechanism limits grinding window
- **Pass criteria**: Documented in ARCHITECTURE.md

### TC-706: Replay attack — same betId
- **Steps**: Submit same betId twice (off-chain mode)
- **Expected**: Backend should reject duplicate betId (409 Conflict)
- **Note**: On-chain mode prevents this naturally (UTXO consumed)
- **Pass criteria**: No duplicate bets possible

### TC-707: Player public key extraction from P2PK UTXO
- **Steps**: Connect wallet -> verify extractPubKeyFromUtxo returns valid 33-byte hex
- **Expected**: 66 hex characters (33 bytes), starts with "02" or "03"
- **Pass criteria**: Valid compressed public key format

### TC-708: Contract ergoTree matches frontend config
- **Steps**: Compare CONTRACT_ERGO_TREE in .env.local with compiled contract
- **Expected**: Exact match
- **Pass criteria**: Frontend and node agree on contract

### TC-709: No hardcoded secrets or keys in frontend JS bundle
- **Static analysis**:
  ```bash
  cd frontend && npm run build
  grep -i 'secret.*=.*['"'']' dist/assets/*.js | grep -v 'playerSecret\|commitment'
  ```
- **Pass criteria**: No secrets or private keys in production bundle

---

## TC-8xx: Edge Cases

### TC-800: Minimum bet (0.001 ERG = 1,000,000 nanoERG)
- **Steps**: Enter 0.001 -> place bet
- **Expected**: Valid transaction, box value = 1,000,000 nanoERG (minimum box value)
- **Pass criteria**: Node accepts minimum box value

### TC-801: Bet amount with many decimal places
- **Steps**: Enter "0.123456789" (9 decimals, exceeds nanoERG precision)
- **Expected**: Truncated to nanoERG precision
- **Pass criteria**: No overflow errors

### TC-802: Very large bet amount
- **Steps**: Enter "10000" (10,000 ERG)
- **Expected**: Either succeeds (if wallet has funds) or "insufficient balance" error
- **Pass criteria**: No integer overflow in BigInt calculations

### TC-803: TIMEOUT_DELTA = 0 (instant refund)
- **Steps**: Set TIMEOUT_DELTA=0 in contract config -> place bet
- **Expected**: Player can refund immediately (HEIGHT >= timeoutHeight)
- **Pass criteria**: Refund works without waiting

### TC-804: TIMEOUT_DELTA = 1000 (very long timeout)
- **Steps**: Set TIMEOUT_DELTA=1000 -> place bet
- **Expected**: Player must wait 1000 blocks for refund
- **Pass criteria**: Timeout height set correctly

### TC-805: Rapid bet placement (5 bets in 10 seconds)
- **Steps**: Place 5 bets quickly (no waiting for reveal)
- **Expected**: All 5 create separate commit boxes
- **Pass criteria**: No rate limiting on bet placement (PoC scope)

### TC-806: Switch between on-chain and off-chain mode
- **Steps**: Place bet on-chain -> disable contract -> reload -> place bet off-chain
- **Expected**: Both modes work, off-chain shows banner
- **Pass criteria**: Clean mode switch

### TC-807: Browser tab backgrounded during signing
- **Steps**: Start signing -> switch to another tab -> come back
- **Expected**: Nautilus popup still visible or error state
- **Pass criteria**: No zombie state

### TC-808: Multiple wallets installed (Nautilus + SAFEW)
- **Steps**: Both extensions installed -> connect Nautilus
- **Expected**: Correct wallet selected, no confusion
- **Pass criteria**: Wallet selection works

### TC-809: Wallet locked (password protected)
- **Steps**: Nautilus is locked -> try to sign
- **Expected**: Nautilus prompts for password before signing
- **Pass criteria**: Signing flow handles locked wallet

---

## Execution Checklist

When MAT-343 is merged and MAT-344 is deployed, run tests in this order:

### Phase 1: Static Analysis (no browser needed)
```
[ ] TC-201: signTransaction grep
[ ] TC-202: SDK import grep
[ ] TC-700: No Math.random
[ ] TC-701: CSPRNG for secrets
[ ] TC-702: blake2b256 usage
[ ] TC-703: Secret not sent to backend
[ ] TC-709: No hardcoded secrets in bundle
```

### Phase 2: Wallet Connection (browser)
```
[ ] TC-101: Connect Nautilus
[ ] TC-102: Disconnect
[ ] TC-103: Reconnect
[ ] TC-104: Page refresh
```

### Phase 3: On-Chain Commit (browser + node)
```
[ ] TC-200: Happy path commit
[ ] TC-203: Register layout verification
[ ] TC-204: Commitment hash verification
[ ] TC-205: Bet amount in box
[ ] TC-210: Timeout height
```

### Phase 4: Reveal (requires house wallet + bot or manual)
```
[ ] TC-300: Player wins
[ ] TC-301: Player loses
[ ] TC-305: Win payout amount
```

### Phase 5: Refund (requires timeout or modified TIMEOUT_DELTA)
```
[ ] TC-400: Player refunds after timeout
[ ] TC-402: Refund amount 98%
```

### Phase 6: Error Cases
```
[ ] TC-600: Nautilus rejection
[ ] TC-603-607: Input validation
[ ] TC-609: Double-click
```

---

## Automation Notes

These tests are designed for manual execution with browser + curl. Future automation could use:

1. **Vitest** for static analysis (grep checks as unit tests)
2. **Playwright** for browser automation (wallet mocking needed)
3. **Python scripts** for node API verification (register checks, box value checks)
4. **Custom Nautilus test fixture** for EIP-12 signing automation

### Example: Automated register check (Python)
```python
import requests, json

NODE = "http://127.0.0.1:9052"
HEADERS = {"api_key": "hello"}

def check_commit_box(box_id):
    box = requests.get(f"{NODE}/utxo/byBoxId/{box_id}").json()
    regs = box.get("additionalRegisters", {})
    
    checks = {
        "R4 (housePk)": bool(regs.get("R4")),
        "R5 (playerPk)": bool(regs.get("R5")),
        "R6 (commitment)": bool(regs.get("R6")),
        "R7 (choice)": bool(regs.get("R7")),
        "R8 (timeout)": bool(regs.get("R8")),
        "R9 (secret)": bool(regs.get("R9")),
    }
    
    for name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    
    return all(checks.values())
```

---

## Blocking Dependencies

| Dependency | Issue | Status |
|-----------|-------|--------|
| Contract compiled + P2S address | MAT-344 | Done |
| SDK wired into CoinFlipGame | MAT-343 | In Progress |
| Frontend build passes | - | Verify |
| House wallet funded with ERG | - | Manual |
| Player wallet funded with test ERG | - | Manual |
| Ergo node mining | - | Verify |

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-29 | QA Tester Jr | Initial test plan (100 test cases) |
