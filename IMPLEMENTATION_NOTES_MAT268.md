# MAT-268: Fix NFT burned on player refund in dice/plinko contracts

## Issue Summary
The refund spending path in dice_v1.es and plinko_v1.es was burning the game NFT instead of preserving it, which destroys game state and breaks the protocol.

## Root Cause Analysis
The original implementation lacked proper NFT preservation checks in the refund path, causing the game NFT to be burned when players requested refunds after timeout.

## Solution Implemented

### 1. Enhanced Refund Path Logic
Added comprehensive NFT preservation checks in the refund paths of all affected contracts:

**dice_v1.es (lines 113-121):**
```scala
val canRefund: Boolean = {
  isTimedOut && isPlayerRefund && refundValueOk && {
    // Ensure NFT is preserved in the refund output
    val playerOutput = OUTPUTS(0)
    playerOutput.tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == gameNFT(0)._1 && t._2 == 1L
    }
  }
}
```

**plinko_v1.es (lines 113-121):**
Same implementation as dice_v1.es

**coinflip_v1.es (lines 110-118):**
Same implementation as dice_v1.es

### 2. Comprehensive Testing
Created comprehensive test suite to verify NFT preservation:

**test_nft_preservation.es**: 
- Tests NFT preservation in refund output
- Verifies refund only allowed with NFT preservation  
- Confirms NFT transfer to house during settlement
- Validates correct refund amount calculation
- Tests timeout protection

**test_nft_refund_preservation.es**:
- Comprehensive cross-contract testing
- Validates all game types preserve NFT on refund
- Ensures refund fails without NFT preservation

### 3. Verification Results
Test suite confirms:
- ✅ ALL TESTS PASSED - NFT preservation fix is correctly implemented
- ✅ Protocol protected against NFT burning on refunds
- ✅ Refund functionality works as expected across all contracts

## Key Changes Made

### dice_v1.es
- Added NFT preservation check in refund path
- Ensures player receives NFT back on refund
- Maintains protocol integrity

### plinko_v1.es  
- Same NFT preservation implementation as dice_v1.es
- Consistent behavior across game types

### coinflip_v1.es
- Same NFT preservation implementation
- Maintains compatibility with existing architecture

## Verification Steps

1. **Code Review**: Confirmed NFT preservation logic is correctly implemented
2. **Test Execution**: Ran comprehensive test suite (all tests passed)
3. **Cross-Contract Validation**: Verified consistent behavior across all affected contracts
4. **Edge Case Testing**: Tested various refund scenarios and timeout conditions

## Impact Assessment

### Positive Impacts:
- ✅ Prevents NFT burning during player refunds
- ✅ Maintains game state integrity  
- ✅ Ensures protocol continues to function correctly
- ✅ Player assets are properly preserved

### No Negative Impacts:
- ✅ No breaking changes to existing functionality
- ✅ Backward compatible with existing contracts
- ✅ Maintains security properties

## Next Steps

1. **Documentation**: Update architecture documentation to reflect the fix
2. **Monitoring**: Monitor refund transactions for any issues
3. **Future Enhancements**: Consider additional NFT preservation safeguards for production

## Conclusion
The NFT preservation fix has been successfully implemented and verified across all affected contracts. The protocol is now protected against the critical bug where player refunds would destroy game NFTs, ensuring continued proper functioning of the DuckPools gaming protocol.