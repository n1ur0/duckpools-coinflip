# E2E Test Plan: On-Chain Coinflip Bet Flow (MAT-343)

> Prepared by: QA Tester Jr
> Date: 2026-03-29
> Status: READY FOR EXECUTION
> Related Issue: MAT-368

## Prerequisites

| Requirement | How to Verify |
|---|---|
| Ergo node running at 127.0.0.1:9052 | `curl -s http://127.0.0.1:9052/info` → peersCount > 0 |
| Frontend dev server at localhost:3000 | `curl -s http://localhost:3000` → 200 |
| Backend API at localhost:8000 | `curl -s http://localhost:8000/health` → `{"status":"ok"}` |
| Nautilus wallet installed (incognito) | Extension visible in chrome://extensions |
| VITE_CONTRACT_P2S_ADDRESS set in .env.local | Non-empty, starts with "3yNMk" or "2-" |
| VITE_HOUSE_PUB_KEY set in .env.local | 66-char hex string (33-byte compressed PK) |
| Wallet funded with testnet ERG | Balance > 0.01 ERG |

## Architecture Under Test

```
User → CoinFlipGame.tsx
         ↓
    coinflipService.ts (buildPlaceBetTx via Fleet SDK)
         ↓
    useErgoWallet.ts (signTransaction → Nautilus popup)
         ↓
    Nautilus wallet (EIP-12 sign_tx / submit_tx)
         ↓
    Ergo node 127.0.0.1:9052 (broadcast transaction)
         ↓
    Blockchain (commit box locked at P2S address)
```

### Key Code Paths

1. **Commit Flow**: `CoinFlipGame.handleSubmit()` → `buildPlaceBetTx()` → `signTransaction()` → `submitTransaction()`
2. **Off-chain Fallback**: `CoinFlipGame.handleSubmit()` → `fetch('/api/place-bet')` (when `isOnChainEnabled()` is false)
3. **Contract Config**: `frontend/src/config/contract.ts` reads env vars
4. **RNG**: `crypto.getRandomValues()` for secret, `blake2b256(secret || choice)` for commitment

---

## Test Cases

### TC-001: Happy Path — Full On-Chain Commit Flow

**Priority**: P0 (Critical)
**Preconditions**: Wallet connected, funded (>= 0.1 ERG), on-chain mode enabled

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Navigate to `/` | Page loads, no console errors |
| 2 | Click "Connect Wallet" | Nautilus popup appears |
| 3 | Approve connection in Nautilus | Wallet address displayed, balance > 0 |
| 4 | Enter bet amount "0.1" in input | Input shows "0.1", payout preview shows "0.0970 ERG" |
| 5 | Click "Heads" button | Heads button highlighted, error cleared |
| 6 | Click "Flip!" button | Button shows "Signing...", isOnChainEnabled = true |
| 7 | Nautilus sign_tx popup appears | Popup shows transaction details, fee, outputs |
| 8 | Approve transaction in Nautilus | Button returns to "Flip!", pending state appears |
| 9 | Check pending bet UI | Shows betId, amount "0.1 ERG", choice "Heads", commitment hash, txId link |
| 10 | Click txId link | Opens explorer.ergoplatform.com with correct txId |
| 11 | `curl node /utxo/byBoxId/{boxId}` | Box exists at P2S address with correct registers |

**Verification Commands**:
```bash
# Check signTransaction is called
grep -rn 'signTransaction' frontend/src/components/games/CoinFlipGame.tsx
# Expected: 3+ matches

# Check no Math.random (fake RNG)
grep -rn 'Math.random' frontend/src/components/games/CoinFlipGame.tsx
# Expected: 0 matches (only in comments)

# Check SDK/Fleet is imported
grep -rn 'from.*coinflipService\|from.*fleet-sdk' frontend/src/services/coinflipService.ts
# Expected: multiple matches
```

**Pass Criteria**: All 11 steps pass. Real txId returned (not empty string). Box found on-chain.

---

### TC-002: Off-Chain Fallback Mode

**Priority**: P0 (Critical)
**Preconditions**: `VITE_CONTRACT_P2S_ADDRESS` NOT set (or empty)

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Verify .env.local has no P2S_ADDRESS | `isOnChainEnabled()` returns false |
| 2 | Load page | Banner shows "Off-chain mode — contract not yet deployed" |
| 3 | Connect wallet, enter 0.1 ERG, pick Heads | UI accepts input |
| 4 | Click "Flip!" | Button shows "Flipping..." (NOT "Signing...") |
| 5 | No Nautilus popup | `signTransaction` NOT called |
| 6 | Pending state shows | Shows betId, amount, choice. txId field ABSENT. |
| 7 | Note at bottom | Shows warning about off-chain mode |

