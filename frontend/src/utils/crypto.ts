// Cryptographic utilities

import { blake2b } from '@noble/hashes/blake2b';

/**
 * blake2b256 hash — native on Ergo, used for commitment/reveal scheme.
 * MUST match on-chain verification in all smart contracts.
 */
export function blake2b256(message: Uint8Array): Uint8Array {
  return blake2b(message, { dkLen: 32 });
}

/**
 * SHA-256 hash (legacy — do NOT use for new commitment logic)
 */
export async function sha256(message: Uint8Array): Promise<Uint8Array> {
  const hash = await crypto.subtle.digest('SHA-256', message.buffer as ArrayBuffer);
  return new Uint8Array(hash);
}

/**
 * Generate a random 8-byte secret
 */
export function generateSecret(): Uint8Array {
  return crypto.getRandomValues(new Uint8Array(8));
}

/**
 * Convert bytes to hex string
 */
export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Generate a UUID v4 string.
 * Uses crypto.randomUUID() when available (secure contexts),
 * otherwise falls back to crypto.getRandomValues().
 * This avoids "crypto.randomUUID is not a function" errors
 * in non-secure contexts (e.g. file://, some embedded browsers, or older WebViews).
 */
export function generateUUID(): string {
  if (typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback: generate UUID v4 from random bytes
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  // Set version 4 (0100 in bits) at byte[6] high nibble
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  // Set variant 1 (10xx in bits) at byte[8] high nibble
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

/**
 * Convert hex string to bytes
 */
export function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}
