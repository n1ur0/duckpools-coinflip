/**
 * DuckPools Plinko Game Utilities
 *
 * Plinko uses the same commit-reveal architecture as coinflip but with:
 * - 12 rows of pegs = 12 random bits = 2 bytes from secret
 * - Each bit determines left (0) or right (1) bounce
 * - Final position = number of "right" bounces (0-12)
 * - Different landing zones have different multipliers (pyramid distribution)
 *
 * Multipliers (0-indexed positions):
 *   0: 1000x, 1: 130x, 2: 26x, 3: 9x, 4: 4x, 5: 2x, 6: 1x, 7: 2x, 8: 4x, 9: 9x, 10: 26x, 11: 130x, 12: 1000x
 */

import { sha256, bytesToHex, hexToBytes, generateSecret } from './crypto';

// ─── Constants ─────────────────────────────────────────────────

/** Number of peg rows */
export const PLINKO_ROWS = 12;

/** Number of possible landing zones (rows + 1) */
export const PLINKO_ZONES = PLINKO_ROWS + 1;

/** Minimum multiplier (center zone) */
export const PLINKO_MIN_MULTIPLIER = 1.0;

/** Maximum multiplier (edge zones) */
export const PLINKO_MAX_MULTIPLIER = 1000.0;

/** Base house edge (3%) */
export const PLINKO_BASE_HOUSE_EDGE = 0.03;

// Multipliers for each landing zone (0-indexed)
// Pyramidal distribution: edges are high risk/high reward, center is safe/low reward
const PLINKO_MULTIPLIERS: ReadonlyArray<number> = [
  1000, 130, 26, 9, 4, 2, 1, 2, 4, 9, 26, 130, 1000
];

// ─── Payout Calculation ────────────────────────────────────────

/**
 * Get the multiplier for a given landing zone.
 * @param zone - Landing zone (0-12)
 * @returns Multiplier for this zone
 */
export function getPlinkoMultiplier(zone: number): number {
  if (zone < 0 || zone >= PLINKO_ZONES) {
    throw new Error(`Invalid zone: ${zone}. Must be 0-${PLINKO_ZONES - 1}`);
  }
  return PLINKO_MULTIPLIERS[zone];
}

/**
 * Calculate the adjusted multiplier with house edge.
 * @param zone - Landing zone (0-12)
 * @param houseEdge - House edge (default 3%)
 * @returns Adjusted multiplier
 */
export function getPlinkoAdjustedMultiplier(zone: number, houseEdge: number = PLINKO_BASE_HOUSE_EDGE): number {
  const rawMultiplier = getPlinkoMultiplier(zone);
  return rawMultiplier * (1 - houseEdge);
}

/**
 * Calculate win probability for a given zone.
 * This is based on binomial distribution: C(12, k) * (0.5)^12
 * @param zone - Landing zone (0-12)
 * @returns Probability percentage (0-100)
 */
export function getPlinkoZoneProbability(zone: number): number {
  if (zone < 0 || zone >= PLINKO_ZONES) {
    throw new Error(`Invalid zone: ${zone}`);
  }
  // Binomial coefficient C(12, zone) * (1/2)^12
  const combinations = binomialCoefficient(PLINKO_ROWS, zone);
  const probability = combinations / Math.pow(2, PLINKO_ROWS);
  return probability * 100;
}

/**
 * Calculate expected ROI for a bet on a specific zone.
 * ROI = (multiplier * probability) - 1
 */
export function getPlinkoExpectedROI(zone: number, houseEdge: number = PLINKO_BASE_HOUSE_EDGE): number {
  const multiplier = getPlinkoAdjustedMultiplier(zone, houseEdge);
  const probability = getPlinkoZoneProbability(zone) / 100;
  return (multiplier * probability) - 1;
}

/**
 * Calculate payout amount in nanoERG.
 */
export function calculatePlinkoPayout(betNanoErg: number, zone: number, houseEdge: number = PLINKO_BASE_HOUSE_EDGE): number {
  const multiplier = getPlinkoAdjustedMultiplier(zone, houseEdge);
  return Math.floor(betNanoErg * multiplier);
}

/**
 * Get all zones with their multipliers and probabilities.
 * Useful for displaying the Plinko board.
 */
export function getPlinkoZones(): Array<{ zone: number; multiplier: number; probability: number }> {
  return Array.from({ length: PLINKO_ZONES }, (_, zone) => ({
    zone,
    multiplier: getPlinkoAdjustedMultiplier(zone),
    probability: getPlinkoZoneProbability(zone),
  }));
}

// ─── Commitment Scheme ─────────────────────────────────────────

/**
 * Generate a commitment for a Plinko bet.
 * commitment = SHA256(secret_2_bytes)
 *
 * We use 2 bytes of random secret to generate 16 bits (we need 12 bits for the rows).
 * The secret is stored in R7 and will be revealed later.
 *
 * @returns { secret, commitment } both as hex strings
 */
export async function generatePlinkoCommit(
  secret?: Uint8Array,
): Promise<{ secret: Uint8Array; commitment: string }> {
  // Generate 2 bytes of random secret (16 bits, we need 12)
  const actualSecret = secret || generateSecret();

  // Commitment = SHA256(secret)
  const commitHash = await sha256(actualSecret);
  return {
    secret: actualSecret,
    commitment: bytesToHex(commitHash),
  };
}

/**
 * Verify a Plinko commitment.
 */
export async function verifyPlinkoCommit(
  commitmentHex: string,
  secretBytes: Uint8Array,
): Promise<boolean> {
  const { commitment } = await generatePlinkoCommit(secretBytes);
  return commitment.toLowerCase() === commitmentHex.toLowerCase();
}