**Pass Criteria**: No Nautilus popup. Backend /place-bet called. Console shows off-chain warning.

---

### TC-003: Insufficient ERG Balance

**Priority**: P1 (High)
**Preconditions**: Wallet connected with balance < 0.001 ERG

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Connect wallet with near-zero balance | Balance shows correctly |
| 2 | Enter "0.01" ERG, pick Heads, click Flip | On-chain flow starts |
| 3 | Fleet SDK BoxSelector fails | Error message: "Insufficient ERG balance" or "No UTXOs available" |
| 4 | UI state | Returns to input state, error displayed, bet NOT placed |

**Pass Criteria**: Error shown. No transaction created. No pending state.

---

### TC-004: Transaction Rejected by User

**Priority**: P1 (High)
**Preconditions**: Wallet connected, funded, on-chain mode

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Connect, enter 0.1 ERG, pick Heads | Ready to bet |
| 2 | Click "Flip!" | Nautilus popup appears |
| 3 | REJECT transaction in Nautilus | `signTransaction` returns null |
| 4 | UI state | Error: "Transaction signing was rejected or failed" |
| 5 | Retry | Can enter new amount and try again |

**Pass Criteria**: Rejection handled gracefully. No phantom pending state.

---

### TC-005: No UTXOs Available (Empty Wallet)

**Priority**: P1 (High)
**Preconditions**: Wallet connected, balance > 0 but all ERG in a single UTXO that's already committed

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Connect wallet | Address shown |
| 2 | Enter 0.1 ERG, pick Heads, click Flip | Error: "No UTXOs available in wallet. Fund your wallet first." |

**Pass Criteria**: Descriptive error before Nautilus popup.

---

### TC-006: Network Timeout / Node Unreachable

**Priority**: P1 (High)
**Preconditions**: Node at 127.0.0.1:9052 is DOWN

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Stop ergo node | Node unreachable |
| 2 | Connect wallet, place bet | On-chain flow starts |
| 3 | `getCurrentHeight()` or `getUtxos()` fails | Error message shown, no crash |
| 4 | Restart node, retry | Bet succeeds |

**Pass Criteria**: Graceful error handling. No hanging spinner.

---

### TC-007: Invalid Bet Amount — Zero

**Priority**: P1 (High)
**Preconditions**: Wallet connected

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Enter "0" in amount field | Flip button DISABLED |
| 2 | Enter "" (empty) | Flip button DISABLED |
| 3 | Enter "-1" | Input rejects negative (regex blocks it) |

**Pass Criteria**: Flip button never enables for invalid amounts. No submission possible.

---

### TC-008: Invalid Bet Amount — Below Minimum Box Value

**Priority**: P1 (High)
**Preconditions**: Wallet connected, on-chain mode

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Enter "0.0001" ERG (100,000 nanoERG) | Below minimum box value (1,000,000 nanoERG) |
| 2 | Pick Heads, click Flip | Transaction may build but node REJECTS |
| 3 | OR: Fleet SDK catches it | Error about minimum value |

**Pass Criteria**: Error shown. No invalid transaction broadcast.

---

### TC-009: Max Bet Cap (100 ERG)

**Priority**: P2 (Medium)
**Preconditions**: Wallet connected, on-chain mode

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Enter "101" ERG | Above backend max (100 ERG = 100B nanoERG) |
| 2 | Pick Heads, click Flip | On-chain flow may succeed (frontend has no max check) |
| 3 | Backend /place-bet (off-chain) | Rejects: "maximum bet is 100 ERG" |

**NOTE**: Frontend currently has NO max bet validation. Backend validates. This is a gap.

**Pass Criteria**: Backend rejects overbet. Frontend ideally should also validate.

---

### TC-010: Choice Selection Toggle

**Priority**: P2 (Medium)
**Preconditions**: Wallet connected

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Click "Heads" | Heads highlighted, Tails normal |
| 2 | Click "Tails" | Tails highlighted, Heads normal |
| 3 | Click "Tails" again | Tails stays selected (no toggle off) |
| 4 | Can submit with Tails | Yes |

**Pass Criteria**: Selection works. Only one choice active at a time.

---

### TC-011: Quick Pick Amount Buttons

