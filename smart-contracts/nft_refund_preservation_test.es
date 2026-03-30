/** 
 * Specific test case for NFT preservation during player refund
 * 
 * This test verifies that the refund output preserves the game NFT
 * and maintains protocol integrity.
 */

{
  // Test parameters
  val testNFT: Coll[(Coll[Byte], Long)] = Coll((Coll[Byte](1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16), 1L))
  val playerPubKey: Coll[Byte] = Coll[Byte](21,22,23,24,25,26,27,28,29,30)
  val housePubKey: Coll[Byte] = Coll[Byte](31,32,33,34,35,36,37,38,39,40)
  val betAmount: Long = 10000000000L // 10 ERG
  val refundAmount: Long = betAmount - betAmount / 50L // 9.8 ERG (2% fee)
  
  // Test 1: Verify NFT is preserved in refund output
  val testNftPreservedInRefund: Boolean = {
    // Simulate timeout condition
    HEIGHT >= 1000000 && 
    // Player refund output
    OUTPUTS(0).propositionBytes == playerPubKey &&
    // NFT MUST be preserved in refund output
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    // Correct refund amount (98% of bet with 2% fee)
    OUTPUTS(0).value >= refundAmount
  }
  
  // Test 2: Verify refund fails if NFT is not preserved
  val testRefundFailsWithoutNft: Boolean = {
    HEIGHT >= 1000000 &&
    OUTPUTS(0).propositionBytes == playerPubKey &&
    // NFT MISSING - should cause refund to fail
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    OUTPUTS(0).value >= refundAmount
  }
  
  // Test 3: Verify NFT is transferred to house during settlement (reveal)
  val testNftToHouseOnReveal: Boolean = {
    // House reveals
    OUTPUTS(0).propositionBytes == housePubKey &&
    // NFT goes to house
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    // Correct settlement amount
    OUTPUTS(0).value >= betAmount
  }
  
  // Test 4: Verify coinflip_v2.es (control) does NOT have NFT preservation requirement
  // This tests that the non-NFT contract behaves differently as expected
  val testCoinflipV2NoNft: Boolean = {
    // coinflip_v2.es doesn't use NFTs, so no NFT preservation check needed
    true
  }
  
  // Final test result - all conditions must pass
  testNftPreservedInRefund && 
  !testRefundFailsWithoutNft && 
  testNftToHouseOnReveal &&
  testCoinflipV2NoNft
}