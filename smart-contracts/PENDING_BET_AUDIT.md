# PendingBet Contract Security Audit

## Critical Finding: NFT Burned on Player Refund (MAT-261)

**Severity**: CRITICAL - single refund destroys entire protocol  
**Status**: FIXED  
**Components**: coinflip_v1.es, dice_v1.es, plinko_v1.es

### Problem Description

The PendingBet box holds the game NFT (COINFLIP_NFT_ID, DICE_NFT_ID, or PLINKO_NFT_ID) as its first token. The refund spending path (`canRefund`) did NOT enforce NFT preservation, which would cause the NFT to be burned when a player refunds.

### Root Cause

In the original contracts:

```ergoscript
// Original vulnerable code:
val canRefund = isTimedOut && isPlayerRefund && refundValueOk
```

The reveal path had `nftPreserved`, but the refund path did NOT. When a player refunds:
1. OUTPUTS(0) = player address with ERG value (no NFT token)
2. No output was constrained to hold the NFT
3. NFT would be BURNED (destroyed)
4. Game state box becomes invalid (references burned NFT)
5. ALL future bets become impossible

### Impact

- Any single player refund would permanently kill the protocol
- The timeout refund path was designed as a player safety mechanism, but it was actually a griefing vector
- On testnet this would be an inconvenience; on mainnet this would be catastrophic

### Fix Implemented

Added NFT preservation check to the refund path in all three contracts:

```ergoscript
// Fixed code:
val canRefund = isTimedOut && isPlayerRefund && refundValueOk && nftPreserved
```

Where `nftPreserved` is defined as:

```ergoscript
val nftPreserved = OUTPUTS.exists { (output: Box) =>
  output.tokens.exists { (token: (Coll[Byte], Long)) =>
    token._1 == nftId && token._2 == 1L
  }
}
```

This requires the refund transaction to preserve the NFT in one of the outputs.

### Alternative Solutions Considered

1. **House-controlled NFT output**: More complex, requires second output specifically for house to receive NFT
2. **Player preserves NFT**: Simpler, forces player to include NFT in their refund output

We chose option 2 (player preserves NFT) because:
- Fewer transaction outputs required
- Simpler contract logic
- Less room for implementation errors
- Player can always spend the NFT back to the house later

### Verification

To verify the fix:

1. **Contract deployment**: All three contracts now include `&& nftPreserved` in `canRefund`
2. **Transaction building**: Off-chain bot must include NFT in refund transaction outputs
3. **Testing**: Player refund does not burn NFT
4. **Integration**: Game continues working after a refund

### Files Modified

- `smart-contracts/contracts/coinflip_v1.es` - Added NFT preservation to refund path
- `smart-contracts/contracts/dice_v1.es` - Added NFT preservation to refund path
- `smart-contracts/contracts/plinko_v1.es` - Added NFT preservation to refund path

### Testing Checklist

- [ ] Refund transaction preserves NFT in all three contracts
- [ ] Player receives correct ERG refund amount
- [ ] Game remains operational after refund (NFT not burned)
- [ ] Timeout logic still works correctly
- [ ] House reveal path unaffected by changes
- [ ] Integration test: full bet → refund → new bet cycle

### Security Considerations

1. **Player UX**: Players must now include the NFT in their refund output, which requires proper wallet support
2. **Gas costs**: Additional output may slightly increase transaction fees
3. **Compatibility**: This change is backwards compatible with existing reveal logic

### Recommendation

This fix should be deployed immediately as it prevents a critical vulnerability that could destroy the protocol. The fix is minimal and low-risk, addressing the core issue without changing the fundamental game mechanics.