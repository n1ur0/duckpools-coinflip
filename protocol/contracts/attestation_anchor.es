/**
 * XER-4: Attestation Anchor Contract
 *
 * Lightweight on-chain anchoring for attestations that don't need
 * full verification boxes. Uses an OP_RETURN-style approach —
 * commits the attestation hash to the blockchain for tamper-proof
 * timestamping without the cost of a full verification box.
 *
 * Use case: High-volume attestations where full on-chain verification
 * is too expensive. The anchor provides an immutable timestamp and
 * hash commitment. Off-chain verifiers check the anchored hash against
 * the full attestation data.
 *
 * BOX LAYOUT:
 *   Tokens:  [AnchorToken(opt)]  — optional, for grouping
 *   Value:   min ERG (~0.001 ERG)
 *   R4:      Coll[Byte]         — attestation hash: blake2b256(full_attestation_data), 32 bytes
 *   R5:      Coll[Byte]         — model public key (references registered model), 33 bytes
 *   R6:      Int                — anchor height (block height when anchored)
 *   R7:      Coll[Byte]         — previous anchor hash (chain linkage), 32 bytes
 *   R8:      Coll[Byte]         — provider public key, 33 bytes
 *
 * SPEND PATHS:
 *   1. CONSUME: Provider can spend the anchor after 1440 blocks (~2 days).
 */

{
  val attestHash:     Coll[Byte] = SELF.R4[Coll[Byte]].get
  val modelPkBytes:   Coll[Byte] = SELF.R5[Coll[Byte]].get
  val anchorHeight:   Int         = SELF.R6[Int].get
  // R7 (prev anchor hash) is for chain linkage, informational
  val providerPkBytes:Coll[Byte] = SELF.R8[Coll[Byte]].get

  val providerProp: SigmaProp = proveDlog(decodePoint(providerPkBytes))

  // ── CONSUME path: provider reclaims after expiry ───────────────
  val expiryHeight: Int = anchorHeight + 1440L  // ~2 days at 2-min blocks
  val canConsume: Boolean = {
    HEIGHT > expiryHeight &&
    providerProp && {
      OUTPUTS.size >= 1 &&
      OUTPUTS(0).propositionBytes == providerProp.propBytes &&
      OUTPUTS(0).value >= SELF.value
    }
  }

  canConsume
}
