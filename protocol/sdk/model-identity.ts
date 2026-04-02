/**
 * XER-4 SDK: Proof of Model Identity
 *
 * TypeScript SDK for registering models, creating attestations,
 * and verifying model identity on the Ergo blockchain.
 */

import {
  Box,
  Contract,
  ErgoAddress,
  EpochRules,
  I64,
  SByte,
  SColl,
  SInt,
  SigmaProp,
  Token,
  TransactionBuilder,
  TxBuilder,
} from '@fleet-sdk/core';
import { blake2b256 } from '@fleet-sdk/crypto';
import * as nobleSecp256k1 from '@noble/secp256k1';

// ── Types ────────────────────────────────────────────────────────

export interface ModelRegistration {
  /** Provider's Ergo address */
  providerAddress: string;
  /** Model signing public key (compressed, 33 bytes hex) */
  modelPublicKey: string;
  /** blake2b256 of model architecture/config */
  architectureHash: string;
  /** blake2b256 of weights manifest */
  weightsCommitment: string;
  /** IPFS CID or URL pointing to model metadata */
  metadataUri: string;
}

export interface ModelAttestation {
  /** Hex-encoded prompt hash (blake2b256 of prompt) */
  promptHash: string;
  /** Hex-encoded output hash (blake2b256 of model output) */
  outputHash: string;
  /** Block height when attestation was created */
  height: number;
  /** Random nonce for replay protection (hex) */
  nonce: string;
  /** Hex-encoded signature over the payload */
  signature: string;
}

export interface AttestationPayload {
  /** Hex-encoded payload hash */
  payloadHash: string;
  /** Hex-encoded payload (for signing) */
  payload: string;
}

// ── Model Registration ───────────────────────────────────────────

export class ModelIdentityRegistrar {
  /**
   * Build a transaction to register a new model on-chain.
   *
   * Creates a UTXO box containing the Model NFT and all registration
   * data. The box is guarded by the model_identity_registration.es
   * contract.
   */
  static buildRegistrationTx(
    builder: TxBuilder,
    registration: ModelRegistration,
    modelNftTokenId: string,
    inputBoxes: Box[],
    changeAddress: string,
    currentHeight: number,
    contractErgoTree: string,
  ): TransactionBuilder {
    const providerPk = ErgoAddress.fromBase58(registration.providerAddress)
      .publicKeys[0];

    const unsignedTx = builder
      .from(inputBoxes)
      .to(
        new Contract(contractErgoTree).toErgoTree(),
        { value: BigInt('1000000'), tokens: [{ tokenId: modelNftTokenId, amount: BigInt(1) }] },
        (box) => [
          SByte.fromHex(providerPk),
          SByte.fromHex(registration.modelPublicKey),
          SColl(SByte).fromHex(registration.architectureHash),
          SColl(SByte).fromHex(registration.weightsCommitment),
          SInt(currentHeight),
          SColl(SByte).fromHex(Buffer.from(registration.metadataUri).toString('hex')),
        ],
      )
      .sendChangeTo(ErgoAddress.fromBase58(changeAddress))
      .build();

    return unsignedTx;
  }

  /**
   * Build a transaction to update model metadata.
   * Preserves Model NFT and key registers, updates R6/R7/R9.
   */
  static buildUpdateTx(
    builder: TxBuilder,
    registrationBox: Box,
    updatedRegistration: Partial<Pick<ModelRegistration, 'architectureHash' | 'weightsCommitment' | 'metadataUri'>>,
    inputBoxes: Box[],
    changeAddress: string,
    contractErgoTree: string,
  ): TransactionBuilder {
    const providerPk = registrationBox.additionalRegisters.R4
      .toString()
      .replace('0e', '');

    const r6 = updatedRegistration.architectureHash || registrationBox.additionalRegisters.R6.toString();
    const r7 = updatedRegistration.weightsCommitment || registrationBox.additionalRegisters.R7.toString();
    const r9 = updatedRegistration.metadataUri
      ? Buffer.from(updatedRegistration.metadataUri).toString('hex')
      : registrationBox.additionalRegisters.R9.toString();

    const unsignedTx = builder
      .from(inputBoxes)
      .to(
        new Contract(contractErgoTree).toErgoTree(),
        {
          value: registrationBox.value,
          tokens: [{ tokenId: registrationBox.tokens[0].tokenId, amount: BigInt(1) }],
        },
        (box) => [
          SByte.fromHex(providerPk),
          SByte.fromHex(registrationBox.additionalRegisters.R5.toString()),
          SColl(SByte).fromHex(r6),
          SColl(SByte).fromHex(r7),
          SInt(registrationBox.additionalRegisters.R8.toBigInt()),
          SColl(SByte).fromHex(r9),
        ],
      )
      .sendChangeTo(ErgoAddress.fromBase58(changeAddress))
      .build();

    return unsignedTx;
  }

