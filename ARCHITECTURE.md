# DuckPools Coinflip — Architecture & Trust Assumptions

> Protocol design decisions and security playbook for the coinflip PoC.
> Last updated: 2026-03-28

## Overview

DuckPools is a provably-fair coinflip game on Ergo. Players commit a bet
(choice + secret) on-chain, the house reveals after a block-confirmation
delay, and the contract pays the winner atomically.

Two contract versions exist:

| Version | File | Status |
|---------|------|--------|
| v1 | `smart-contracts/coinflip_v1.es` | Superseded |
| v2 | `smart-contracts/coinflip_v2.es` | Active |

v2 is the current contract. It adds on-chain block-hash RNG, deterministic
payout enforcement, and compressed-PK encoding (R4/R5 as `Coll[Byte]`).

---

## Trust Assumptions (PoC)

These are the known trust assumptions for the current protocol design.
Each one is a trade-off between simplicity (PoC scope) and security
(production requirements).

### TA-1: Player secret is visible on-chain

**Severity:** MEDIUM  
**Contracts:** v1 (R8=Int), v2 (R9=Coll[Byte])

The commit-reveal scheme requires the player's secret to be stored in the
box registers so the contract can verify the commitment during reveal.
This means **any blockchain observer can read the player's secret and
choice immediately after the commit transaction is confirmed**.

**Impact:**
- A front-running observer knows the player's choice before the house reveals.
- The house itself learns the player's choice when it reads the box.
- This does NOT allow the house to change the outcome (see TA-2), but it
  breaks the traditional "secret until reveal" guarantee.

**Why it's accepted for PoC:**
- ErgoScript cannot perform ZK proofs or hash pre-image checks without
  revealing the pre-image.
- The on-chain RNG (block hash) still provides outcome fairness — knowing
  the player's choice does not help predict the flip result.

**Production fix:** Use a ZK-SNARK circuit where the player proves
knowledge of `(secret, choice)` matching the commitment hash without
revealing either value. The contract would verify the proof instead of
re-reading the secret.

### TA-2: House selects the reveal block (block-hash grinding risk)

**Severity:** HIGH  
**Contracts:** v1 (no RNG), v2 (uses `CONTEXT.preHeader.parentId`)

v2 determines the coinflip outcome using:
```
blake2b256(CONTEXT.preHeader.parentId ++ playerSecret)[0] % 2
```

The house builds the reveal transaction and decides when to submit it.
Since `preHeader.parentId` depends on the block that includes the tx,
the house could theoretically:
1. Wait for a block whose hash produces a favorable outcome.
2. Submit the reveal tx only in that block.
3. Discard (or let timeout) bets where the outcome is unfavorable.

**Impact:**
- The house could selectively reveal only winning bets, giving itself
  a >50% win rate.
- The player cannot verify that the house didn't cherry-pick blocks.

**Mitigations in v2:**
- The timeout mechanism (R8) limits the house's window — if the house
  doesn't reveal before timeout, the player can refund.
- The payout is enforced on-chain (v2 checks OUTPUTS value), so the
  house cannot underpay on reveal.

**Why it's accepted for PoC:**
- Full mitigation requires a house commitment (the house pre-commits to
  a value before the player reveals), which adds protocol complexity.
- The timeout + on-chain enforcement provides reasonable fairness for
  a testnet PoC.

**Production fix:** Implement a dual commitment scheme:
1. House commits `hash(houseSecret)` before the player bets.
2. Both secrets are revealed, and RNG uses `blake2b256(houseSecret ++ playerSecret ++ blockHash)`.
3. The house cannot grind because it's bound to its pre-committed secret.

### TA-3: No on-chain payout enforcement in v1

**Severity:** HIGH  
**Contracts:** v1 only

v1's reveal path checks that OUTPUTS(0) goes to the player but does NOT
verify the payout amount. A malicious house could reveal with 0 ERG to
the player and pocket the entire bet.

**Fixed in v2:** v2 enforces:
- Player wins: `OUTPUTS(0).value >= betAmount * 97 / 50` (1.94x)
- House wins: `OUTPUTS(0).value >= betAmount`

### TA-4: Only house can reveal — no player-initiated reveal

**Severity:** LOW  
**Contracts:** v1, v2

Both contracts only allow the house (via `houseProp`) to trigger the reveal
path. If the house goes offline, the player must wait for the timeout and
then claim a refund (98% of bet, 2% fee).

**Impact:** UX degradation when house is unavailable, but no loss of funds
(beyond the 2% timeout fee).