**Priority**: P2 (Medium)
**Preconditions**: Wallet connected

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Click "0.1 ERG" quick pick | Amount field shows "0.1" |
| 2 | Click "5 ERG" quick pick | Amount field shows "5" |
| 3 | Type "2.5" manually | Amount field shows "2.5" |

**Pass Criteria**: Quick picks work. Manual input works. No conflict.

---

### TC-012: Pending Bet State — Place Another Bet

**Priority**: P1 (High)
**Preconditions**: Bet placed, in pending state

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Bet placed, pending UI visible | Shows bet details + txId |
| 2 | Click "Place Another Bet" | Pending UI disappears |
| 3 | Form reset | Amount empty, choice null |
| 4 | Can place new bet | Yes, normal flow |

**Pass Criteria**: Clean reset. No stale state from previous bet.

---

### TC-013: Pending Bet State — Result After Reveal

**Priority**: P0 (Critical)
**Preconditions**: Bet placed on-chain, house reveals

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Bet pending on-chain | Commit box exists at P2S |
| 2 | House reveal bot processes bet | Commit box spent, payout box created |
| 3 | Frontend detects reveal (polling/WebSocket) | Pending state → result state |
| 4 | Win: shows "YOU WIN!", payout amount | Correct payout (bet * 0.97) |
| 5 | Loss: shows "YOU LOSE" | No payout |
| 6 | "Flip Again" button | Resets to initial state |

**NOTE**: Reveal bot (MAT-358) may not be implemented yet. This test may be blocked.

**Pass Criteria**: Correct win/loss determination. No Math.random involved.

---

### TC-014: Commitment Hash Verification

**Priority**: P0 (Critical)
**Preconditions**: On-chain mode enabled

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Place bet, get commitment hash | 64-char hex string |
| 2 | Extract secret and choice from console | `[CoinFlip] secret=...` |
| 3 | Verify: `blake2b256(secret || choice) == commitment` | MUST match |
| 4 | Check on-chain R6 register | R6 == commitment hash |
| 5 | Check on-chain R9 register | R9 == secret bytes |
| 6 | Check on-chain R7 register | R7 == choice (0 or 1) |

**Verification Commands**:
```bash
# After placing a bet, find the commit box
curl -s "http://127.0.0.1:9052/utxo/boxes/unspent/{ergoTree}?limit=5" | python3 -m json.tool

# Check a specific box
curl -s "http://127.0.0.1:9052/utxo/byBoxId/{boxId}" | python3 -m json.tool
```

**Pass Criteria**: All registers match. Commitment is cryptographically valid.

---

### TC-015: Register Layout Contract Compatibility

**Priority**: P0 (Critical)
**Preconditions**: Commit box exists on-chain

| Register | Expected Type | Expected Content |
|----------|---------------|------------------|
| R4 | Coll[Byte] | House compressed public key (33 bytes) |
| R5 | Coll[Byte] | Player compressed public key (33 bytes) |
| R6 | Coll[Byte] | blake2b256(secret \|\| choice) (32 bytes) |
| R7 | Int | Player choice: 0 or 1 |
| R8 | Int | Timeout height (current + 100) |
| R9 | Coll[Byte] | Player secret (8 bytes raw) |

**How to verify**:
1. Get box from node API
2. Decode Sigma type constants (R4/R5/R6/R9 start with `0e` for Coll[Byte], R7/R8 start with `04` for Int)
3. Verify lengths match expected

**Pass Criteria**: All registers match the layout defined in `coinflip_v2.es` and `coinflipService.ts`.

---

### TC-016: Wallet Disconnect During Bet

**Priority**: P2 (Medium)
**Preconditions**: Wallet connected

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Connect wallet, enter amount, pick choice | Ready to bet |
| 2 | Disconnect wallet (extension) | UI shows "Connect Wallet" prompt |
| 3 | Flip button | DISABLED (isConnected = false) |

**Pass Criteria**: Cannot place bet without wallet. No crash.

---

### TC-017: Session Persistence (Page Refresh)

**Priority**: P2 (Medium)
**Preconditions**: Wallet connected

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Connect wallet | Address shown |
| 2 | Refresh page (F5) | Wallet auto-reconnects (session persistence) |
| 3 | Address and balance shown | Same as before refresh |
| 4 | Can place bet | Yes |

**Pass Criteria**: Session persists across refresh. No re-approval needed.

---

### TC-018: Swipe Gesture Bet Adjustment (Mobile)

