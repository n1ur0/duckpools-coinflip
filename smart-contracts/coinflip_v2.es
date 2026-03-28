/**
 * DuckPools Coinflip Game Contract v2
 *
 * Commit-reveal coinflip with on-chain block-hash RNG.
 *
 * TRUST ASSUMPTIONS (see ARCHITECTURE.md for details):
 * - TA-1: Player secret stored in R9 is visible on-chain. Any observer
 *   can read the player's choice after commit. The contract needs the
 *   secret to verify the commitment hash — this is a fundamental
 *   ErgoScript limitation (no ZK proofs).
 * - TA-2: House selects the reveal block (block-hash grinding risk).
 *   The house controls when to submit the reveal tx, so it could
 *   theoretically wait for a favorable block hash. Mitigated by the
 *   timeout mechanism (R8) — if the house delays too long, the player
 *   can claim a 98% refund.
 * - TA-4: Only the house can trigger reveal. No player-initiated reveal.
 *   If the house is offline, the player must wait for timeout.
 *
 * Production hardening: dual commitment scheme (house pre-commits too),
 * ZK proofs for secret verification, player-initiated reveal path.
 *
 * COMPILED (2026-03-28, ergo-6.0.3 Lithos testnet, treeVersion=1):
 *   R4:  Coll[Byte]  — house's compressed public key (33 bytes)
 *   R5:  Coll[Byte]  — player's compressed public key (33 bytes)
 *   R6:  Coll[Byte]  — blake2b256(secret || choice) — 32 bytes
 *   R7:  Int         — player's choice: 0=heads, 1=tails
 *   R8:  Int         — block height for timeout/refund
 *   R9:  Coll[Byte]  — player's secret (32 random bytes)
 *
 * Note: betId is tracked off-chain only (not in box registers).
 *       Ergo only supports R4-R9 (6 non-mandatory registers).
 *
 * Spending paths:
 *   1. REVEAL (house): Verifies commitment on-chain, determines outcome
 *      via block-hash RNG, pays player on win or house on loss.
 *   2. REFUND (player): After timeout height, player reclaims bet minus 2% fee.
 */

{
  // ── Read registers ─────────────────────────────────────────────
  val housePkBytes:    Coll[Byte] = SELF.R4[Coll[Byte]].get
  val playerPkBytes:   Coll[Byte] = SELF.R5[Coll[Byte]].get
  val commitmentHash:  Coll[Byte] = SELF.R6[Coll[Byte]].get
  val playerChoice:    Int         = SELF.R7[Int].get
  val timeoutHeight:   Int         = SELF.R8[Int].get
  val playerSecret:    Coll[Byte] = SELF.R9[Coll[Byte]].get

  // ── Derive SigmaProps from raw PK bytes ────────────────────────
  val housePk:  GroupElement = decodePoint(housePkBytes)
  val playerPk: GroupElement = decodePoint(playerPkBytes)
  val houseProp:  SigmaProp = proveDlog(housePk)
  val playerProp: SigmaProp = proveDlog(playerPk)

  // ── On-chain commitment verification ───────────────────────────
  // commitmentHash MUST equal blake2b256(secret || choice_byte)
  val choiceByte  = if (playerChoice == 0) (0.toByte) else (1.toByte)
  val computedHash = blake2b256(playerSecret ++ Coll(choiceByte))
  val commitmentOk = (computedHash == commitmentHash)

  // ── On-chain RNG using parent block hash ───────────────────────
  // Entropy = blake2b256(prevBlockHash || playerSecret)
  // Result  = hash[0] % 2  (0 = heads, 1 = tails)
  val blockSeed  = CONTEXT.preHeader.parentId
  val rngHash    = blake2b256(blockSeed ++ playerSecret)
  val flipResult = rngHash(0) % 2
  val playerWins = (flipResult == playerChoice)

  // ── Value calculations ─────────────────────────────────────────
  val betAmount    = SELF.value
  // Player wins: 1.94x payout (3% house edge on the 2x)
  val winPayout    = betAmount * 97L / 50L
  // Refund: 98% of bet (2% fee to prevent spam)
  val refundAmount = betAmount - betAmount / 50L

  // ── REVEAL path: house spends ─────────────────────────────────
  val canReveal: Boolean = {
    houseProp && commitmentOk && {
      if (playerWins) {
        OUTPUTS(0).propositionBytes == playerProp.propBytes &&
        OUTPUTS(0).value >= winPayout
      } else {
        OUTPUTS(0).propositionBytes == houseProp.propBytes &&
        OUTPUTS(0).value >= betAmount
      }
    }
  }

  // ── REFUND path: player spends after timeout ───────────────────
  val canRefund: Boolean = {
    HEIGHT >= timeoutHeight &&
    playerProp &&
    OUTPUTS(0).propositionBytes == playerProp.propBytes &&
    OUTPUTS(0).value >= refundAmount
  }

  // ── Main guard ─────────────────────────────────────────────────
  canReveal || canRefund
}
