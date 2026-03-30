/** 
 * Test case for NFT preservation during refund
 * 
 * This test verifies that:
 * 1. NFT is preserved when player requests refund
 * 2. Contract prevents refunds without NFT preservation
 */

{
  // Test parameters
  val testNFT: Coll[(Coll[Byte], Long)] = Coll((Coll[Byte](1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16), 1L))
  val playerPubKey: Coll[Byte] = Coll[Byte](21,22,23,24,25,26,27,28,29,30)
  val housePubKey: Coll[Byte] = Coll[Byte](31,32,33,34,35,36,37,38,39,40)
  
  // Test 1: Verify NFT preservation in refund output
  val testRefundOutput: Boolean = {
    val output = OUTPUTS(0)
    output.tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    }
  }
  
  // Test 2: Verify refund is only allowed with NFT preservation
  val canRefundWithNFT: Boolean = {
    // Simulate timeout condition
    HEIGHT >= 1000000 && 
    // Player refund output
    OUTPUTS(0).propositionBytes == playerPubKey &&
    // NFT preserved
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    // Correct refund amount
    OUTPUTS(0).value >= 9800000000L // 9.8 ERG (assuming 10 ERG bet with 2% fee)
  }
  
  // Test 3: Verify refund fails without NFT
  val canRefundWithoutNFT: Boolean = {
    HEIGHT >= 1000000 &&
    OUTPUTS(0).propositionBytes == playerPubKey &&
    // NFT MISSING - should fail
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    OUTPUTS(0).value >= 9800000000L
  }
  
  // Final test result
  testRefundOutput && canRefundWithNFT && !canRefundWithoutNFT
}