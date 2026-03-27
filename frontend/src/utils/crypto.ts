// Cryptographic utilities

/**
 * SHA-256 hash for commitment/reveal scheme
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
 * Convert hex string to bytes
 */
export function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}
