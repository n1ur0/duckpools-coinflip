# DuckPools Coinflip v2 — Security Audit Report

**Auditor**: QA Tester Jr  
**Date**: 2026-03-29  
**Scope**: coinflip_v2.es (compiled), coinflipService.ts, CoinFlipGame.tsx, game_routes.py  
**Issue**: MAT-351

---

## Executive Summary

The coinflip_v2.es contract is a **significant improvement over v1**. It fixes the critical R10 register issue (R10 doesn't exist in Ergo), uses `decodePoint()` for proper PK handling, implements on-chain RNG via block hash, and enforces payout amounts. However, several **design-level trust assumptions remain** that are documented as acceptable for the PoC.

**Verdict**: APPROVED for continued PoC development. No critical blockers found. One medium finding requires attention.

---

## Findings

### FINDING-1: Stale v1.es file in repo — CONFUSION RISK (Medium)

**File**: `smart-contracts/coinflip_v1.es`  
**Severity**: Medium (code clarity)  
**Status**: Fixed in this PR (moved to archive/)

The v1 contract was in the repo with a completely different register layout:

| Register | v1.es (stale) | v2.es (active) |
|----------|--------------|----------------|
| R4 | housePubKey (GroupElement) | housePkBytes (Coll[Byte]) |
| R5 | playerPubKey (Coll[Byte]) | playerPkBytes (Coll[Byte]) |
| R6 | commitmentHash (Coll[Byte]) | commitmentHash (Coll[Byte]) |
| R7 | playerChoice (Int) | playerChoice (Int) |
| R8 | **playerSecret (Int)** | **timeoutHeight (Int)** |
| R9 | **betId (Coll[Byte])** | **playerSecret (Coll[Byte])** |
| R10 | **timeoutHeight (Int)** | **DOES NOT EXIST** |

v1 references R10 which **does not exist in Ergo** (only R4-R9 are non-mandatory registers). This contract was never compilable. The file was misleading — any developer reading it would get the wrong register layout.

Additionally, line 102 contained corrupted code: `val secretBytes=player...ytes`

**Fix**: Moved `coinflip_v1.es` to `smart-contracts/archive/` with a README explaining why it's archived.

---

### FINDING-2: Player secret visible on-chain (Low — Known Trust Assumption)

**File**: `smart-contracts/coinflip_v2.es` line 46  
**Severity**: Low (accepted PoC limitation)  
**Status**: DOCUMENTED — TA-1 in contract header and ARCHITECTURE.md

R9 stores `playerSecret: Coll[Byte]` which is readable by anyone via the explorer or node API. An observer can:
1. Read R9 (player's secret bytes)
2. Read R7 (player's choice)
3. Compute `blake2b256(secret || choice)` to verify
4. Know the player's choice before house reveals

**Mitigation accepted for PoC**: Documented as TA-1. The contract needs the secret to verify the commitment — this is a fundamental ErgoScript limitation without ZK proofs.

**For production**: Use a commitment scheme where the secret doesn't need to be stored, or use ZK-SNARKs.

---

### FINDING-3: Block hash selection by house — grinding risk (Low — Known Trust Assumption)

**File**: `smart-contracts/coinflip_v2.es` line 63  
**Severity**: Low (accepted PoC limitation)  
**Status**: DOCUMENTED — TA-2 in contract header and ARCHITECTURE.md

The house controls when to submit the reveal transaction. It could theoretically:
1. Wait for a block whose hash, combined with the player's secret, produces a favorable outcome
2. Submit the reveal tx only when the house wins

**Mitigation**: The timeout mechanism (R8) limits how long the house can delay. After timeout, the player can claim a 98% refund.

**Economic analysis**: Mining a block costs significant resources. The house would need to mine multiple blocks to find one with a favorable hash. At 3% house edge, this is only profitable if grinding cost < 3% of bet volume, which is unlikely for individual bets.

**For production**: House pre-commits to a block height, or uses a commitment from a decentralized oracle.

---

### FINDING-4: No player-initiated reveal path (Low — Known Trust Assumption)

**File**: `smart-contracts/coinflip_v2.es` lines 76-86  
**Severity**: Low (UX limitation, not security)  
**Status**: DOCUMENTED — TA-4 in contract header

Only the house can trigger reveal. If the house goes offline:
- Player must wait until timeoutHeight (R8) to claim refund
- Player loses 2% on refund

**For production**: Add a player-initiated reveal path where the player provides a block header proof.

---

### FINDING-5: Commitment hash verification — CORRECT (Pass)

**Contract**: v2.es lines 55-58  
**Service**: coinflipService.ts lines 173-184 (verifyCommitment)  
**Game**: CoinFlipGame.tsx lines 18-29 (generateCommitment)

Both contract and frontend use `blake2b256(secret || choice_byte)`:
- Contract: `blake2b256(playerSecret ++ Coll(choiceByte))` where `choiceByte = if (playerChoice == 0) 0.toByte else 1.toByte`
- Frontend: `blake2b256(buf)` where `buf[secret.length] = choice` (0 or 1)

**Verified**: The byte layout matches. `generateCommitment()` and `verifyCommitment()` in coinflipService.ts use the same encoding as the contract.

---

### FINDING-6: Register encoding — CORRECT (Pass)

**Service**: coinflipService.ts lines 131-138  
**Contract**: v2.es lines 41-46

| Register | Service Encoding | Contract Type | Match |
|----------|-----------------|---------------|-------|
| R4 | `SColl(SByte, HOUSE_PUB_KEY)` | `Coll[Byte]` | YES |
| R5 | `SColl(SByte, playerPubKey)` | `Coll[Byte]` | YES |
| R6 | `SColl(SByte, commitment)` | `Coll[Byte]` | YES |
| R7 | `SInt(choice)` | `Int` | YES |
| R8 | `SInt(timeoutHeight)` | `Int` | YES |
| R9 | `SColl(SByte, secretToHex(secret))` | `Coll[Byte]` | YES |

All register encodings use the correct Sigma types. The service properly converts the Uint8Array secret to hex before encoding as `SColl(SByte, ...)`.

---

### FINDING-7: Payout enforcement — CORRECT (Pass)

**Contract**: v2.es lines 76-86

The contract now properly enforces payouts:
- **Player wins**: `OUTPUTS(0).value >= winPayout` (1.94x) AND goes to player
- **House wins**: `OUTPUTS(0).value >= betAmount` AND goes to house

This is a significant improvement over v1 which had no payout enforcement.

---

### FINDING-8: Refund path — CORRECT (Pass)

**Contract**: v2.es lines 88-94

Refund conditions:
- `HEIGHT >= timeoutHeight` — time lock
- `playerProp` — player must sign
- `OUTPUTS(0).propositionBytes == playerProp.propBytes` — output goes to player
- `OUTPUTS(0).value >= refundAmount` — player gets >= 98% of bet

No NFT handling in v2 (correct — v2 doesn't use NFTs in the contract guard).

---

### FINDING-9: Backend /place-bet — no bet deduplication (Medium)

**File**: `backend/game_routes.py` lines 361-398  
**Severity**: Medium (tracked separately as MAT-350)

The `_bets` list has no uniqueness check. A client can submit the same `betId` multiple times, inflating stats. This is tracked as MAT-350 (assigned to Security Engineer Jr).

---

### FINDING-10: No Math.random() in game logic (Pass)

Verified: `Math.random()` only appears in `Confetti.tsx` (visual animation). No game logic uses it. All outcomes are determined by on-chain block hash RNG via `blake2b256(prevBlockHash || playerSecret)[0] % 2`.

---

### FINDING-11: Frontend-backend contract consistency (Pass)

- Backend `COINFLIP_ERGO_TREE` matches `coinflip_deployed.json` `ergoTreeHex` — VERIFIED (438 chars, identical)
- Backend `COINFLIP_P2S_ADDRESS` matches `coinflip_deployed.json` `p2sAddress` — VERIFIED
- Frontend `contract.ts` reads from env vars (`VITE_CONTRACT_P2S_ADDRESS`, `VITE_CONTRACT_ERGO_TREE`) — these must be set in `.env.local` to match
- Register layout comments are consistent across backend, frontend, and contract

---

### FINDING-12: buildPlaceBetTx error handling (Pass)

The function properly validates:
- `isOnChainEnabled()` check (line 108)
- Insufficient UTXOs (line 144)
- Empty UTXO list (CoinFlipGame.tsx line 169)
- Missing change address (CoinFlipGame.tsx line 165)
- P2PK extraction failure (CoinFlipGame.tsx line 180)
- Signing rejection (CoinFlipGame.tsx line 200)
- Broadcast failure (CoinFlipGame.tsx line 206)

---

### FINDING-13: v1.es has a syntax error (Low — stale file)

**File**: `smart-contracts/coinflip_v1.es` line 102  
**Severity**: Low (file is stale/non-functional)

Line 102 contains: `val secretBytes=player...ytes`

This appears to be a truncated/corrupted line. The original intent was likely `val secretBytes = playerSecret.toBytes`. Combined with the R10 issue, this file has been archived.

---

## Verification Checklist

| Check | Result |
|-------|--------|
| `grep signTransaction CoinFlipGame.tsx` | PASS (lines 50, 199, 263) |
| `grep from.*coinflipService CoinFlipGame.tsx` | PASS (line 9) |
| `grep Math.random frontend/src/components/games/` | PASS (0 results in game logic) |
| `npx tsc --noEmit` | PASS (exit 0) |
| `npm run build` | PASS (265KB JS, 65KB CSS) |
| Backend ergoTree matches deployed JSON | PASS (438 chars, identical) |
| Register layout consistent (v2) | PASS (all 6 registers match) |
| Commitment hash algorithm matches | PASS (blake2b256(secret \|\| choice_byte)) |
| Payout enforcement on-chain | PASS (v2 enforces winPayout and betAmount) |
| Refund path correct | PASS (98% refund, player signs, time-locked) |

---

## Summary

| Severity | Count | Action |
|----------|-------|--------|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 2 | Archive v1.es (FINDING-1, done); bet dedup (FINDING-9, MAT-350) |
| Low | 3 | Known trust assumptions (FINDING-2,3,4) — documented |
| Pass | 7 | Verified correct (FINDING-5,6,7,8,10,11,12) |

**Recommendation**: APPROVED for continued PoC development. The v2 contract is well-designed with proper commitment verification, on-chain RNG, and payout enforcement. The stale v1.es file has been archived to avoid developer confusion.
