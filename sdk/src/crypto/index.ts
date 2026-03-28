/**
 * DuckPools SDK - Crypto Utilities
 * blake2b256 hashing, commitment generation, and RNG computation
 *
 * CRITICAL (SEC-CRITICAL-1): All commitment generation and RNG computation
 * MUST use blake2b256 to match on-chain smart contract verification.
 * The Ergo blockchain's native hash opcode is blake2b256. Using SHA-256
 * would cause every single reveal to fail verification, making the protocol
 * completely unusable.
 */

import { Buffer } from 'buffer';
import { createHash, randomBytes } from 'crypto';

// Use Web Crypto API in browser, Node.js crypto in Node.js
let subtle: SubtleCrypto | null = null;

if (typeof globalThis !== 'undefined' && globalThis.crypto?.subtle) {
  // Available in modern Node.js (19+) and all browsers
  subtle = globalThis.crypto.subtle;
} else if (typeof window !== 'undefined' && window.crypto?.subtle) {
  subtle = window.crypto.subtle;
} else {
  // Node.js fallback using crypto.createHash
  subtle = {
    digest: async (algorithm: string, data: Uint8Array) => {
      const algo = algorithm.replace('-', '').toLowerCase();
      const hash = createHash(algo);
      hash.update(Buffer.from(data));
      return new Uint8Array(hash.digest());
    },
  } as unknown as SubtleCrypto;
}

/**
 * blake2b256 hash of data — the native hash function on Ergo.
 *
 * CRITICAL: Use this for ALL commitment generation and RNG computation.
 * The on-chain smart contracts use the blake2b256 opcode.
 * Using SHA-256 would cause every reveal to fail on-chain (SEC-CRITICAL-1).
 */
export async function blake2b256(data: Uint8Array | Buffer | string): Promise<Buffer> {
  let buffer: Buffer;

  if (typeof data === 'string') {
    buffer = Buffer.from(data, 'utf8');
  } else if (Buffer.isBuffer(data)) {
    buffer = data;
  } else {
    buffer = Buffer.from(data);
  }

  // Node.js crypto.blake2b is available since Node.js 15.x
  // digest_size=32 matches Ergo's blake2b256
  return createHash('blake2b512')
    .update(buffer)
    .digest()
    .subarray(0, 32);
}

/**
 * SHA-256 hash — retained for legacy compatibility only.
 * DO NOT use for commitment/reveal or RNG (SEC-CRITICAL-1).
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
  try {
    // Node.js: use crypto.randomBytes (always available)
    return randomBytes(8).toString('hex');
  } catch {
    // Browser: use Web Crypto API
    if (typeof globalThis !== 'undefined' && globalThis.crypto) {
      const bytes = new Uint8Array(8);
      globalThis.crypto.getRandomValues(bytes);
      return Buffer.from(bytes).toString('hex');
    }
    if (typeof window !== 'undefined' && window.crypto) {
      const bytes = new Uint8Array(8);
      window.crypto.getRandomValues(bytes);
      return Buffer.from(bytes).toString('hex');
    }
  }
  throw new Error('Random number generator not available');
}

/**
 * Generate commitment hash for bet
 * Format: blake2b256(secret_8_bytes || choice_byte)
 *
 * CRITICAL: This MUST match on-chain contract verification.
 * The ErgoScript `blake2b256(secretBytes ++ choiceBytes)` opcode
 * produces the same output as this function.
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

  // Compute commitment: blake2b256(secret || choice)
  // MUST match on-chain: blake2b256(secretBytes ++ choiceBytes)
  const commitBuffer = Buffer.concat([secretBytes, choiceByte]);
  const commitHash = await blake2b256(commitBuffer);

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
 * Format: blake2b256(blockHash_hex_string_utf8 || secret_bytes)
 * Outcome: first_byte % 2 (0=heads, 1=tails)
 *
 * CRITICAL: This MUST use blake2b256 to match on-chain verification.
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

  // Compute RNG hash — MUST be blake2b256 to match on-chain
  const rngBuffer = Buffer.concat([blockHashBuffer, secretBytes]);
  const rngHash = await blake2b256(rngBuffer);

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
