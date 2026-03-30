/**
 * DuckPools Coinflip Game Contract v3
 *
 * Commit-reveal coinflip with reveal-window enforcement and NFT preservation.
 *
 * FAIRNESS IMPROVEMENTS OVER v2:
 * 1. SHORTER TIMEOUT (30 blocks instead of 100): Reduces house's block-grinding window
 * 2. REVEAL HEIGHT COMMITMENT (R10): House must pre-commit to the reveal block height
 *    at bet creation time. This limits (but cannot fully eliminate) block grinding.
 * 3. REVEAL WINDOW: House must reveal between rngBlockHeight and timeoutHeight.
 *    This narrows the grinding window to just (timeoutHeight - rngBlockHeight) blocks.
 * 4. NFT PRESERVATION: Both reveal and refund paths preserve the game NFT in OUTPUTS(1).
 *    This prevents protocol breakage from accidental NFT burning.
 *
 * SECURITY MODEL (PoC+):
 *   - Player secret (R9) is visible on-chain. Honest house assumption.
 *   - House block-grinding window is limited to (timeoutHeight - rngBlockHeight) blocks.
 *   - Only house can reveal. Player must wait for timeout if house offline.
 *   - Production hardening: ZK proofs, oracle RNG, player-initiated reveal.
 *
 * REGISTER LAYOUT:
 *   R4:  Coll[Byte]  — house's compressed public key (33 bytes)
 *   R5:  Coll[Byte]  — player's compressed public key (33 bytes)
 *   R6:  Coll[Byte]  — blake2b256(secret || choice) — 32 bytes
 *   R7:  Int         — player's choice: 0=heads, 1=tails
 *   R8:  Int         — timeout block height for refund
 *   R9:  Coll[Byte]  — player's secret (8 random bytes)
 *   R10: Int         — pre-committed reveal height (earliest block house can reveal)
 *
 * TOKEN LAYOUT:
 *   Token 0: Game NFT (amount=1) — preserved in OUTPUTS(1) for both paths
 *
 * SPENDING PATHS:
 *   1. REVEAL (house): Verifies commitment, checks reveal window, pays winner
 *      NFT preserved in OUTPUTS(1)
 *   2. REFUND (player): After timeout height, player reclaims bet minus 2% fee
 *      NFT preserved in OUTPUTS(1)
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

  // -- Game NFT preservation -----------------------------------------
  val gameNFTId: Coll[Byte] = SELF.tokens(0)._1
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
  // Conditions: house signature valid, commitment verified,
  // reveal happens between rngBlockHeight and timeoutHeight,
  // correct payout to winner, NFT preserved in OUTPUTS(1)
  val canReveal: Boolean = {
    houseProp && commitmentOk && nftPreserved && {
      // House must reveal within the committed window
      val revealWindow = (HEIGHT >= rngBlockHeight) && (HEIGHT <= timeoutHeight)
      revealWindow && {
        if (playerWins) {
          // Player wins: must pay to player with >= 1.94x
          OUTPUTS(0).propositionBytes == playerProp.propBytes &&
          OUTPUTS(0).value >= winPayout
        } else {
          // House wins: must pay to house with full bet
          OUTPUTS(0).propositionBytes == houseProp.propBytes &&
          OUTPUTS(0).value >= betAmount
        }
      }
    }
  }

  // -- REFUND path: player spends after timeout ----------------------
  // Conditions: timeout reached, player signature valid,
  // correct refund amount, NFT preserved in OUTPUTS(1)
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
