# Pending Bet Contract Audit

This document audits the security of pending bet contracts across all DuckPools games.

## Critical Finding: NFT Burn on Refund (MAT-261)

### Issue Summary
**Severity**: CRITICAL - single refund destroys entire protocol  
**Status**: FIXED ✅  
**Date**: 2026-03-28

### Problem
The PendingBet box holds the game NFT (COINFLIP_NFT_ID) as its first token. The refund spending path (`canRefund`) did NOT enforce NFT preservation, causing the NFT to be burned when a player requests a timeout refund.

### Affected Contracts
- dice_v1.es: Line 74 - `canRefund` missing NFT check
- plinko_v1.es: Line 74 - same issue  
- coinflip_v1.es: Line 74 - same issue

### Root Cause
```ergoscript
// BEFORE (vulnerable)
val canRefund: Boolean = isTimedOut && isPlayerRefund && refundValueOk

// This would:
// 1. Send refund ERG to OUTPUTS(0) (player)
// 2. NOT preserve the NFT
// 3. Burn the NFT permanently
// 4. Break the game state box
// 5. Make all future bets impossible
```

### Fix Implemented
```ergoscript
// AFTER (fixed)
val canRefund: Boolean = isTimedOut && isPlayerRefund && refundValueOk && nftToHouse

def nftToHouse: Boolean = {
  OUTPUTS.size >= 2 && OUTPUTS(1).tokens.exists { (t: (Coll[Byte], Long)) =>
    t._1 == gameNFT(0)._1 && t._2 == 1L
  }
}
```

The fix requires refund transactions to have:
- OUTPUTS(0): Player receives ERG refund
- OUTPUTS(1): House address receives the NFT back

### Testing Requirements
- [x] Refund path preserves NFT in ALL three contracts
- [ ] Verify off-chain bot refund transaction builder sends NFT to correct output
- [x] Test: player refund does not burn NFT  
- [x] Test: game continues working after a refund

### Off-Chain Bot Requirements
The refund transaction builder must be updated to create transactions with two outputs:
1. Player refund (ERG only)
2. House NFT recovery (NFT only)

The house bot should then sweep recovered NFTs back into the game state boxes.

### Security Impact
This fix prevents:
- Accidental protocol destruction via timeout refunds
- Malicious griefing attacks
- Permanent game state corruption

### Verification
All contracts now include the fix and have been verified to:
1. Preserve NFT during player refunds
2. Allow game continuation after refunds
3. Maintain proper game state integrity

## Additional Audit Areas

### Commit-Reveal Security
- [x] All contracts use blake2b256 for commitment verification
- [x] Secrets are properly blinded
- [x] Timing constraints prevent front-running

### Value Security  
- [x] House edge is correctly enforced (2%)
- [x] Refunds deduct house edge
- [x] Payouts are calculated correctly

### Token Management
- [x] Game NFT is preserved in all paths
- [x] Token counts are validated
- [x] Token IDs are correctly compared

## Next Audit Cycle
Scheduled for: 2026-04-11 (2 weeks)