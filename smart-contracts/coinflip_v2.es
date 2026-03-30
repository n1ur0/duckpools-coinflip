/**
 * DuckPools Coinflip Game Contract v2
 *
 * Commit-reveal coinflip with on-chain block-hash RNG and NFT preservation.
 *
 * DIFFERENCES FROM v1:
 *   - Same register layout (R4-R9)
 *   - Same commit-reveal RNG scheme
 *   - Added NFT preservation guard in both reveal and refund paths
 *
 * TRUST ASSUMPTIONS (see ARCHITECTURE.md for details):
 * - TA-1: Player secret stored in R9 is visible on-chain. Any observer
 *   can read the player's choice after commit. The contract needs the
 *   secret to verify the commitment hash — this is a fundamental
 *   ErgoScript limitation (no ZK proofs).
 * - TA-2: House selects the reveal block (block-hash grinding risk).
 *   The house controls when to submit the reveal tx, so it could
 *   theoretically wait for a favorable block hash. Mitigated by the
 *   timeout mechanism (R8).
 * - TA-3: Only the house can trigger reveal. No player-initiated reveal.
 *   If the house is offline, the player must wait for timeout.
 *
 * NOTE: R10 (rngBlockHeight) is NOT supported by Lithos 6.0.3.
 *       Reveal window is enforced off-chain by the house backend.
 *       See coinflip_v3.es documentation for the R10 design.
 *
 * REGISTER LAYOUT:
 *   R4:  Coll[Byte]  — house's compressed public key (33 bytes)
 *   R5:  Coll[Byte]  — player's compressed public key (33 bytes)
 *   R6:  Coll[Byte]  — blake2b256(secret || choice) — 32 bytes
 *   R7:  Int         — player's choice: 0=heads, 1=tails
 *   R8:  Int         — timeout block height for refund
 *   R9:  Coll[Byte]  — player's secret (8 random bytes)
 *
 * TOKEN LAYOUT:
 *   Token 0: Game NFT (amount=1) — preserved in OUTPUTS(1) for both paths
 *
 * SPENDING PATHS:
 *   1. REVEAL (house): Verifies commitment, pays winner
 *   2. REFUND (player): After timeout, player reclaims bet minus 2% fee
 */

{
  // -- Read registers ------------------------------------------------
  val housePkBytes:    Coll[Byte] = SELF.R4[Coll[Byte]].get
  val playerPkBytes:   Coll[Byte] = SELF.R5[Coll[Byte]].get
  val commitmentHash:  Coll[Byte] = SELF.R6[Coll[Byte]].get
  val playerChoice:    Int         = SELF.R7[Int].get
  val timeoutHeight:   Int         = SELF.R8[Int].get
  val playerSecret:    Coll[Byte] = SELF.R9[Coll[Byte]].get

  // -- Derive SigmaProps from raw PK bytes ---------------------------
  val housePk:  GroupElement = decodePoint(housePkBytes)
  val playerPk: GroupElement = decodePoint(playerPkBytes)
  val houseProp:  SigmaProp = proveDlog(housePk)
  val playerProp: SigmaProp = proveDlog(playerPk)

  // -- Game NFT preservation -----------------------------------------
  val gameNFTId: Coll[Byte] = SELF.tokens(0)._1
  val nftPreserved: Boolean = {
    OUTPUTS.size >= 2 &&
    OUTPUTS(1).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == gameNFTId && t._2 == 1L
    }
  }

  // -- On-chain commitment verification ------------------------------
  val choiceByte   = if (playerChoice == 0) (0.toByte) else (1.toByte)
  val computedHash = blake2b256(playerSecret ++ Coll(choiceByte))
  val commitmentOk = (computedHash == commitmentHash)

  // -- On-chain RNG using parent block hash --------------------------
  val blockSeed   = CONTEXT.preHeader.parentId
  val rngHash     = blake2b256(blockSeed ++ playerSecret)
  val flipResult  = rngHash(0) % 2
  val playerWins  = (flipResult == playerChoice)

  // -- Value calculations --------------------------------------------
  val betAmount    = SELF.value
  val winPayout    = betAmount * 97L / 50L
  val refundAmount = betAmount - betAmount / 50L

  // -- REVEAL path: house spends before timeout ----------------------
  val canReveal: Boolean = {
    houseProp && commitmentOk && nftPreserved && {
      HEIGHT < timeoutHeight && {
        if (playerWins) {
          OUTPUTS(0).propositionBytes == playerProp.propBytes &&
          OUTPUTS(0).value >= winPayout
        } else {
          OUTPUTS(0).propositionBytes == houseProp.propBytes &&
          OUTPUTS(0).value >= betAmount
        }
      }
    }
  }

  // -- REFUND path: player spends after timeout ----------------------
  val canRefund: Boolean = {
    HEIGHT >= timeoutHeight &&
    playerProp &&
    nftPreserved &&
    OUTPUTS(0).propositionBytes == playerProp.propBytes &&
    OUTPUTS(0).value >= refundAmount
  }

  // -- Main guard ----------------------------------------------------
  canReveal || canRefund
}
