/**
 * XER-4: Model Identity — Unit Tests
 *
 * Tests for the proof-of-model-identity SDK.
 * Run: npx vitest run protocol/tests/model-identity.test.ts
 */

import { describe, it, expect, beforeAll } from 'vitest';
import {
  ModelAttestor,
  ModelAttestationVerifier,
  generateModelKeyPair,
  hashArchitecture,
  hashWeightsManifest,
  generateNonce,
} from '../sdk/model-identity';

describe('XER-4: Model Identity', () => {
  let modelKeys: { privateKey: string; publicKey: string };
  let attackerKeys: { privateKey: string; publicKey: string };

  beforeAll(() => {
    modelKeys = generateModelKeyPair();
    attackerKeys = generateModelKeyPair();
  });

  describe('ModelAttestor', () => {
    it('should create deterministic payload from same inputs', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 500000;
      const nonce = 'c'.repeat(64);

      const payload1 = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);
      const payload2 = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);

      expect(payload1.payloadHash).toBe(payload2.payloadHash);
      expect(payload1.payload).toBe(payload2.payload);
    });

    it('should produce different payloads for different nonces', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 500000;

      const nonce1 = generateNonce();
      const nonce2 = generateNonce();

      const payload1 = ModelAttestor.createPayload(promptHash, outputHash, height, nonce1);
      const payload2 = ModelAttestor.createPayload(promptHash, outputHash, height, nonce2);

      expect(payload1.payloadHash).not.toBe(payload2.payloadHash);
    });

    it('should sign and verify attestation correctly', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 500000;
      const nonce = generateNonce();

      const { payload } = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);
      const signature = ModelAttestor.signAttestation(payload, modelKeys.privateKey);
      const valid = ModelAttestor.verifyAttestationSignature(payload, signature, modelKeys.publicKey);

      expect(valid).toBe(true);
    });

    it('should reject signature from wrong key', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 500000;
      const nonce = generateNonce();

      const { payload } = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);
      // Sign with model key but verify with attacker key
      const signature = ModelAttestor.signAttestation(payload, modelKeys.privateKey);
      const valid = ModelAttestor.verifyAttestationSignature(payload, signature, attackerKeys.publicKey);

      expect(valid).toBe(false);
    });

    it('should reject tampered payload', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 500000;
      const nonce = generateNonce();

      const { payload } = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);
      const signature = ModelAttestor.signAttestation(payload, modelKeys.privateKey);

      // Tamper with the payload
      const tamperedPayload = payload.slice(0, -2) + 'ff';
      const valid = ModelAttestor.verifyAttestationSignature(tamperedPayload, signature, modelKeys.publicKey);

      expect(valid).toBe(false);
    });
  });

  describe('ModelAttestationVerifier', () => {
    it('should verify valid attestation off-chain', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 500000;
      const nonce = generateNonce();
      const currentHeight = 500100;

      const { payload } = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);
      const signature = ModelAttestor.signAttestation(payload, modelKeys.privateKey);

      const result = ModelAttestationVerifier.verifyOffChain(
        { promptHash, outputHash, height, nonce, signature },
        modelKeys.publicKey,
        currentHeight,
      );

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should reject expired attestation', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 499000; // 1000 blocks ago
      const nonce = generateNonce();
      const currentHeight = 500000;
      const maxDelta = 720;

      const { payload } = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);
      const signature = ModelAttestor.signAttestation(payload, modelKeys.privateKey);

      const result = ModelAttestationVerifier.verifyOffChain(
        { promptHash, outputHash, height, nonce, signature },
        modelKeys.publicKey,
        currentHeight,
        maxDelta,
      );

      expect(result.valid).toBe(false);
      expect(result.errors.some(e => e.includes('expired'))).toBe(true);
    });

    it('should reject attestation from future', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 600000; // future
      const nonce = generateNonce();
      const currentHeight = 500000;

      const { payload } = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);
      const signature = ModelAttestor.signAttestation(payload, modelKeys.privateKey);

      const result = ModelAttestationVerifier.verifyOffChain(
        { promptHash, outputHash, height, nonce, signature },
        modelKeys.publicKey,
        currentHeight,
      );

      expect(result.valid).toBe(false);
      expect(result.errors.some(e => e.includes('future'))).toBe(true);
    });

    it('should reject attestation with wrong model key', () => {
      const promptHash = 'a'.repeat(64);
      const outputHash = 'b'.repeat(64);
      const height = 500000;
      const nonce = generateNonce();
      const currentHeight = 500100;

      const { payload } = ModelAttestor.createPayload(promptHash, outputHash, height, nonce);
      const signature = ModelAttestor.signAttestation(payload, modelKeys.privateKey);

      // Verify against a different model's key
      const result = ModelAttestationVerifier.verifyOffChain(
        { promptHash, outputHash, height, nonce, signature },
        attackerKeys.publicKey,
        currentHeight,
      );

      expect(result.valid).toBe(false);
      expect(result.errors.some(e => e.includes('signature'))).toBe(true);
    });
  });

  describe('Utility Functions', () => {
    it('should generate deterministic architecture hashes', () => {
      const config = '{"architecture": "transformer", "layers": 12}';
      const hash1 = hashArchitecture(config);
      const hash2 = hashArchitecture(config);
      expect(hash1).toBe(hash2);
      expect(hash1).toHaveLength(64); // 32 bytes hex
    });

    it('should generate different hashes for different configs', () => {
      const hash1 = hashArchitecture('{"layers": 12}');
      const hash2 = hashArchitecture('{"layers": 24}');
      expect(hash1).not.toBe(hash2);
    });

    it('should generate unique nonces', () => {
      const nonce1 = generateNonce();
      const nonce2 = generateNonce();
      expect(nonce1).not.toBe(nonce2);
    });

    it('should generate valid key pairs', () => {
      const keys = generateModelKeyPair();
      expect(keys.privateKey).toHaveLength(64); // 32 bytes hex
      expect(keys.publicKey).toHaveLength(64); // 32 bytes hex (schnorr pubkey)
    });

    it('should generate different key pairs each time', () => {
      const keys1 = generateModelKeyPair();
      const keys2 = generateModelKeyPair();
      expect(keys1.privateKey).not.toBe(keys2.privateKey);
      expect(keys1.publicKey).not.toBe(keys2.publicKey);
    });
  });
});
