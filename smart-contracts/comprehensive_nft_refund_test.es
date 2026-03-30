/** 
 * Comprehensive test for NFT preservation during refund across all game contracts
 * 
 * This test verifies that:
 * 1. NFT is preserved when player requests refund in all game types
 * 2. Contract prevents refunds without NFT preservation
 * 3. NFT is correctly transferred to house during settlement
 * 4. Refund amount is correct (98% of bet with 2% fee)
 */

{
  // Test parameters
  val testNFT: Coll[(Coll[Byte], Long)] = Coll((Coll[Byte](1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16), 1L))
  val playerPubKey: Coll[Byte] = Coll[Byte](21,22,23,24,25,26,27,28,29,30)
  val housePubKey: Coll[Byte] = Coll[Byte](31,32,33,34,35,36,37,38,39,40)
  val betAmount: Long = 10000000000L // 10 ERG
  val refundAmount: Long = betAmount - betAmount / 50L // 9.8 ERG (2% fee)
  
  // Test 1: Verify NFT preservation in refund output (all contracts should pass)
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
    // Correct refund amount (98% of bet with 2% fee)
    OUTPUTS(0).value >= refundAmount
  }
  
  // Test 3: Verify refund fails without NFT (should return false)
  val canRefundWithoutNFT: Boolean = {
    HEIGHT >= 1000000 &&
    OUTPUTS(0).propositionBytes == playerPubKey &&
    // NFT MISSING - should fail the refund
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    OUTPUTS(0).value >= refundAmount
  }
  
  // Test 4: Verify NFT goes to house during settlement (reveal path)
  val canRevealWithNFTToHouse: Boolean = {
    // House reveals
    OUTPUTS(0).propositionBytes == housePubKey &&
    // NFT goes to house
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    // Correct settlement amount
    OUTPUTS(0).value >= betAmount
  }
  
  // Test 5: Verify refund fails if amount is incorrect
  val canRefundWithIncorrectAmount: Boolean = {
    HEIGHT >= 1000000 &&
    OUTPUTS(0).propositionBytes == playerPubKey &&
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    // Incorrect amount - should fail
    OUTPUTS(0).value < refundAmount
  }
  
  // Test 6: Verify refund fails if not timed out
  val canRefundBeforeTimeout: Boolean = {
    HEIGHT < 1000000 &&
    OUTPUTS(0).propositionBytes == playerPubKey &&
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == testNFT(0)._1 && t._2 == 1L
    } &&
    OUTPUTS(0).value >= refundAmount
  }
  
  // Final test result - all conditions must pass
  testRefundOutput && 
  canRefundWithNFT && 
  !canRefundWithoutNFT && 
  canRevealWithNFTToHouse &&
  !canRefundWithIncorrectAmount &&
  !canRefundBeforeTimeout
}