// ─── RNG ───────────────────────────────────────────────────────

/**
 * Compute Plinko RNG outcome from block hash and player secret.
 *
 * 1. Compute combined hash = SHA256(blockHash_as_utf8 || secret_bytes)
 * 2. Extract first 12 bits (1.5 bytes) from hash
 * 3. Count number of set bits = number of "right" bounces = landing zone
 *
 * Returns a landing zone (0-12).
 *
 * Note: Uses the SAME block hash encoding as coinflip (UTF-8 string)
 * for consistency and shared RNG infrastructure.
 */
export async function computePlinkoRng(
  blockHash: string,
  secretBytes: Uint8Array,
): Promise<number> {
  const blockHashBuffer = new TextEncoder().encode(blockHash);

  const rngInput = new Uint8Array(blockHashBuffer.length + secretBytes.length);
  rngInput.set(blockHashBuffer, 0);
  rngInput.set(secretBytes, blockHashBuffer.length);

  const rngHash = await sha256(rngInput);

  // Extract first 12 bits (1.5 bytes) from hash
  // We'll use the first 2 bytes (16 bits) but only use the first 12
  const byte1 = rngHash[0];
  const byte2 = rngHash[1];

  // Extract 12 bits: first 8 bits from byte1, first 4 bits from byte2
  const bits: number[] = [];
  for (let i = 0; i < 8; i++) {
    bits.push((byte1 >> i) & 1);
  }
  for (let i = 0; i < 4; i++) {
    bits.push((byte2 >> i) & 1);
  }

  // Count number of set bits = number of "right" bounces = landing zone
  const zone = bits.filter(bit => bit === 1).length;

  return zone;
}

/**
 * Get the path for animation.
 * Returns an array of "left" or "right" for each row.
 */
export async function getPlinkoPath(
  blockHash: string,
  secretBytes: Uint8Array,
): Promise<Array<'left' | 'right'>> {
  const blockHashBuffer = new TextEncoder().encode(blockHash);

  const rngInput = new Uint8Array(blockHashBuffer.length + secretBytes.length);
  rngInput.set(blockHashBuffer, 0);
  rngInput.set(secretBytes, blockHashBuffer.length);

  const rngHash = await sha256(rngInput);

  // Extract first 12 bits
  const byte1 = rngHash[0];
  const byte2 = rngHash[1];

  const path: Array<'left' | 'right'> = [];
  for (let i = 0; i < 8; i++) {
    const bit = (byte1 >> i) & 1;
    path.push(bit === 1 ? 'right' : 'left');
  }
  for (let i = 0; i < 4; i++) {
    const bit = (byte2 >> i) & 1;
    path.push(bit === 1 ? 'right' : 'left');
  }

  return path;
}

/**
 * Determine if the player won the Plinko bet.
 * Player wins if the ball lands in a zone with multiplier > 1.
 */
export function isPlinkoWin(zone: number): boolean {
  return getPlinkoMultiplier(zone) > 1;
}

// ─── Sigma-State Serialization Helpers ─────────────────────────

/**
 * Encode an integer as an ErgoScript IntConstant SValue hex.
 * Used for bet configuration in R6 if needed.
 */
export function encodeIntConstant(value: number): string {
  const zigzag = (value << 1) ^ (value >> 31);
  const unsigned = zigzag >>> 0;
  const vlq = encodeVLQ(unsigned);
  return `02${vlq}`;
}

/**
 * Encode a bigint as an ErgoScript LongConstant SValue hex.
 * Used for player secret in R7.
 */
export function encodeLongConstant(value: bigint): string {
  const zigzag = Number((value << 1n) ^ (value >> 63n));
  const vlq = encodeVLQBigInt(BigInt.asUintN(64, BigInt(zigzag)));
  return `04${vlq}`;
}

/**
 * Encode bytes as an ErgoScript Coll[Byte] SValue hex.
 * Format: 0e 01 VLQ(len) rawBytes
 */
export function encodeCollByte(hexData: string): string {
  const data = hexToBytes(hexData);
  const len = data.length;
  return `0e01${encodeVLQ(len)}${hexData}`;
}

/**
 * Encode a UTF-8 string as Coll[Byte].
 */
export function encodeStringAsCollByte(str: string): string {
  const bytes = new TextEncoder().encode(str);
  return `0e01${encodeVLQ(bytes.length)}${bytesToHex(bytes)}`;
}

// ─── Internal Helpers ─────────────────────────────────────────

/**
 * Calculate binomial coefficient C(n, k).
 */
function binomialCoefficient(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;

  let result = 1;
  for (let i = 0; i < Math.min(k, n - k); i++) {
    result = (result * (n - i)) / (i + 1);
  }

  return Math.round(result);
}

/**
 * Encode unsigned integer as VLQ hex string.
 */
function encodeVLQ(value: number): string {
  if (value === 0) return '00';
  const bytes: number[] = [];
  let remaining = value >>> 0; // unsigned 32-bit
  while (remaining > 0) {
    let byte = remaining & 0x7f;
    remaining >>>= 7;
    if (remaining > 0) byte |= 0x80;
    bytes.push(byte);
  }
  return bytes.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Encode bigint as VLQ hex string.
 */
function encodeVLQBigInt(value: bigint): string {
  if (value === 0n) return '00';
  const bytes: number[] = [];
  let remaining = value;
  while (remaining > 0n) {
    let byte = Number(remaining & 0x7fn);
    remaining >>= 7n;
    if (remaining > 0n) byte |= 0x80;
    bytes.push(byte);
  }
  return bytes.map(b => b.toString(16).padStart(2, '0')).join('');
}
