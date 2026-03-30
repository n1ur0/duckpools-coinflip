/**
 * DuckPools Coinflip Contract v2-final
 *
 * Canonical commit-reveal coinflip for Ergo blockchain.
 * This is the Phase 2 production contract.
 *
 * PROTOCOL FLOW:
 *   1. PLAYER COMMITS: Frontend generates random 8-byte secret, computes
 *      commitment = blake2b256(secret || choice_byte), sends commitment
 *      + choice + secret to backend. Backend creates PendingBetBox on-chain
 *      with this contract, R4-R10 populated.
 *
 *   2. HOUSE REVEALS: Backend observes new PendingBetBox, waits until
 *      rngBlockHeight, fetches current block header, computes
 *      RNG = blake2b256(blockId || secret)[0] % 2, builds reveal
 *      transaction spending the bet box. Must reveal before timeoutHeight.
 *
 *   3. PAYOUT: If playerWins, OUTPUTS(0) goes to player with >= 1.94x bet.
 *      If houseWins, OUTPUTS(0) goes to house with full bet amount.
 *
 *   4. REFUND: If HEIGHT >= timeoutHeight, player can spend the box
 *      themselves, receiving >= 98% of bet (2% spam-prevention fee).
 *
 * SECURITY MODEL (PoC+):
 *   - Player secret (R9) is visible on-chain. Honest house assumption.
 *   - House must pre-commit to reveal height (R10) at bet creation.
 *     This limits the block-grinding window to
 *     (timeoutHeight - rngBlockHeight) blocks (default: 30).
 *   - Only house can reveal. Player must wait for timeout if house offline.
 *   - Production hardening: ZK proofs, oracle RNG, player-initiated reveal.
 *
 * COMPILED (2026-03-30, ergo-6.0.3 Lithos testnet, treeVersion=1):
 *   R4:  Coll[Byte]  -- house compressed public key (33 bytes)
 *   R5:  Coll[Byte]  -- player compressed public key (33 bytes)
 *   R6:  Coll[Byte]  -- blake2b256(secret || choice_byte) -- 32 bytes
 *   R7:  Int         -- player's choice: 0=heads, 1=tails
 *   R8:  Int         -- timeout block height for refund
 *   R9:  Coll[Byte]  -- player secret (8 random bytes)
 *   R10: Int         -- pre-committed reveal height (earliest block house can reveal)
 *
 * ECONOMICS:
 *   House edge: 3% (player gets 1.94x on win instead of 2x)
 *   Refund fee: 2% (player gets 0.98x on timeout refund)
 *   Timeout:    100 blocks (~200 minutes on Ergo)
 *   Reveal window: 30 blocks (~60 minutes, rngBlockHeight to timeoutHeight)
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
  // and correct payout to winner
  val canReveal: Boolean = {
    houseProp && commitmentOk && {
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
  // and player receives >= 98% of bet
  val canRefund: Boolean = {
    HEIGHT >= timeoutHeight &&
    playerProp &&
    OUTPUTS(0).propositionBytes == playerProp.propBytes &&
    OUTPUTS(0).value >= refundAmount
  }

  // -- Main guard ----------------------------------------------------
  canReveal || canRefund
}
