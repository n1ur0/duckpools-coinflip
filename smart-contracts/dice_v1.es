/**
 * DuckPools Dice Game Contract v1
 *
 * Dice game with commit-reveal scheme.
 * Fixed: NFT preservation in refund path to prevent protocol breakage.
 *
 * ========== SECURITY DESIGN TRADE-OFFS (PoC vs Production) ==========
 *
 * 1. PLAYER SECRET VISIBLE ON-CHAIN (R8 register)
 *    - SEC-HIGH finding (MAT-348)
 *    - Player secret is stored in R8[Int] which is readable by anyone
 *    - House can peek at player's choice before reveal
 *    - TRUST ASSUMPTION: House is honest and does not read R8
 *    - PRODUCTION: Use ZK-proof or commitment scheme without storing secret
 *
 * 2. NO PAYOUT AMOUNT ENFORCEMENT
 *    - SEC-MEDIUM finding (MAT-336)
 *    - Contract verifies player gets OUTPUTS(0), but not how much ERG
 *    - Malicious house could pay 0 ERG and pocket everything
 *    - TRUST ASSUMPTION: House follows payout rules (bet * 0.97 if win)
 *    - PRODUCTION: Add guard: OUTPUTS(0).value >= bet_amount * 0.97
 *
 * 3. BLOCK HASH SELECTION BY HOUSE
 *    - SEC-MEDIUM finding (MAT-336)
 *    - House chooses which block height/hash to use for RNG
 *    - House could grind blocks for favorable outcome
 *    - TRUST ASSUMPTION: House uses current block hash without manipulation
 *    - PRODUCTION: Pre-commit to block height or use oracle
 *
 * 4. ONLY HOUSE CAN REVEAL
 *    - SEC-MEDIUM finding (MAT-336)
 *    - No player-initiated reveal path
 *    - If house goes offline, player must wait for timeout
 *    - TRUST ASSUMPTION: House is always available to reveal
 *    - PRODUCTION: Add player self-reveal with on-chain RNG
 *
 * ========== SUMMARY ==========
 * This is a PROOF-OF-CONTRACT. It trusts the house operator to be honest.
 * For production deployment, cryptographic guarantees must be enforced on-chain.
 *
 * See ARCHITECTURE.md for full security analysis.
 */

{
  // Game parameters
  val housePubKey: GroupElement = fromSelf.R4[GroupElement].get
  
  // Player commitment
  val playerPubKey: Coll[Byte] = fromSelf.R5[Coll[Byte]].get
  val commitmentHash: Coll[Byte] = fromSelf.R6[Coll[Byte]].get
  
  // Game parameters
  val playerChoice: Int = fromSelf.R7[Int].get // 1-6 dice roll
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
    val secretBytes = playerSecret.toBytes
    val choiceBytes = playerChoice.toBytes
    val computedHash = blake2b256(secretBytes ++ choiceBytes)
    computedHash == commitmentHash
  }
  
  // Spending conditions
  val canReveal: Boolean = isHouse && nftPreserved && isValidReveal
  val canRefund: Boolean = isTimedOut && isPlayerRefund && refundValueOk && nftPreserved
  
  // Main condition: either reveal or refund
  canReveal || canRefund
}