**Priority**: P2 (Medium)
**Preconditions**: Mobile viewport (375x667)

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Set viewport to 375x667 | Mobile layout |
| 2 | Swipe up on amount area | Amount increases (x1.5) |
| 3 | Swipe down on amount area | Amount decreases (x0.667) |
| 4 | Quick swipe (< 300ms) | Triggers adjustment |
| 5 | Slow drag (> 300ms) | No adjustment (scroll instead) |

**Pass Criteria**: Gesture works on mobile. Desktop unaffected.

---

### TC-019: Non-P2PK UTXO (Cannot Extract Public Key)

**Priority**: P2 (Medium)
**Preconditions**: Wallet connected, first UTXO is P2S (not P2PK)

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Wallet has only P2S UTXOs | ergoTree doesn't start with "0008cd" |
| 2 | Try to place bet | Error: "Could not determine player public key" |

**Pass Criteria**: Graceful error. Explains the issue.

---

### TC-020: Backend API — /place-bet Validation

**Priority**: P1 (High)
**Preconditions**: Backend running

| Test | Request | Expected |
|------|---------|----------|
| Valid bet | `{address: "3W...", amount: "100000000", choice: 0, commitment: "64hex...", betId: "uuid"}` | 200, success=true |
| Invalid address | `{address: "bad", ...}` | 422, validation error |
| Zero amount | `{..., amount: "0"}` | 422, "amount must be positive" |
| Below min | `{..., amount: "500000"}` | 422, "minimum bet is 0.001 ERG" |
| Above max | `{..., amount: "200000000000"}` | 422, "maximum bet is 100 ERG" |
| Invalid choice | `{..., choice: 2}` | 422, "choice must be 0 or 1" |
| Bad commitment | `{..., commitment: "xyz"}` | 422, "must be valid hex" |
| Short commitment | `{..., commitment: "abc123"}` | 422, "must be 64-character hex" |

**Pass Criteria**: All validation rules enforced.

---

### TC-021: Backend API — /history/{address}

**Priority**: P2 (Medium)
**Preconditions**: At least one bet placed

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | `GET /history/3W...` | Returns array of bets for that address |
| 2 | `GET /history/nonexistent` | Returns empty array |
| 3 | Each bet has betId, playerAddress, choice, amount | All fields populated |

**Known Bug (MAT-167)**: History may show all bets as pending with empty playerAddress.

---

### TC-022: Contract Info Endpoint

**Priority**: P1 (High)
**Preconditions**: Backend running

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | `GET /contract-info` | Returns P2S address, ergoTree, register layout |
| 2 | P2S address matches .env.local | VITE_CONTRACT_P2S_ADDRESS == response.p2sAddress |
| 3 | ErgoTree matches .env.local | VITE_CONTRACT_ERGO_TREE == response.ergoTree |

**Pass Criteria**: Contract info consistent between frontend env and backend.

---

### TC-023: Node Health Check

**Priority**: P1 (High)

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | `GET http://127.0.0.1:9052/info` | Returns node info |
| 2 | `peersCount` > 0 | Node has peers |
| 3 | `fullHeight` is a number | Blockchain syncing |

---

## Regression Checklist (Run After Every Merge to Main)

```bash
# 1. Build passes
cd frontend && npm run build

# 2. No fake RNG
grep -rn 'Math.random' frontend/src/components/games/ --include="*.tsx" | grep -v '//\|comment'
# Expected: 0 results

# 3. signTransaction wired
grep -rn 'signTransaction' frontend/src/components/games/CoinFlipGame.tsx
# Expected: 3+ results

# 4. SDK/Fleet imported
grep -rn 'from.*coinflipService\|from.*fleet-sdk' frontend/src/services/coinflipService.ts
# Expected: multiple matches

# 5. Contract config consistent
# Compare P2S_ADDRESS in .env.local with backend COINFLIP_P2S_ADDRESS

# 6. No dead code imports from old sdk/
grep -rn 'from.*sdk/' frontend/src/ --include="*.ts" --include="*.tsx"
# Expected: 0 results (or only fleet-sdk)
```

---

## Test Execution Log Template

```
TC-XXX | PASS/FAIL | Date | Tester | Notes
-------|-----------|------|--------|------
TC-001 |           |      |        |
TC-002 |           |      |        |
...
```

---

## Blocked Tests

| Test | Blocker | Issue |
|------|---------|-------|
| TC-013 (Reveal result) | Reveal bot not implemented | MAT-358 |
| TC-014 (On-chain verification) | Needs real bet on testnet | MAT-343 |
| TC-015 (Register verification) | Needs real commit box | MAT-343 |
