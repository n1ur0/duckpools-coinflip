# Phase 2 — Smart Contract Architecture Decision Record

**Issue:** 76e4dc09-c0b2-434a-8211-f17b45c476d7
**Author:** DeFi Architect Sr
**Date:** 2026-03-30
**Status:** IMPLEMENTED

---

## Summary

Canonical contract for Phase 2 is **`coinflip_v2_final.es`**. All other versions
are deprecated or have critical defects.

## Contract Version Audit

| Version | File | Status | Issues |
|---------|------|--------|--------|
| v1 | `coinflip_v1.es` | **DEPRECATED** | Truncated ErgoScript (`fromSe....get`), broken NFT token logic, player secret as `R8[Int]` instead of `R9[Coll[Byte]]`, bloat on-chain statistical tests that can't work |
| v2 | `coinflip_v2.es` | **STABLE** | Clean, compiles, deployed. Minor: sparse documentation |
| v3 | `coinflip_v3.es` | **BROKEN** | Uses invalid ErgoScript syntax (`CONTEXT HEIGHT rngBlockHeight`) — will not compile |
| commit_reveal | `coinflip_commit_reveal.es` | **STABLE** | Equivalent to v2, slightly different structure |
| **v2-final** | `coinflip_v2_final.es` | **CANONICAL** | v2 with full documentation, security notes, register layout spec |

## Canonical Contract: coinflip_v2_final.es

### Protocol Flow
```
1. PLAYER COMMITS
   Frontend: secret = random 8 bytes
   Frontend: commitment = blake2b256(secret || choice_byte)
   Frontend -> Backend: { commitment, choice, secret, betAmount, address }
   Backend -> On-chain: Creates PendingBetBox with contract + R4-R9

2. HOUSE REVEALS
   Backend: Observes new PendingBetBox via node API
   Backend: Fetches CONTEXT.preHeader.parentId (block hash)
   Backend: Computes RNG = blake2b256(blockId || secret)[0] % 2
   Backend: Builds reveal tx, signs with house key, broadcasts

3. PAYOUT
   Player wins: OUTPUTS(0) -> player with >= 1.94x bet
   House wins:  OUTPUTS(0) -> house with >= 1.0x bet

4. REFUND (timeout)
   HEIGHT >= timeoutHeight: Player spends box, gets >= 0.98x bet
```

### Register Layout (R4-R9)
```
R4: Coll[Byte] — house compressed PK (33 bytes)
R5: Coll[Byte] — player compressed PK (33 bytes)
R6: Coll[Byte] — blake2b256(secret || choice_byte) (32 bytes)
R7: Int        — player choice: 0=heads, 1=tails
R8: Int        — timeout block height (refund after this)
R9: Coll[Byte] — player secret (8 random bytes)
```

### Economics
- House edge: 3% (player gets 1.94x on win, not 2x)
- Refund fee: 2% (player gets 0.98x on timeout, prevents spam)
- Timeout: 100 blocks (~200 min on Ergo)

### Security Model (PoC)
| Trust | Risk | Mitigation |
|-------|------|------------|
| TA-1: Player secret visible on-chain (R9) | House can peek at choice before reveal | Honest house assumption; production: ZK proofs |
| TA-2: House selects reveal block (grinding) | House could wait for favorable block hash | Timeout mechanism limits delay window |
| TA-3: Only house can reveal | Player stuck if house offline | Refund path after timeout |
| TA-4: No payout amount upper bound enforcement | House could overpay (no risk to player) | Not a player risk; house self-interest |

## Fixes Applied

### 1. Contract Compilation (Task 2.1)
- **Problem:** v1 has truncated ErgoScript, v3 uses invalid syntax
- **Solution:** v2-final is the canonical contract. Already compiles on ergo-6.0.3 Lithos testnet.
- **Deployed:** P2S address in `coinflip_deployed.json` (from v2 compilation)

### 2. Commit-Reveal Implementation (Task 2.2)
- **Problem:** v1 used `Math.random` (off-chain only), stored secret as Int
- **Solution:** v2-final uses `blake2b256(CONTEXT.preHeader.parentId ++ playerSecret)` for on-chain RNG
- **No Math.random:** Verified by contract structure test

### 3. NFT Preservation on Refund (Task 2.3)
- **Problem:** v1 used NFT tokens for game identification, complex refund logic
- **Solution:** v2-final uses pure PK-based authentication (proveDlog), no NFT tokens needed
- **Impact:** NFT preservation is a non-issue in v2 since there are no NFTs

### 4. Unit Tests (Task 2.5)
- **42 contract tests** in `tests/test_coinflip_contract.py`:
  - Commitment scheme (12 tests): generation, verification, binding, blake2b256
  - RNG computation (6 tests): binary output, determinism, uniformity, blake2b256 match
  - Payout math (5 tests): 1.94x win, 3% edge, 98% refund, edge cases
  - Contract structure (11 tests): register layout, spending paths, no Math.random
  - Edge cases (7 tests): zero secret, 0xFF secret, invalid inputs
  - Integration (2 tests): full commit-reveal cycle

- **12 fairness tests** in `tests/test_rng_fairness.py`:
  - Uniformity (4 tests): 100k samples, chi-square, fixed/varying inputs
  - Entropy (2 tests): Shannon entropy 1-bit and 8-bit
  - Runs test (1 test): no extreme streaks
  - Serial correlation (1 test): no autocorrelation
  - Commitment binding (2 tests): no preimage attacks
  - Determinism (2 tests): known vectors, reproducibility

### 5. RNG Fairness Verification (Task 2.6)
- Backend module `rng_module.py` fixed (3 truncated lines)
- Contract verification function updated to validate v2 register layout
- Statistical test suite: chi-square, Shannon entropy, runs, autocorrelation

## Files Changed
```
NEW:  smart-contracts/coinflip_v2_final.es     (canonical contract)
FIX:  backend/rng_module.py                     (3 syntax fixes + verify function rewrite)
NEW:  tests/test_coinflip_contract.py           (42 tests)
NEW:  tests/test_rng_fairness.py                (12 tests)
```

## Integration Notes for Downstream

- **Backend Engineer:** `game_routes.py` already references v2 P2S address — no changes needed
- **Frontend Engineer:** Register layout R4-R9 documented above. Commit = blake2b256(secret || choice_byte)
- **LP Contract Developer Jr:** v2-final is the contract to deploy. Use existing deploy script.
- **Security Auditor Sr:** RNG fairness verified: chi-square p>0.01, entropy>0.999, no autocorrelation
