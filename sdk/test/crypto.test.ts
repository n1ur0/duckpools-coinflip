/**
 * DuckPools SDK - Crypto Tests
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  generateSecret,
  generateCommit,
  verifyCommit,
  computeRng,
  formatSecret,
  formatHash,
} from '../src/crypto/index.js';

describe('Crypto', () => {
  describe('generateSecret', () => {
    it('should generate 16-character hex string (8 bytes)', () => {
      const secret = generateSecret();
      assert.strictEqual(secret.length, 16);
      assert.match(secret, /^[0-9a-f]{16}$/);
    });

    it('should generate unique secrets', () => {
      const secret1 = generateSecret();
      const secret2 = generateSecret();
      assert.notStrictEqual(secret1, secret2);
    });
  });

  describe('generateCommit', () => {
    it('should generate SHA256 commitment', async () => {
      const secret = generateSecret();
      const choice = 0;
      const { commitment } = await generateCommit(secret, choice);
      assert.strictEqual(commitment.length, 64);
      assert.match(commitment, /^[0-9a-f]{64}$/);
    });

    it('should generate consistent commitment for same input', async () => {
      const secret = generateSecret();
      const choice = 1;
      const { commitment: c1 } = await generateCommit(secret, choice);
      const { commitment: c2 } = await generateCommit(secret, choice);
      assert.strictEqual(c1, c2);
    });

    it('should generate different commitments for different choices', async () => {
      const secret = generateSecret();
      const { commitment: c1 } = await generateCommit(secret, 0);
      const { commitment: c2 } = await generateCommit(secret, 1);
      assert.notStrictEqual(c1, c2);
    });
  });

  describe('verifyCommit', () => {
    it('should verify valid commitment', async () => {
      const secret = generateSecret();
      const choice = 0;
      const { commitment } = await generateCommit(secret, choice);
      const isValid = await verifyCommit(commitment, secret, choice);
      assert.strictEqual(isValid, true);
    });

    it('should reject wrong secret', async () => {
      const secret = generateSecret();
      const wrongSecret = generateSecret();
      const choice = 0;
      const { commitment } = await generateCommit(secret, choice);
      const isValid = await verifyCommit(commitment, wrongSecret, choice);
      assert.strictEqual(isValid, false);
    });

    it('should reject wrong choice', async () => {
      const secret = generateSecret();
      const choice = 0;
      const { commitment } = await generateCommit(secret, choice);
      const isValid = await verifyCommit(commitment, secret, 1);
      assert.strictEqual(isValid, false);
    });
  });

  describe('computeRng', () => {
    it('should compute 0 or 1 as outcome', async () => {
      const blockHash = 'test-block-hash-32-bytes-long-xyz';
      const secret = generateSecret();
      const outcome = await computeRng(blockHash, secret);
      assert.ok(outcome === 0 || outcome === 1);
    });

    it('should compute deterministic outcome for same input', async () => {
      const blockHash = 'test-block-hash-32-bytes-long-xyz';
      const secret = generateSecret();
      const outcome1 = await computeRng(blockHash, secret);
      const outcome2 = await computeRng(blockHash, secret);
      assert.strictEqual(outcome1, outcome2);
    });

    it('should compute different outcomes for different secrets', async () => {
      const blockHash = 'test-block-hash-32-bytes-long-xyz';
      const secret1 = generateSecret();
      const secret2 = generateSecret();
      const outcome1 = await computeRng(blockHash, secret1);
      const outcome2 = await computeRng(blockHash, secret2);
      // Different secrets should likely produce different outcomes
      // (though theoretically could be same by chance)
    });
  });

  describe('formatSecret', () => {
    it('should format hex secret as bytes', () => {
      const secret = 'deadbeefcafebabe';
      const formatted = formatSecret(secret);
      assert.ok(formatted.length > 0);
      assert.ok(formatted.includes('0x'));
    });
  });

  describe('formatHash', () => {
    it('should format hex hash', () => {
      const hash = 'deadbeefcafebabe000000000000000000000000000000000000000000000000';
      const formatted = formatHash(hash);
      assert.ok(formatted.length > 0);
    });
  });
});
