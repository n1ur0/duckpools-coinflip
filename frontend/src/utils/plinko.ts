/**
 * DuckPools Plinko Game Utilities
 *
 * Plinko uses the same commit-reveal architecture as coinflip/dice with:
 * - Ball drops through rows of pegs (binomial distribution)
 * - Landing slot determines payout multiplier
 * - Higher-risk outer slots = higher multiplier, center slots = lower multiplier
 * - Player chooses number of rows (risk level) and bet amount
 *
 * Mathematical Model:
 * - For n rows, there are n+1 slots (indexed 0 to n)
 * - Slot k probability follows binomial distribution: P(k) = C(n, k) / 2^n
 * - Multiplier for slot k uses power-law parameterization:
 *     multiplier(k) = A * (1/P(k))^alpha
 *   where A = (1 - house_edge) / sum(P(j)^(1-alpha))
 * - Expected value: E[X] = sum(P(k) * multiplier(k)) = 1 - house_edge
 * - alpha controls risk/reward curve (0.5 = balanced, 0.7 = high risk)
 * - This ensures the house edge is exactly the stated edge regardless of rows
 */

import { sha256, bytesToHex, generateSecret } from './crypto';

// ─── Constants ─────────────────────────────────────────────────

/** Minimum number of rows (safest) */
export const PLINKO_MIN_ROWS = 8;

/** Maximum number of rows (riskiest) */
export const PLINKO_MAX_ROWS = 16;

/** Default number of rows */
export const PLINKO_DEFAULT_ROWS = 12;

/** House edge (3%) */
export const PLINKO_HOUSE_EDGE = 0.03;

// ─── Mathematical Functions ───────────────────────────────────

/**
 * Calculate binomial coefficient C(n, k) = n! / (k! * (n-k)!)
 * Used to compute slot probabilities in Plinko.
 */
export function binomialCoefficient(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;

  // Use iterative calculation to avoid large factorials
  let result = 1;
  for (let i = 0; i < Math.min(k, n - k); i++) {
    result = result * (n - i) / (i + 1);
  }
  return result;
}

/**
 * Calculate the probability of landing in slot k given n rows.
 * P(k) = C(n, k) / 2^n
 *
 * @param rows - Number of rows (8-16)
 * @param slot - Slot index (0 to rows)
 */
export function getPlinkoSlotProbability(rows: number, slot: number): number {
  if (slot < 0 || slot > rows) {
    throw new Error(`Slot ${slot} out of range for ${rows} rows (must be 0-${rows})`);
  }

  const n = rows;
  const k = slot;

  // P(k) = C(n, k) / 2^n
  return binomialCoefficient(n, k) / Math.pow(2, n);
}

/**
 * Calculate payout multiplier for a slot.
 *
 * Uses a power-law parameterization to create an exciting risk/reward curve
 * while maintaining the exact house edge:
 *
 *   multiplier(k) = A * (1/P(k))^alpha
 *
 * where A = (1 - house_edge) / sum(P(j)^(1-alpha))
 *
 * This ensures: E[X] = sum(P(k) * multiplier(k)) = (1 - house_edge)
 *
 * For alpha=0.5: edge multipliers ~21x, center ~0.7x (balanced)
 * For alpha=0.7: edge multipliers ~68x, center ~0.57x (high risk)
 *
 * @param rows - Number of rows
 * @param slot - Slot index
 */
export function getPlinkoSlotMultiplier(rows: number, slot: number): number {
  const probability = getPlinkoSlotProbability(rows, slot);
  const alpha = 0.5; // Risk parameter: 0.5 = balanced, 0.7 = high risk

  // Pre-compute normalization constant for this row count
  let denom = 0;
  for (let s = 0; s <= rows; s++) {
    denom += Math.pow(getPlinkoSlotProbability(rows, s), 1 - alpha);
  }

  const A = (1 - PLINKO_HOUSE_EDGE) / denom;
  return A * Math.pow(1 / probability, alpha);
}

