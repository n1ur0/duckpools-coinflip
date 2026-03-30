/**
 * DuckPools Coinflip Game Contract v1
 *
 * Commit-reveal coinflip with on-chain RNG and NFT preservation.
 *
 * REGENERATED from scratch (MAT-393) — the original v1.es had multiple
 * compilation errors: `fromSelf` instead of `SELF`, `sig.verify(pk)`
 * instead of SigmaProp equality, corrupted `player...ytes`, and no
 * actual on-chain RNG (no block-hash derivation).
 *
 * REGISTER LAYOUT:
 *   R4:  Coll[Byte]  — house's compressed public key (33 bytes)
 *   R5:  Coll[Byte]  — player's compressed public key (33 bytes)
 *   R6:  Coll[Byte]  — blake2b256(secret || choice_byte) — 32 bytes
 *   R7:  Int         — player's choice: 0=heads, 1=tails
 *   R8:  Int         — timeout block height for refund
 *   R9:  Coll[Byte]  — player's secret (8 random bytes)
 *   R10: Int         — pre-committed reveal height (earliest block house can reveal)
 *
 * TOKEN LAYOUT:
 *   Token 0: Game NFT (amount=1) — MUST be preserved in both reveal and refund
 *
 * SPENDING PATHS:
 *   1. REVEAL (house): Verifies commitment, checks reveal window, pays winner.
 *      NFT goes to OUTPUTS(1) (house or next game box).
 *   2. REFUND (player): After timeout, player reclaims bet minus 2% fee.
 *      NFT goes to OUTPUTS(1) (returned to pool).
 *
 * RNG:
 *   Entropy = blake2b256(prevBlockHash || playerSecret)
 *   Result  = hash[0] % 2  (0 = heads, 1 = tails)
 *
 * TRUST ASSUMPTIONS:
 *   - TA-1: Player secret visible on-chain (honest house assumption)
 *   - TA-2: House selects reveal block (block-grinding risk, mitigated by R10 window)
 *   - TA-3: Only house can trigger reveal; player must wait for timeout if offline
 */

{
  // -- Read registers ------------------------------------------------
  val housePkBytes:    Coll[Byte] = SELF.R4[Coll[Byte]].get
  val playerPkBytes:   Coll[Byte] = SELF.R5[Coll[Byte]].get
  val commitmentHash:  Coll[Byte] = SELF.R6[Coll[Byte]].get
  val playerChoice:    Int         = SELF.R7[Int].get
  val timeoutHeight:   Int         = SELF.R8[Int].get
  val playerSecret:    Coll[Byte] = SELF.R9[Coll[Byte]].get
  val rngBlockHeight:  Int         = SELF.R10[Int].get

  // -- Derive SigmaProps from raw PK bytes ---------------------------
  val housePk:  GroupElement = decodePoint(housePkBytes)
  val playerPk: GroupElement = decodePoint(playerPkBytes)
  val houseProp:  SigmaProp = proveDlog(housePk)
  val playerProp: SigmaProp = proveDlog(playerPk)

  // -- Game NFT from SELF's tokens -----------------------------------
  // The game box MUST carry exactly 1 NFT as token(0).
  val gameNFTId: Coll[Byte] = SELF.tokens(0)._1

  // -- NFT preservation check ----------------------------------------
  // NFT must appear in OUTPUTS(1) in both reveal and refund paths.
  // This ensures the NFT is never burned — critical for protocol continuity.
  val nftPreserved: Boolean = {
    OUTPUTS.size >= 2 &&
    OUTPUTS(1).tokens.exists { (t: (Coll[Byte], Long)) =>
      t._1 == gameNFTId && t._2 == 1L
    }
  }

  // -- On-chain commitment verification ------------------------------
  // commitmentHash MUST equal blake2b256(secret || choice_byte)
  val choiceByte   = if (playerChoice == 0) (0.toByte) else (1.toByte)
  val computedHash = blake2b256(playerSecret ++ Coll(choiceByte))
  val commitmentOk = (computedHash == commitmentHash)

  // -- On-chain RNG using parent block hash --------------------------
  // Entropy = blake2b256(prevBlockHash || playerSecret)
  // Result  = hash[0] % 2  (0 = heads, 1 = tails)
  // NOTE: CONTEXT.preHeader.parentId is the ONLY block hash available
  // in ErgoScript. Historical block lookups require an oracle.
  val blockSeed   = CONTEXT.preHeader.parentId
  val rngHash     = blake2b256(blockSeed ++ playerSecret)
  val flipResult  = rngHash(0) % 2
  val playerWins  = (flipResult == playerChoice)

  // -- Value calculations --------------------------------------------
  val betAmount    = SELF.value
  // Player wins: 1.94x payout (3% house edge on the 2x)
  val winPayout    = betAmount * 97L / 50L
  // Refund: 98% of bet (2% fee to prevent spam)
  val refundAmount = betAmount - betAmount / 50L

  // -- REVEAL path: house spends within reveal window ----------------
  // Conditions: house signature, commitment verified, reveal window,
  // correct payout to winner, NFT preserved in OUTPUTS(1)
  val canReveal: Boolean = {
    houseProp && commitmentOk && nftPreserved && {
      // House must reveal within the committed window
      val revealWindow = (HEIGHT >= rngBlockHeight) && (HEIGHT <= timeoutHeight)
      revealWindow && {
        if (playerWins) {
          // Player wins: OUTPUTS(0) pays player with >= 1.94x
          OUTPUTS(0).propositionBytes == playerProp.propBytes &&
          OUTPUTS(0).value >= winPayout
        } else {
          // House wins: OUTPUTS(0) pays house with full bet
          OUTPUTS(0).propositionBytes == houseProp.propBytes &&
          OUTPUTS(0).value >= betAmount
        }
      }
    }
  }

  // -- REFUND path: player spends after timeout ----------------------
  // Conditions: timeout reached, player signature, correct refund amount,
  // NFT preserved in OUTPUTS(1)
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
