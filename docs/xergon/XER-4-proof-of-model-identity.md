# XER-4: Proof of Model Identity

## Status
DRAFT — Protocol Architect

## Priority
HIGH (core trust layer)

## Objective
On-chain, verifiable proof that a specific AI model produced a given output. This is the foundational trust layer for Xergon — every provider claim, payment, and reputation signal depends on model identity being cryptographically verifiable.

## Design

### Overview

Model identity is established through a **registration → attestation → verification** lifecycle on Ergo.

1. **Model Registration**: A provider registers a model on-chain by committing model metadata (architecture hash, weights checksum, provider pubkey) into a UTXO box. The box holds a unique Model NFT that serves as the on-chain identity.

2. **Attestation**: When a model produces an output, it signs `hash(prompt || output || timestamp || nonce)` with its private key. The attestation is submitted on-chain or stored off-chain with on-chain anchoring.

3. **Verification**: Any party can verify that an attestation came from a registered model by checking the signature against the registered pubkey and confirming the model box hasn't been revoked.

### Trust Properties

| Property | Mechanism |
|----------|-----------|
| Model authenticity | ECDSA/secp256k1 signature from registered model key |
| Non-repudiation | Signature is cryptographically binding |
| Revocability | Model box can be spent (revoked) by provider or governance |
| Timestamp integrity | Ergo block height in attestation, not provider-controlled |
| Privacy (optional) | Sigma protocol ZK proofs allow verification without revealing model identity |

### Register Layout (ModelIdentityBox)

```
Tokens:  [ModelNFT]           — unique NFT, acts as model ID
Value:   min ERG for box rent (~0.001 ERG)
R4:      Coll[Byte]           — provider public key (33 bytes, compressed)
R5:      Coll[Byte]           — model public key (33 bytes, compressed, signing key)
R6:      Coll[Byte]           — architecture hash (blake2b256 of model config, 32 bytes)
R7:      Coll[Byte]           — weights commitment (blake2b256 of weight checksum manifest, 32 bytes)
R8:      Int                  — registration height
R9:      Coll[Byte]           — metadata URI (IPFS CID or similar, variable length)
```

### Attestation Box Layout

```
Tokens:  [AttestationToken(opt)] — if on-chain attestation
Value:   min ERG for box rent
R4:      Coll[Byte]           — model public key (references registered model)
R5:      Coll[Byte]           — blake2b256(prompt_hash || output_hash || height || nonce)
R6:      Coll[Byte]           — signature over R5 payload
R7:      Int                  — attestation height
R8:      Coll[Byte]           — provider pubkey (who submitted the attestation)
R9:      Coll[Byte]           — request ID or reference (links to off-chain request)
```

### Contract Spend Paths

**Model Registration Box:**
1. **Revoke** — provider can destroy the registration (spend box, burn NFT)
2. **Governance revoke** — multi-sig governance can revoke compromised models
3. **Update** — provider can update metadata (recreate box with same NFT)

**Attestation Verification Contract:**
1. **Verify** — anyone can spend if: signature is valid against model pubkey, model is registered (checked via input box reference), attestation height is valid
2. **Expire** — after configurable height, attestation box can be spent back to submitter

### Sigma Protocol Extension (Privacy)

For use cases where the specific model identity must remain private while still proving authenticity:

- Use `proveDHTuple` or custom Sigma protocol
- Prove knowledge of a valid model key without revealing which key
- Requires a set of registered model keys as context
- Enables "I can prove this came from a registered model" without "here's which model"

### Security Considerations

1. **Key compromise**: Provider must be able to rotate model keys. Design a key-rotation path that preserves the Model NFT but updates R5.
2. **Weights spoofing**: Architecture hash (R6) and weights commitment (R7) are hash commitments. Full weights are off-chain (IPFS/Filecoin). The on-chain hash binds to the off-chain data — any tampering is detectable.
3. **Sybil resistance**: XER-6 will address this. XER-4 focuses on identity verification per-model, not per-provider uniqueness.
4. **Attestation spam**: Minimum ERG in attestation boxes deters spam. Rate limiting can be added via governance contracts.
5. **Replay attacks**: Nonce + height in attestation payload prevents replay.

## Open Questions

- [ ] Should model registration require a staking bond? (XER-6 overlap)
- [ ] Attestation anchoring: full on-chain boxes vs. OP_RETURN-style commits?
- [ ] ZK privacy: which specific Sigma protocol? `proveDHTuple` is simplest but limited.
- [ ] Cross-chain verification? (future scope)

## Dependencies

- XER-6: Sybil-resistant provider identity (registration may require provider identity proof)
- XER-9: ERG payment rails (attestations may be payment-conditional)
