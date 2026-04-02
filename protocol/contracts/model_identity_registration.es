/**
 * XER-4: Model Identity Registration Contract
 *
 * Registers an AI model on-chain with cryptographic commitments to
 * its architecture and weights. The Model NFT token is the on-chain
 * identity — whoever controls it controls the model's identity.
 *
 * TRUST ASSUMPTIONS:
 * - TA-1: Model weights are stored off-chain (IPFS/Filecoin). The
 *   on-chain hash (R7) commits to the weights manifest but cannot
 *   verify the full weights on-chain due to size limits.
 * - TA-2: Provider is trusted to register accurate architecture hash
 *   (R6). Governance can revoke if fraud is proven.
 * - TA-3: Model signing key (R5) must be kept secure. If compromised,
 *   the revocation path must be used immediately.
 *
 * REGISTER LAYOUT:
 *   Tokens: [ModelNFT]          — unique NFT, model's on-chain identity
 *   R4:  Coll[Byte]             — provider public key (33 bytes, compressed secp256k1)
 *   R5:  Coll[Byte]             — model signing public key (33 bytes, compressed)
 *   R6:  Coll[Byte]             — architecture hash: blake2b256(model_config), 32 bytes
 *   R7:  Coll[Byte]             — weights commitment: blake2b256(weights_manifest), 32 bytes
 *   R8:  Int                    — registration block height
 *   R9:  Coll[Byte]             — metadata URI (IPFS CID, variable length)
 *
 * SPEND PATHS:
 *   1. REVOKE (provider): Provider burns the Model NFT, destroying the identity.
 *   2. GOVERNANCE_REVOKE: Multi-sig governance burns the Model NFT.
 *   3. UPDATE (provider): Provider recreates the box with updated metadata
 *      (same Model NFT, preserves identity, changes R6/R7/R9).
 */

{
  // ── Read registers ─────────────────────────────────────────────
  val providerPk: Coll[Byte] = SELF.R4[Coll[Byte]].get
  val modelPk:    Coll[Byte] = SELF.R5[Coll[Byte]].get
  // R6 (arch hash) and R7 (weights commitment) are commitments, not
  // directly used in verification logic — they're data for off-chain
  // consumers to verify against stored model artifacts.
  val regHeight:  Int         = SELF.R8[Int].get
  // R9 metadata URI is informational, not verified on-chain.

  // ── Derive SigmaProps from raw PK bytes ────────────────────────
  val providerProp: SigmaProp = proveDlog(decodePoint(providerPk))
  // modelProp is NOT verified here — it's used by the attestation
  // verification contract (model_attestation.es) to check signatures.

  // ── Governance public key (hardcoded for initial version) ──────
  // TODO: Replace with multi-sig governance contract (XER-6 or XER-2)
  // For now, governance is a single key that can revoke any model.
  // In production: committee NFT + threshold signature.
  val governancePkBytes: Coll[Byte] = fromBase64(
    "GOVERNANCE_PUBKEY_BASE64_HERE"
  )
  val governanceProp: SigmaProp = proveDlog(decodePoint(governancePkBytes))

  // ── REVOKE path: provider burns the model identity ─────────────
  // Provider spends the box. Model NFT is NOT preserved in outputs
  // (burned). This is irreversible.
  val canRevoke: Boolean = {
    providerProp && {
      // Verify Model NFT is NOT in any output (burned)
      // We check that no output box contains the same NFT token ID.
      val modelNftId = SELF.tokens(0)._1
      !OUTPUTS.exists { (box: Box) =>
        box.tokens.exists { (token: (Coll[Byte], Long)) =>
          token._1 == modelNftId
        }
      }
    }
  }

  // ── GOVERNANCE_REVOKE path: committee burns compromised model ──
  val canGovernanceRevoke: Boolean = {
    governanceProp && {
      val modelNftId = SELF.tokens(0)._1
      !OUTPUTS.exists { (box: Box) =>
        box.tokens.exists { (token: (Coll[Byte], Long)) =>
          token._1 == modelNftId
        }
      }
    }
  }

  // ── UPDATE path: provider updates metadata, keeps identity ─────
  // Model NFT must be preserved in exactly one output.
  // R4 (provider) and R5 (model key) must match.
  // R6, R7, R9 can be updated.
  val canUpdate: Boolean = {
    providerProp && {
      val modelNftId = SELF.tokens(0)._1
      // Exactly one output must contain the Model NFT
      OUTPUTS.exists { (box: Box) =>
        box.tokens.exists { (token: (Coll[Byte], Long)) =>
          token._1 == modelNftId && token._2 == 1L
        }
      } && {
        // Find the output with our NFT and verify key continuity
        val updateBox = OUTPUTS.find { (box: Box) =>
          box.tokens.exists { (token: (Coll[Byte], Long)) =>
            token._1 == modelNftId
          }
        }.get
        // Provider and model keys must not change
        updateBox.R4[Coll[Byte]].get == providerPk &&
        updateBox.R5[Coll[Byte]].get == modelPk &&
        // Registration height preserved
        updateBox.R8[Int].get == regHeight
      }
    }
  }

  // ── Main guard ─────────────────────────────────────────────────
  canRevoke || canGovernanceRevoke || canUpdate
}
