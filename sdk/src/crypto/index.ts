/**
 * DuckPools SDK - Crypto Utilities
 * SHA256 hashing, commitment generation, and RNG computation
 */

import { Buffer } from 'buffer';

// Use Web Crypto API in browser, Node.js crypto in Node.js
let subtle: SubtleCrypto | null = null;

if (typeof window !== 'undefined' && window.crypto && window.crypto.subtle) {
  subtle = window.crypto.subtle;
} else if (typeof require === 'function') {
  // Node.js environment
  try {
    const nodeCrypto = require('crypto');
    subtle = {
      digest: async (algorithm: string, data: Uint8Array) => {
        const nodeCrypto = require('crypto');
        const hash = nodeCrypto.createHash(algorithm.replace('-', '').toLowerCase());
        hash.update(Buffer.from(data));
        return new Uint8Array(hash.digest());
      },
    } as unknown as SubtleCrypto;
  } catch (_e) {
    // crypto module not available
  }
}

/**
 * SHA256 hash of data
 */
export async function sha256(data: Uint8Array | Buffer | string): Promise<Buffer> {
  let buffer: Buffer;

  if (typeof data === 'string') {
    buffer = Buffer.from(data, 'utf8');
  } else if (Buffer.isBuffer(data)) {
    buffer = data;
  } else {
    buffer = Buffer.from(data);
  }

  if (subtle) {
    const result = await subtle.digest('SHA-256', new Uint8Array(buffer));
    return Buffer.from(result);
  }

  throw new Error('SHA256 not available: neither Web Crypto API nor Node.js crypto is available');
}

/**
 * Generate a random secret (8 bytes)
 */
export function generateSecret(): string {
  if (typeof window !== 'undefined' && window.crypto) {
    const bytes = new Uint8Array(8);
    window.crypto.getRandomValues(bytes);
    return Buffer.from(bytes).toString('hex');
  } else if (typeof require === 'function') {
    const nodeCrypto = require('crypto');
    return nodeCrypto.randomBytes(8).toString('hex');
  }
  throw new Error('Random number generator not available');
}

/**
 * Generate commitment hash for bet
 * Format: SHA256(secret_8_bytes || choice_byte)
 *
 * @param secret - 8-byte secret as hex string (or random if not provided)
 * @param choice - Bet choice (0=heads, 1=tails)
 * @returns Commitment hash as hex string
 */
export async function generateCommit(
  secret: string | undefined,
  choice: number
): Promise<{ secret: string; commitment: string }> {
  // Generate secret if not provided
  const actualSecret = secret || generateSecret();

  // Ensure secret is 8 bytes (16 hex chars)
  let secretBytes: Buffer;
  if (Buffer.from(actualSecret, 'hex').length === 8) {
    secretBytes = Buffer.from(actualSecret, 'hex');
  } else if (actualSecret.length === 16 && /^[0-9a-fA-F]{16}$/.test(actualSecret)) {
    secretBytes = Buffer.from(actualSecret, 'hex');
  } else {
    // Pad or truncate to 8 bytes
    secretBytes = Buffer.alloc(8);
    const inputBytes = Buffer.from(actualSecret, 'utf8');
    inputBytes.copy(secretBytes, 0, 0, Math.min(8, inputBytes.length));
  }

  // Create choice byte
  const choiceByte = Buffer.alloc(1);
  choiceByte.writeUInt8(choice & 0xff, 0);

  // Compute commitment: SHA256(secret || choice)
  const commitBuffer = Buffer.concat([secretBytes, choiceByte]);
  const commitHash = await sha256(commitBuffer);

  return {
    secret: secretBytes.toString('hex'),
    commitment: commitHash.toString('hex'),
  };
}

/**
 * Verify commitment matches
 */
export async function verifyCommit(
  commitHex: string,
  secretHex: string,
  choice: number
): Promise<boolean> {
  // Compute expected commitment
  const { commitment } = await generateCommit(secretHex, choice);
  return commitHex.toLowerCase() === commitment.toLowerCase();
}

/**
 * Compute RNG hash for bet outcome
 * Format: SHA256(blockHash_hex_string_utf8 || secret_bytes)
 * Outcome: first_byte % 2 (0=heads, 1=tails)
 *
 * @param blockHash - Block hash as hex string (NOT converted to bytes)
 * @param secretHex - 8-byte secret as hex string
 * @returns Outcome (0=heads, 1=tails)
 */
export async function computeRng(blockHash: string, secretHex: string): Promise<number> {
  // Block hash is used as UTF-8 string, NOT as bytes
  const blockHashBuffer = Buffer.from(blockHash, 'utf8');

  // Secret is 8 bytes
  const secretBytes = Buffer.from(secretHex, 'hex');

  // Compute RNG hash
  const rngBuffer = Buffer.concat([blockHashBuffer, secretBytes]);
  const rngHash = await sha256(rngBuffer);

  // Outcome is first byte % 2
  return rngHash[0] % 2;
}

/**
 * Format secret for display (show first 4 chars only)
 */
export function formatSecret(secret: string, showLength = 4): string {
  if (secret.length <= showLength * 2) {
    return secret;
  }
  return `${secret.substring(0, showLength * 2)}...`;
}

/**
 * Format hash for display (show first 8 chars only)
 */
export function formatHash(hash: string, showLength = 8): string {
  if (hash.length <= showLength * 2) {
    return hash;
  }
  return `${hash.substring(0, showLength * 2)}...`;
}