/**
 * Calculate payout amount in nanoERG from bet amount and slot.
 *
 * @param betNanoErg - Bet amount in nanoERG
 * @param rows - Number of rows
 * @param slot - Landing slot
 */
export function calculatePlinkoPayout(betNanoErg: number, rows: number, slot: number): number {
  const multiplier = getPlinkoSlotMultiplier(rows, slot);
  return Math.floor(betNanoErg * multiplier);
}

// ─── Expected Return Calculation (FIXED) ────────────────────

/**
 * Compute the expected return for Plinko using PROBABILITY-WEIGHTED sum.
 *
 * E[X] = sum(P(k) * multiplier(k)) for all slots k
 *      = sum(P(k) * A * (1/P(k))^alpha)
 *      = A * sum(P(k)^(1-alpha))
 *      = (1 - house_edge) / sum(P(j)^(1-alpha)) * sum(P(k)^(1-alpha))
 *      = (1 - house_edge)
 *
 * This returns the expected payout amount, not the edge.
 * The house edge is: 1 - (expected_payout / bet) = house_edge
 *
 * @param betNanoErg - Bet amount in nanoERG
 * @param rows - Number of rows
 * @returns Expected payout in nanoERG
 */
export function computePlinkoExpectedReturn(betNanoErg: number, rows: number): number {
  let expectedPayout = 0;

  // CORRECT: Probability-weighted sum
  for (let slot = 0; slot <= rows; slot++) {
    const probability = getPlinkoSlotProbability(rows, slot);
    const multiplier = getPlinkoSlotMultiplier(rows, slot);
    const payout = betNanoErg * multiplier;

    // Weight each payout by its probability
    expectedPayout += probability * payout;
  }

  return Math.floor(expectedPayout);
}

/**
 * Get the theoretical RTP (Return to Player) for Plinko.
 *
 * RTP = (expected_payout / bet) * 100
 *     = (1 - house_edge) * 100
 *
 * For a 3% house edge, RTP = 97%
 *
 * @returns RTP as percentage (e.g., 97.0 for 3% house edge)
 */
export function getPlinkoRTP(): number {
  return (1 - PLINKO_HOUSE_EDGE) * 100;
}

/**
 * Get all slot multipliers for a given row count.
 * Returns an array where index = slot number, value = multiplier.
 *
 * @param rows - Number of rows
 */
export function getPlinkoMultiplierTable(rows: number): number[] {
  const multipliers: number[] = [];

  for (let slot = 0; slot <= rows; slot++) {
    multipliers.push(getPlinkoSlotMultiplier(rows, slot));
  }

  return multipliers;
}

/**
 * Get all slot probabilities for a given row count.
 * Returns an array where index = slot number, value = probability.
 *
 * @param rows - Number of rows
 */
export function getPlinkoProbabilityTable(rows: number): number[] {
  const probabilities: number[] = [];

  for (let slot = 0; slot <= rows; slot++) {
    probabilities.push(getPlinkoSlotProbability(rows, slot));
  }

  return probabilities;
}

// ─── Commitment Scheme ─────────────────────────────────────────

/**
 * Generate a commitment for a Plinko bet.
 * commitment = SHA256(secret_8_bytes || rows_byte || target_slot_byte)
 *
 * @param rows - Number of rows (8-16)
 * @param targetSlot - Optional target slot (for future betting on specific slots)
 * @param secret - Optional custom secret (8 bytes)
 * @returns { secret, commitment } both as hex strings
 */
