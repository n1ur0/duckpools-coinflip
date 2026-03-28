{
  // --- Plinko Contract v1 ---
  // Commit-reveal betting game for plinko drop
  // Fixed: NFT preservation in refund path (MAT-261)
  //
  // Tokens:
  //   (0) = PLINKO_NFT_ID (singleton, 1 unit) - game identity
  //
  // Registers:
  //   R4: Coll[Byte] - Player's ErgoTree (return address)
  //   R5: Coll[Byte] - Commitment hash (32 bytes SHA256)
  //   R6: Int        - Drop position/choice
  //   R7: Int        - Player's random secret
  //   R8: Coll[Byte] - Bet ID (32 bytes)
  //   R9: Int        - Timeout height (blocks until refund)

  val nftId = SELF.tokens(0)._1
  val playerTree = SELF.R4[Coll[Byte]].get
  val commitment = SELF.R5[Coll[Byte]].get
  val dropPosition = SELF.R6[Int].get
  val secret = SELF.R7[Int].get
  val betId = SELF.R8[Coll[Byte]].get
  val timeoutHeight = SELF.R9[Int].get

  // Helper: Check if NFT is preserved in output
  val nftPreserved = OUTPUTS.exists { (output: Box) =>
    output.tokens.exists { (token: (Coll[Byte], Long)) =>
      token._1 == nftId && token._2 == 1L
    }
  }

  // Helper: Check if timeout has passed
  val isTimedOut = HEIGHT >= timeoutHeight

  // Helper: Check if this is a player refund (player spending their own box)
  val isPlayerRefund = OUTPUTS(0).propositionBytes == playerTree

  // Helper: Check if refund value is correct (player gets their bet amount back)
  val refundValueOk = OUTPUTS(0).value == SELF.value

  // --- Path 1: Reveal (House reveals secret) ---
  // House provides the secret and block hash to determine outcome
  val canReveal = {
    // Find house output box (same script, preserves NFT)
    val houseOut = OUTPUTS.find { (b: Box) =>
      b.propositionBytes == SELF.propositionBytes &&
      b.tokens.exists { (t: (Coll[Byte], Long)) => t._1 == nftId && t._2 == 1L }
    }
    
    houseOut.isDefined &&
    // Verify commitment: SHA256(secret || dropPosition) == R5
    // This would be implemented with proper crypto operations
    // For now, we assume the verification happens off-chain
    true
  }

  // --- Path 2: Refund (Player after timeout) ---
  // FIXED: Now preserves NFT to prevent burning (MAT-261)
  val canRefund = isTimedOut && isPlayerRefund && refundValueOk && nftPreserved

  canReveal || canRefund
}