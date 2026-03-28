# DuckPools Dice Game - Smart Contract Specification

> **Version:** 1.0
> **Date:** 2026-03-27
> **Author:** Ergo Specialist (MAT-14)
> **Status:** Design Phase

---

## Overview

The dice game shares the same commit-reveal architecture as coinflip but allows variable probability:
- Player picks a **roll target** (2-98): "I bet the roll will be UNDER this number"
- RNG outcome = `SHA256(blockHash || secret)[0] % 100` (range 0-99)
- Player wins if `rngOutcome < rollTarget`
- Variable house edge: 1%-5% depending on risk level
- Payout multiplier = `(100 / rollTarget) * (1 - houseEdge)`

---

## Contract: PendingDiceBet

### Register Layout

| Register | Type | Content |
|----------|------|---------|
| R4 | Coll[Byte] | Player's ErgoTree (return address on win/refund) |
| R5 | Coll[Byte] | Commitment hash (32 bytes SHA256 of `secret || rollTarget`) |
| R6 | Int | Roll target (2-98) |
| R7 | Long | Player's random secret (8 bytes, big-endian, as i64) |
| R8 | Coll[Byte] | Bet ID (32 bytes) |
| R9 | Int | Timeout height (blocks until refund) |

### Tokens

| Token | Description |
|-------|-------------|
| Dice NFT (singleton, 1 unit) | Identifies this game contract |

### Spending Paths

#### Path 1: Reveal (Settlement)

Conditions:
1. Must include house signature (SigmaProp from game state)
2. Verify commitment: `SHA256(secretBytes ++ rollTarget.toBytes) == R5`
3. Compute RNG: `SHA256(blockId ++ secretBytes)`
4. Extract outcome: `rngHash[0] % 100`
5. If `outcome < R6`: player wins → send `box.value * multiplier` to R4
6. If `outcome >= R6`: house wins → send to house address
7. Multiplier is computed from `R6` (rollTarget) using variable edge formula

#### Path 2: Refund (Timeout)