export async function generatePlinkoCommit(
  rows: number,
  targetSlot?: number,
  secret?: Uint8Array,
): Promise<{ secret: Uint8Array; commitment: string }> {
const actualSecret = secret ?? generateSecret();

  // Encode rows as a single byte (fits 8-16)
  const rowsByte = new Uint8Array(1);
  rowsByte[0] = rows & 0xff;

  // Encode target slot as a single byte (0-16, fits 0-255)
  const targetByte = new Uint8Array(1);
  targetByte[0] = (targetSlot ?? 0) & 0xff;

  // Commitment = SHA256(secret || rows_byte || target_slot_byte)
  const commitInput = new Uint8Array(actualSecret.length + 2);
  commitInput.set(actualSecret, 0);
  commitInput.set(rowsByte, actualSecret.length);
  commitInput.set(targetByte, actualSecret.length + 1);

  const commitHash = await sha256(commitInput);
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
  rows: number,
  targetSlot?: number,
): Promise<boolean> {
  const { commitment } = await generatePlinkoCommit(rows, targetSlot, secretBytes);
  return commitment.toLowerCase() === commitmentHex.toLowerCase();
}

// ─── RNG ───────────────────────────────────────────────────────

/**
 * Compute Plinko RNG outcome from block hash and player secret.
 * The ball's path through pegs is determined by a pseudo-random walk.
 *
 * Algorithm:
 * - For each row, determine if ball goes left (0) or right (1)
 * - Use successive bytes from SHA256(blockHash || secret)
 * - The slot is determined by counting right turns (1s)
 *
 * outcome = count of 1s in first 'rows' bytes
 *
 * Note: This maps perfectly to the binomial distribution since
 * each byte has equal probability of 0 or 1, and we count successes.
 *
 * @param blockHash - Ergo block hash
 * @param secretBytes - Player's secret (8 bytes)
 * @param rows - Number of rows
 * @returns Slot index (0 to rows)
 */
export async function computePlinkoRng(
  blockHash: string,
  secretBytes: Uint8Array,
  rows: number,
): Promise<number> {
  const blockHashBuffer = new TextEncoder().encode(blockHash);

  // Generate enough random bytes: need 'rows' bytes for the path
  const rngInput = new Uint8Array(blockHashBuffer.length + secretBytes.length);
  rngInput.set(blockHashBuffer, 0);
  rngInput.set(secretBytes, blockHashBuffer.length);

  const rngHash = await sha256(rngInput);

  // Count 1s in the first 'rows' bytes
  // Each byte's LSB determines left (0) or right (1)
  let slot = 0;
  for (let i = 0; i < rows; i++) {
    if (rngHash[i % rngHash.length] & 0x01) {
      slot++;
    }
  }

  // Slot ranges from 0 to rows
  return Math.min(slot, rows);
}

// ─── Sigma-State Serialization Helpers ─────────────────────────

/**
 * Encode rows as an ErgoScript IntConstant SValue hex.
 */
export function encodePlinkoRows(rows: number): string {
  const zigzag = (rows << 1) ^ (rows >> 31);
  const unsigned = zigzag >>> 0;
  const vlq = encodeVLQ(unsigned);
  return `02${vlq}`;
}

/**
 * Encode target slot as an ErgoScript IntConstant SValue hex.
 */
export function encodePlinkoSlot(slot: number): string {
  const zigzag = (slot << 1) ^ (slot >> 31);
  const unsigned = zigzag >>> 0;
  const vlq = encodeVLQ(unsigned);
  return `02${vlq}`;
}

/**
 * Encode player secret as an ErgoScript LongConstant SValue hex.
 */
export function encodePlinkoSecret(secret: Uint8Array): string {
  // Convert 8 bytes to bigint
  const value = BigInt('0x' + bytesToHex(secret));
  const zigzag = Number((value << 1n) ^ (value >> 63n));
  const vlq = encodeVLQBigInt(BigInt.asUintN(64, BigInt(zigzag)));
  return `04${vlq}`;
}

// ─── Internal VLQ helpers ──────────────────────────────────────

function encodeVLQ(value: number): string {
  if (value === 0) return '00';
  const bytes: number[] = [];
  let remaining = value >>> 0;
  while (remaining > 0) {
    let byte = remaining & 0x7f;
    remaining >>>= 7;
    if (remaining > 0) byte |= 0x80;
    bytes.push(byte);
  }
  return bytes.map(b => b.toString(16).padStart(2, '0')).join('');
}

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
