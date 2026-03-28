/**
 * DuckPools Dice Game Contract v1
 * 
 * Player commits to a dice roll (1-100), house reveals outcome.
 * Fixed: NFT preservation in refund path to prevent protocol breakage.
 */

{
  // Game parameters
  val housePubKey: GroupElement = fromSelf.R4[GroupElement].get
  
  // Player commitment
  val playerPubKey: Coll[Byte] = fromSelf.R5[Coll[Byte]].get
  val commitmentHash: Coll[Byte] = fromSelf.R6[Coll[Byte]].get
  val chosenNumber: Int = fromSelf.R7[Int].get
  val playerSecret: Int = fromSelf.R8[Int].get
  val betId: Coll[Byte] = fromSelf.R9[Coll[Byte]].get
  
  // Timeout parameters
  val timeoutHeight: Int = fromSelf.R10[Int].get
  
  // Game NFT (first token)
  val gameNFT: Coll[(Coll[Byte], Long)] = fromSelf.tokens
  
  // Helper functions
  def isPlayer(sig: SigmaProp): Boolean = {
    sig.verify(playerPubKey)
  }
  
  def isHouse(sig: SigmaProp): Boolean = {
    sig.verify(housePubKey)
  }
  
  def isTimedOut: Boolean = {
    HEIGHT >= timeoutHeight
  }
  
  def isPlayerRefund: Boolean = {
    OUTPUTS(0).propositionBytes == playerPubKey
  }
  
  def refundValueOk: Boolean = {
    val refundAmount = fromSelf.value - fromSelf.value / 50 // 2% fee
    OUTPUTS(0).value >= refundAmount
  }
  
  def nftPreserved: Boolean = {
    OUTPUTS(0).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == gameNFT(0)._1 && t._2 == 1L
    }
  }
  
  def nftToHouse: Boolean = {
    OUTPUTS.size >= 2 && OUTPUTS(1).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == gameNFT(0)._1 && t._2 == 1L
    }
  }
  
  // Reveal path verification
  def isValidReveal: Boolean = {
    OUTPUTS(0).propositionBytes == fromSelf.R5[Coll[Byte]].get && // Player gets payout
    
    // Verify commitment: blake2b256(secret || choice) matches stored commitment
    // CRITICAL (SEC-CRITICAL-1): MUST use blake2b256 — the native Ergo hash opcode.
    // SHA-256 would cause every reveal to fail on-chain.
    val secretBytes = playerSecret.toBytes
    val choiceBytes = chosenNumber.toBytes
    val computedHash = blake2b256(secretBytes ++ choiceBytes)
    computedHash == commitmentHash
  }
  
  // Spending conditions
  val canReveal: Boolean = isHouse && nftPreserved && isValidReveal
  val canRefund: Boolean = isTimedOut && isPlayerRefund && refundValueOk && nftToHouse
  
  // Main condition: either reveal or refund
  canReveal || canRefund
}