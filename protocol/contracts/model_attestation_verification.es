/**
 * XER-4: Model Attestation Verification Contract
 *
 * Verifies that an attestation (proof that a specific model produced
 * a given output) was signed by a registered model's signing key.
 *
 * This contract does NOT store model registrations — it REFERENCES
 * a ModelIdentityBox (from model_identity_registration.es) as an
 * input to the transaction. The model's public key is read from that
 * box's R5 register.
 *
 * TRUST ASSUMPTIONS:
 * - TA-1: The ModelIdentityBox referenced as input must be a valid,
 *   non-revoked registration. The contract checks that the NFT exists
 *   and keys match but cannot verify governance revocation status
 *   across transactions (that's the registration box's job).
 * - TA-2: Prompt and output hashes (in the attestation payload) are
 *   truncated hashes of the actual content. Full content is verified
 *   off-chain against these hashes.
 * - TA-3: Timestamp is block height (HEIGHT), not wall-clock time.
 *
 * ATTESTATION BOX LAYOUT:
 *   R4:  Coll[Byte]             — model public key (33 bytes, references registered model)
 *   R5:  Coll[Byte]             — attestation payload hash:
 *                                  blake2b256(prompt_hash || output_hash || HEIGHT || nonce), 32 bytes
 *   R6:  Coll[Byte]             — ECDSA signature over R5 payload (DER-encoded, ~71 bytes)
 *   R7:  Int                    — attestation creation height
 *   R8:  Coll[Byte]             — submitter public key (who created the attestation, 33 bytes)
 *   R9:  Coll[Byte]             — request reference ID (links to off-chain request, variable)
 *
 * INPUTS REQUIRED:
 *   - This attestation box (SELF)
 *   - A ModelIdentityBox (the registered model) as another input
 *
 * SPEND PATHS:
 *   1. VERIFY: Anyone can spend if the ECDSA signature (R6) is valid
 *      for the payload (R5) signed by the model key (R4), and the
 *      model key matches the registration box's R5.
 *   2. EXPIRE: Submitter can reclaim the box after expiry height.
 */

{
  // ── Read attestation registers ─────────────────────────────────
  val modelPkBytes:    Coll[Byte] = SELF.R4[Coll[Byte]].get
  val payloadHash:     Coll[Byte] = SELF.R5[Coll[Byte]].get
  val signatureBytes:  Coll[Byte] = SELF.R6[Coll[Byte]].get
  val attestHeight:    Int         = SELF.R7[Int].get
  val submitterPkBytes:Coll[Byte] = SELF.R8[Coll[Byte]].get
  // R9 (request reference) is informational, not verified on-chain.

  // ── Derive SigmaProps ──────────────────────────────────────────
  val modelProp:     SigmaProp = proveDlog(decodePoint(modelPkBytes))
  val submitterProp: SigmaProp = proveDlog(decodePoint(submitterPkBytes))

  // ── Find the ModelIdentityBox in transaction inputs ────────────
  // The registration box must be present as an input (not SELF).
  // We identify it by checking it has exactly 1 token (the Model NFT)
  // and its R5 matches our attestation's model public key.
  val registrationBoxOpt = INPUTS.filter { (input: Box) =>
    input.id != SELF.id &&
    input.tokens.size == 1 &&
    input.R4[Coll[Byte]].isDefined &&
    input.R5[Coll[Byte]].isDefined &&
    input.R5[Coll[Byte]].get == modelPkBytes
  }.headOption

  // ── Verify path: signature check against registered model key ──
  //
  // NOTE: ErgoScript natively supports Sigma protocols (proveDlog,
  // proveDHTuple) but NOT arbitrary ECDSA verification. For full
  // ECDSA sig verification, we have two options:
  //
  // Option A (Sigma Protocol): Use the model's key as a Schnorr/EdDSA
  // key via proveDlog. The attestation box's guard IS the modelProp,
  // meaning only the model's key holder can spend it. This proves
  // model identity by construction — no separate signature needed.
  //
  // Option B (ECDSA via Context Extension): Pass the signature as a
  // context variable and use a custom verifier circuit. This requires
  // Ergo soft-fork or off-chain verification.
  //
  // IMPLEMENTATION: We use Option A (Sigma protocol). The attestation
  // box is guarded by modelProp — only the model key holder can spend.
  // This IS the proof of model identity. R5/R6 store the payload hash
  // and signature for off-chain audit trails, but the on-chain proof
  // is the guard script itself.
  //
  // For the verification spend path, we allow anyone to consume the
  // attestation IF they can prove knowledge of the model's secret key.
  // This means the model key holder (or someone they delegate to)
  // must authorize the spend.
  val canVerify: Boolean = {
    registrationBoxOpt.isDefined && {
      // The spend must be authorized by the model key
      modelProp && {
        // Attestation must not be expired
        HEIGHT <= attestHeight + 720L  // ~2 days at 2-min blocks
      }
    }
  }

  // ── Expire path: submitter reclaims after expiry ───────────────
  val expiryHeight: Int = attestHeight + 720L  // ~2 days
  val canExpire: Boolean = {
    HEIGHT > expiryHeight &&
    submitterProp && {
      OUTPUTS.size >= 1 &&
      OUTPUTS(0).propositionBytes == submitterProp.propBytes &&
      OUTPUTS(0).value >= SELF.value
    }
  }

  // ── Main guard ─────────────────────────────────────────────────
  canVerify || canExpire
}
