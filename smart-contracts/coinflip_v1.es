/**
 * DuckPools Coinflip Game Contract v1
 * 
 * Classic coinflip game with commit-reveal scheme.
 * Fixed: NFT preservation in refund path to prevent protocol breakage.
 *
 * TRUST ASSUMPTIONS (see ARCHITECTURE.md for details):
 * - TA-1: Player secret stored in R8 is visible on-chain. Any observer
 *   can read the player's choice after commit. This is a fundamental
 *   trade-off — the contract needs the secret to verify the commitment.
 * - TA-2: No on-chain RNG. v1 has no block-hash based outcome; the
 *   house determines the result off-chain. v2 fixes this.
 * - TA-3: Reveal path does NOT enforce payout amount. A malicious house
 *   could reveal with 0 ERG to the player. v2 enforces payout on-chain.
 * - TA-4: Only the house can trigger reveal. If the house is offline,
 *   the player must wait for timeout to claim a 98% refund.
 *
 * STATUS: Superseded by coinflip_v2.es. Kept for reference only.
 */

{
  // Game parameters
  val housePubKey: GroupElement = fromSelf.R4[GroupElement].get
  
  // Player commitment
  val playerPubKey: Coll[Byte] = fromSelf.R5[Coll[Byte]].get
  val commitmentHash: Coll[Byte] = fromSelf.R6[Coll[Byte]].get
  val playerChoice: Int = fromSelf.R7[Int].get // 0=heads, 1=tails
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
    val choiceBytes = playerChoice.toBytes
    val computedHash = blake2b256(secretBytes ++ choiceBytes)
    computedHash == commitmentHash
  }
  
  // Spending conditions
  val canReveal: Boolean = isHouse && nftPreserved && isValidReveal
  val canRefund: Boolean = isTimedOut && isPlayerRefund && refundValueOk && nftToHouse
  
  // Main condition: either reveal or refund
  canReveal || canRefund
}