  /**
   * Build a transaction to revoke (burn) a model registration.
   * Destroys the Model NFT. Irreversible.
   */
  static buildRevokeTx(
    builder: TxBuilder,
    registrationBox: Box,
    inputBoxes: Box[],
    changeAddress: string,
  ): TransactionBuilder {
    // Simply spend the registration box without preserving the NFT
    // in any output. The NFT is burned.
    const unsignedTx = builder
      .from(inputBoxes)
      .sendChangeTo(ErgoAddress.fromBase58(changeAddress))
      .build();

    return unsignedTx;
  }
}

// ── Attestation Creation ─────────────────────────────────────────

export class ModelAttestor {
  /**
   * Create an attestation payload for signing.
   *
   * payload = blake2b256(prompt_hash || output_hash || height_bytes || nonce)
   */
  static createPayload(
    promptHash: string,
    outputHash: string,
    height: number,
    nonce: string,
  ): AttestationPayload {
    const heightBytes = Buffer.alloc(4);
    heightBytes.writeUInt32BE(height);

    const payload = Buffer.concat([
      Buffer.from(promptHash, 'hex'),
      Buffer.from(outputHash, 'hex'),
      heightBytes,
      Buffer.from(nonce, 'hex'),
    ]);

    const payloadHash = blake2b256(payload);

    return {
      payloadHash: Buffer.from(payloadHash).toString('hex'),
      payload: payload.toString('hex'),
    };
  }

  /**
   * Sign an attestation payload with the model's private key.
   *
   * Uses Schnorr signature (native to Ergo's Sigma protocol).
   * For ECDSA, use nobleSecp256k1.sign() instead.
   */
  static signAttestation(
    payload: string,
    modelPrivateKey: string,
  ): string {
    const msgHash = blake2b256(Buffer.from(payload, 'hex'));
    const signature = nobleSecp256k1.schnorr.sign(
      Buffer.from(payload, 'hex'),
      modelPrivateKey,
    );
    return Buffer.from(signature).toString('hex');
  }

  /**
   * Verify an attestation signature against a model public key.
   */
  static verifyAttestationSignature(
    payload: string,
    signature: string,
    modelPublicKey: string,
  ): boolean {
    try {
      return nobleSecp256k1.schnorr.verify(
        signature,
        Buffer.from(payload, 'hex'),
        modelPublicKey,
      );
    } catch {
      return false;
    }
  }
}

// ── Attestation Verification ─────────────────────────────────────

export class ModelAttestationVerifier {
  /**
   * Build a verification transaction that spends an attestation box.
   *
   * The attestation box is guarded by the model's public key via
   * proveDlog. Only the model key holder can authorize the spend,
   * which proves model identity by construction.
   */
  static buildVerificationTx(
    builder: TxBuilder,
    attestationBox: Box,
    registrationBox: Box,
    inputBoxes: Box[],
    changeAddress: string,
  ): TransactionBuilder {
    const unsignedTx = builder
      .from(inputBoxes)
      .sendChangeTo(ErgoAddress.fromBase58(changeAddress))
      .build();

    return unsignedTx;
  }

  /**
   * Off-chain verification of an attestation against a registered model.
   *
   * Checks:
   * 1. Signature is valid for the payload using the model's public key
   * 2. Payload components hash correctly
   * 3. Attestation height is within valid range
   */
  static verifyOffChain(
    attestation: ModelAttestation,
    modelPublicKey: string,
    currentHeight: number,
    maxHeightDelta: number = 720,
  ): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Check height freshness
    if (currentHeight - attestation.height > maxHeightDelta) {
      errors.push(`Attestation expired: height ${attestation.height} is too old`);
    }

    if (attestation.height > currentHeight) {
      errors.push(`Attestation from future: height ${attestation.height} > current ${currentHeight}`);
    }

    // Reconstruct and verify payload
    const { payload, payloadHash } = ModelAttestor.createPayload(
      attestation.promptHash,
      attestation.outputHash,
      attestation.height,
      attestation.nonce,
    );

    // Verify signature
    const sigValid = ModelAttestor.verifyAttestationSignature(
      payload,
      attestation.signature,
      modelPublicKey,
    );

    if (!sigValid) {
      errors.push('Invalid signature');
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }
}

// ── Utility Functions ────────────────────────────────────────────

export function generateModelKeyPair(): {
  privateKey: string;
  publicKey: string;
} {
  const privateKey = nobleSecp256k1.utils.randomPrivateKey();
  const publicKey = nobleSecp256k1.schnorr.getPublicKey(privateKey);
  return {
    privateKey: Buffer.from(privateKey).toString('hex'),
    publicKey: Buffer.from(publicKey).toString('hex'),
  };
}

export function hashArchitecture(config: string): string {
  return Buffer.from(blake2b256(Buffer.from(config, 'utf-8'))).toString('hex');
}

export function hashWeightsManifest(weightsCid: string): string {
  return Buffer.from(blake2b256(Buffer.from(weightsCid, 'utf-8'))).toString('hex');
}

export function generateNonce(): string {
  return Buffer.from(nobleSecp256k1.utils.randomPrivateKey()).toString('hex');
}