**Production fix:** Add a player-initiated reveal path that uses a
trusted oracle or time-locked commitment to determine the outcome.

### TA-5: WebSocket auth is not cryptographically verified

**Severity:** HIGH  
**Backend:** `ws_routes.py`

The WebSocket authentication endpoint accepts any non-empty signature as
valid. An attacker can subscribe to any player's bet events.

**Impact:** Information leakage — real-time bet activity is visible to
unauthenticated observers.

**Mitigation:** WebSocket events currently only contain bet status updates,
not secret data. The secrets are already public on-chain (TA-1).

**Production fix:** Implement SigmaProp signature verification using the
Ergo node API (`/node/signature/{message}`) or Nautilus wallet challenge.

### TA-6: Backend uses in-memory storage (no persistence)

**Severity:** LOW  
**Backend:** `game_routes.py`

Player stats, bet history, and leaderboard data are stored in Python
lists/dicts. All data is lost on server restart.

**Impact:** Historical data loss. No financial impact since on-chain state
is the source of truth.

**Production fix:** PostgreSQL persistence (schema exists in
`migrations/`).

### TA-7: No bet deduplication

**Severity:** MEDIUM  
**Backend:** `game_routes.py`

The same `betId` can be submitted multiple times. Duplicate bets inflate
player stats and leaderboard positions.

**Production fix:** Add `betId` uniqueness check with a Set or database
unique constraint. Return 409 Conflict on duplicates.

---

## RNG Design (v2)

### Formula
```
entropy = blake2b256(CONTEXT.preHeader.parentId ++ playerSecret)
flipResult = entropy[0] % 2
```

### Entropy sources
1. **Block hash** (`preHeader.parentId`): Provides ~256 bits of entropy
   from Proof-of-Work. Unpredictable before the block is mined.
2. **Player secret** (R9, 32 bytes): Provides additional entropy and
   ensures different outcomes for simultaneous bets.

### Limitations
- The house controls WHEN to submit the reveal tx (see TA-2).
- The block hash is only truly random from the miner's perspective; the
  house can observe pending blocks and choose when to submit.
- `entropy[0] % 2` uses only 1 bit of the 256-bit hash, but blake2b's
  output is uniformly distributed so the bias is negligible.

---

## Register Layout (v2)

| Register | Type | Content |
|----------|------|---------|
| R4 | Coll[Byte] | House compressed public key (33 bytes) |
| R5 | Coll[Byte] | Player compressed public key (33 bytes) |
| R6 | Coll[Byte] | Commitment hash: `blake2b256(secret ++ choiceByte)` (32 bytes) |
| R7 | Int | Player choice: 0 = heads, 1 = tails |
| R8 | Int | Timeout height for refund |
| R9 | Coll[Byte] | Player secret (32 random bytes) |

Note: v1 used a different layout with R4=GroupElement, R8=Int(secret),
R9=Coll[Byte](betId), R10=Int(timeout). v2 dropped the betId register
(tracked off-chain only) and changed R8/R9 semantics.

---

## Value Calculations (v2)

| Scenario | Formula | Multiplier |
|----------|---------|------------|
| Player wins | `betAmount * 97 / 50` | 1.94x (3% house edge) |
| Player refund (timeout) | `betAmount - betAmount / 50` | 0.98x (2% timeout fee) |
| House wins | House receives full `betAmount` | 1.0x |

---

## Spending Paths (v2)

### 1. Reveal (house)
- Requires: `houseProp && commitmentOk && correctOutput`
- House signs the transaction (proves ownership of R4 key)
- Contract verifies `blake2b256(R9_secret ++ R7_choiceByte) == R6_commitment`
- Contract checks RNG outcome and validates OUTPUTS(0) goes to the
  correct party with the correct amount

### 2. Refund (player, after timeout)
- Requires: `HEIGHT >= R8_timeout && playerProp && correctRefundOutput`
- Player signs the transaction (proves ownership of R5 key)
- Player receives 98% of bet amount
- NFT (if present) goes to house in OUTPUTS(1)

---

## PoC Scope

What IS in scope:
- Single game: coinflip (heads/tails)
- On-chain commit-reveal with block-hash RNG
- Timeout/refund mechanism
- Backend API for bet tracking, stats, history
- WebSocket for real-time bet events

What is NOT in scope:
- Bankroll management, LP tokens, staking
- Multiple games (dice, plinko, crash)
- Oracle price feeds
- Rate limiting, load testing
- ZK proofs or advanced cryptographic schemes
- Mobile native apps
