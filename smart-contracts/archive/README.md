# Archived Contracts

This directory contains deprecated contract versions that are NO LONGER ACTIVE.

## coinflip_v1.es — ARCHIVED 2026-03-29

**Reason**: Uncompilable and superseded by coinflip_v2.es.

### Why it was archived:
1. **R10 register**: v1 references `R10[Int]` for timeoutHeight. Ergo only supports R4-R9 as non-mandatory registers. R10 does not exist.
2. **Wrong register layout**: R8 was used for playerSecret (Int type), R9 for betId. The v2 layout corrects this: R8=timeoutHeight, R9=playerSecret.
3. **PK type mismatch**: R4 used `GroupElement` directly instead of `Coll[Byte]` with `decodePoint()`. This requires the house PK to be passed as a SigmaProp constant rather than raw bytes.
4. **Corrupted line 102**: `val secretBytes=player...ytes` — truncated/corrupted code.
5. **No on-chain RNG**: v1 had no block hash-based RNG. The outcome determination was left to the spending transaction.
6. **No payout enforcement**: v1 only checked that OUTPUTS(0) went to the player, but not how much ERG.

### Active contract:
See `../coinflip_v2.es` — compiled 2026-03-28, deployed to Lithos testnet.

### Audit reference:
- MAT-351: Security audit finding FINDING-1 (stale file confusion risk)
- MAT-348: Player secret visibility (applies to v1 R8 and v2 R9)
- MAT-336: Payout enforcement gap (fixed in v2)