Conditions:
1. `HEIGHT >= R9` (timeout expired)
2. No house signature needed
3. Send full box value back to R4 (player's ErgoTree)

### Variable House Edge Formula

```
riskFactor = 1 - (rollTarget / 100)   // 0.02 to 0.98
houseEdge  = max(0.01, min(0.05, 0.03 - riskFactor * 0.02))
multiplier = (100 / rollTarget) * (1 - houseEdge)
```

| Roll Target | Risk Factor | House Edge | Multiplier |
|-------------|-------------|------------|------------|
| 5           | 0.95        | 1.0%       | 19.80x     |
| 10          | 0.90        | 1.0%       | 9.90x      |
| 25          | 0.75        | 1.5%       | 3.94x      |
| 50          | 0.50        | 3.0%       | 1.94x      |
| 75          | 0.25        | 4.5%       | 1.28x      |
| 90          | 0.10        | 5.0%       | 1.056x     |
| 95          | 0.05        | 5.0%       | 1.000x     |

### ErgoScript Pseudocode

```
{
  val isValidReveal = {
    // House signature present
    proveDlog(housePubkey) &&

    // Verify commitment: SHA256(secret || rollTarget) == R5
    blake2b256(SELF.R7.toBytes ++ SELF.R6.toBytes) == SELF.R5 &&

    // Compute RNG from block hash and secret
    val rngHash = blake2b256(getVar[Coll[Byte]](0).get ++ SELF.R7.toBytes)
    val outcome = (rngHash(0) % 100).toInt

    // Determine winner
    if (outcome < SELF.R6.toInt) {
      // Player wins: send payout to player
      OUTPUTS(0).proposition == SELF.R4 &&
      OUTPUTS(0).value >= SELF.value * computeMultiplier(SELF.R6.toInt)
    } else {
      // House wins: send to house
      OUTPUTS(0).proposition == houseAddress
    }
  }

  val isTimeoutRefund = {
    HEIGHT >= SELF.R9 &&
    OUTPUTS(0).proposition == SELF.R4 &&
    OUTPUTS(0).value == SELF.value
  }

  isValidReveal || isTimeoutRefund
}
```

---

## Commitment Scheme

### Player (Commit Phase)

```
1. Generate 8-byte random secret
2. Pick rollTarget (2-98)
3. Compute: commitment = SHA256(secret_bytes || rollTarget_byte)
4. Submit: { address, amount, rollTarget, commitment, secret, betId }
```

**Important**: The secret is sent to the backend but NOT stored on-chain in the bet box directly. It goes into R7 as a Long (8-byte big-endian as i64). The commitment in R5 binds both secret and rollTarget.

### House/Off-chain Bot (Reveal Phase)

```
1. Detect PendingDiceBet box with dice NFT
2. Wait for next block (use block hash as entropy)
3. Compute RNG: outcome = SHA256(blockHash_UTF8 || secret_bytes)[0] % 100
4. Determine win: outcome < rollTarget
5. Build settlement transaction with house signature
6. Submit to node
```

### RNG Verification (Player-side)

```
1. Get block hash from the reveal transaction
2. Get player's secret from box registers
3. Compute: SHA256(blockHash || secret)[0] % 100
4. Compare with reported outcome
```

---

## Differences from Coinflip

| Feature | Coinflip | Dice |
|---------|----------|------|
| Player choice | 0 (heads) or 1 (tails) | 2-98 (roll under target) |
| Commitment input | `SHA256(secret || choice)` | `SHA256(secret || rollTarget)` |
| RNG range | `[0] % 2` (0 or 1) | `[0] % 100` (0-99) |
| House edge | Fixed 3% | Variable 1%-5% |
| Payout | Fixed 1.94x | Variable 1.0x - 19.8x |
| NFT | Coinflip NFT | Dice NFT |
| R6 content | Choice (0 or 1) | Roll target (2-98) |

---

## Backend Integration

### Endpoint: `POST /place-bet`

The dice game reuses the existing `/place-bet` endpoint with a `game_type` field:

```json
{
  "address": "3W...",
  "amount": "1000000000",
  "game_type": "dice",
  "roll_target": 50,
  "commitment": "a1b2c3...",
  "secret": "0102030405060708",
  "bet_id": "uuid..."
}
```

### Backend Changes Required

1. **Parse `game_type`** from request body
2. **For dice**: Validate `roll_target` is in [2, 98]
3. **Build PendingDiceBet box** with correct registers:
   - R6 = rollTarget (Int)
   - R5 = commitment (Coll[Byte], 32 bytes)
   - R7 = secret as Long (not Int, to fit 8 bytes)
4. **Use dice NFT** instead of coinflip NFT
5. **Multiplier for payout** computed at reveal time based on R6

### Reveal Transaction

Same as coinflip reveal but:
- Uses `SHA256(blockHash || secret)[0] % 100` for outcome
- Checks `outcome < R6` instead of `outcome == R6`
- Payout amount = `box.value * multiplier(R6)`

---

## Deployment Checklist

- [ ] Mint Dice NFT (1 unit, distinct from coinflip NFT)
- [ ] Deploy PendingDiceBet ErgoTree on testnet
- [ ] Add `DICE_NFT_ID` and `DICE_PENDING_BET_SCRIPT` to backend `.env`
- [ ] Backend: add dice handling to `/place-bet` endpoint
- [ ] Backend: update reveal logic for dice (modulo 100, variable multiplier)
- [ ] Frontend: DiceForm component (DONE - see `DiceForm.tsx`)
- [ ] Frontend: dice utility functions (DONE - see `utils/dice.ts`)
- [ ] Test: 20+ successful test bets across different roll targets
- [ ] Test: verify provably-fair verification works for dice
- [ ] Test: verify variable house edge math matches contract
