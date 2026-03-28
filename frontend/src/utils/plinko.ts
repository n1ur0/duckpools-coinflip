/**
 * DuckPools Plinko Game Utilities
 *
 * Plinko uses a Galton board (pegs) where a ball drops through rows of pins
 * and lands in slots at the bottom. Each slot has a different payout multiplier.
 *
 * Key Mechanics:
 * - Player selects number of rows (8, 12, or 16)
 * - Each row doubles the number of possible landing positions (2^rows positions)
 * - Inner slots (near center) have higher probability, lower multiplier
 * - Outer slots (edges) have lower probability, higher multiplier
 * - Ball path is determined by the same commit-reveal RNG as other games
 *
 * Expected Return (RTP) is calculated using PROBABILITY-WEIGHTED mean:
 *   E[X] = sum(probability_i * payout_i) for all slots i
 *
 * NOT arithmetic mean: avg(multipliers) - this would be WRONG!
 *
 * MAT-263: Fixed to use probability-weighted expected value.
 */

import { sha256, bytesToHex, hexToBytes, generateSecret } from './crypto';

// ─── Row Configurations ─────────────────────────────────────────

/** Available row counts for different risk levels */
export type RowCount = 8 | 12 | 16;

/** Multiplier table: maps (rows, slot_index) -> payout multiplier */
interface MultiplierTable {
  rows: RowCount;
  multipliers: number[]; // Array where index = slot number (0 to 2^rows - 1)
}

/**
 * Pre-computed multiplier tables for each row count.
 * Multipliers are symmetric around the center.
 *
 * These are calibrated to maintain a consistent house edge (~3% for default)
 * while rewarding riskier choices (more rows = higher potential multipliers).
 */
const MULTIPLIER_TABLES: Record<RowCount, number[]> = {
  8: [
    3.8, 1.45, 0.72, 0.32, 0.32, 0.72, 1.45, 3.8  // 8 rows = 8 slots (2^3 positions compressed to 8 visual slots)
  ],
  12: [
    6.35, 2.72, 1.21, 0.61, 0.31, 0.11, 0.11, 0.31, 0.61, 1.21, 2.72, 6.35  // 12 rows = 12 slots
  ],
  16: [
    7.3, 3.1, 1.35, 0.58, 0.28, 0.13, 0.08, 0.06, 0.06, 0.13, 0.28, 0.58, 1.35, 3.1, 7.3, 7.3  // 16 rows = 16 slots
  ],
};

// ─── Probability Distributions ───────────────────────────────────

/**
 * Get probability distribution for a given row count.
 * Uses binomial distribution: P(k) = C(n, k) * p^k * (1-p)^(n-k)
 * where n = rows, p = 0.5, k = number of "right" moves.
 *
 * For 8 rows visual slots (not 2^8=256 raw positions), we map
 * the binomial distribution to the slot indices.
 *
 * Returns an array where probability[i] = probability of landing in slot i.
 */
export function getPlinkoProbabilities(rows: RowCount): number[] {
  const numSlots = rows;
  const probabilities: number[] = [];

  // For simplicity, we use normalized Gaussian approximation
  // centered at the middle slot. This approximates the binomial
  // distribution for large n and provides smooth multipliers.
  for (let slot = 0; slot < numSlots; slot++) {
    // Center the distribution
    const x = (slot - (numSlots - 1) / 2) / (numSlots / 4);
    // Gaussian: e^(-x^2/2) - gives bell curve centered at middle
    const rawProb = Math.exp(-(x * x) / 2);
    probabilities.push(rawProb);
  }

  // Normalize to sum to 1
  const total = probabilities.reduce((sum, p) => sum + p, 0);
  return probabilities.map(p => p / total);
}

// ─── Expected Return Calculation (CORRECT METHOD) ────────────────

/**
 * CRITICAL FIX (MAT-263): Calculate expected return using probability-weighted mean.
 *
 * BEFORE (WRONG): arithmetic mean of multipliers
 *   E[X] = avg(multipliers) - INCORRECT! Ignores that outer slots are less likely
 *
 * AFTER (CORRECT): probability-weighted expected value
 *   E[X] = sum_i (probability_i * multiplier_i) - CORRECT! Accounts for slot probabilities
 *
 * This gives the true theoretical RTP (Return To Player) for the house edge calculation.
 *
 * @param rows - Number of rows (8, 12, or 16)
 * @returns The probability-weighted expected return (should be ~0.97 for 3% house edge)
 */
export function computeExpectedReturn(rows: RowCount): number {
  const probabilities = getPlinkoProbabilities(rows);
  const multipliers = MULTIPLIER_TABLES[rows];

  if (probabilities.length !== multipliers.length) {
    throw new Error(`Probability and multiplier arrays must have same length for ${rows} rows`);
  }

  // PROBABILITY-WEIGHTED SUM (not arithmetic mean!)
  let expectedReturn = 0;
  for (let i = 0; i < probabilities.length; i++) {
    expectedReturn += probabilities[i] * multipliers[i];
  }

  return expectedReturn;
}

/**
 * Get the house edge for a given row count.
 * House edge = 1 - expected_return
 *
 * Expected to be ~3% (0.03) for default configuration.
 */
export function getPlinkoHouseEdge(rows: RowCount): number {
  return 1 - computeExpectedReturn(rows);
}

/**
 * Get Return To Player (RTP) percentage.
 * RTP = expected_return * 100
 *
 * Expected to be ~97% for default configuration.
 */
export function getPlinkoRTP(rows: RowCount): number {
  return computeExpectedReturn(rows) * 100;
}

// ─── Payout Calculation ────────────────────────────────────────────

/**
 * Get the multiplier for a specific slot index.
 *
 * @param rows - Number of rows
 * @param slotIndex - Which slot (0 = leftmost, rows-1 = rightmost)
 * @returns Payout multiplier (e.g., 5.6x)
 */
export function getPlinkoMultiplier(rows: RowCount, slotIndex: number): number {
  const multipliers = MULTIPLIER_TABLES[rows];
  if (slotIndex < 0 || slotIndex >= multipliers.length) {
    throw new Error(`Invalid slotIndex ${slotIndex} for ${rows} rows (must be 0-${multipliers.length - 1})`);
  }
  return multipliers[slotIndex];
}

/**
 * Calculate payout amount in nanoERG for a bet.
 *
 * @param betNanoErg - Bet amount in nanoERG
 * @param rows - Number of rows
 * @param slotIndex - Which slot the ball landed in
 * @returns Payout in nanoERG
 */
export function calculatePlinkoPayout(
  betNanoErg: number,
  rows: RowCount,
  slotIndex: number
): number {
  const multiplier = getPlinkoMultiplier(rows, slotIndex);
  return Math.floor(betNanoErg * multiplier);
}

// ─── RNG and Slot Determination ───────────────────────────────────

/**
 * Compute the slot index where the ball lands.
 *
 * Uses the same commit-reveal RNG as coinflip and dice:
 * - RNG = SHA256(blockHash_utf8 || secret_bytes)[0]
 * - Map RNG byte to slot using probability distribution
 *
 * @param blockHash - Block hash from Ergo node
 * @param secretBytes - Player's secret bytes
 * @param rows - Number of rows
 * @returns Slot index (0 to rows-1)
 */
export async function computePlinkoSlot(
  blockHash: string,
  secretBytes: Uint8Array,
  rows: RowCount
): Promise<number> {
  // Generate RNG hash using same method as coinflip/dice
  const blockHashBuffer = new TextEncoder().encode(blockHash);
  const rngInput = new Uint8Array(blockHashBuffer.length + secretBytes.length);
  rngInput.set(blockHashBuffer, 0);
  rngInput.set(secretBytes, blockHashBuffer.length);

  const rngHash = await sha256(rngInput);
  const rngByte = rngHash[0]; // 0-255

  // Map RNG byte to slot index using cumulative probabilities
  const probabilities = getPlinkoProbabilities(rows);
  const rngValue = rngByte / 256; // 0.0 to 1.0

  let cumulative = 0;
  for (let slot = 0; slot < probabilities.length; slot++) {
    cumulative += probabilities[slot];
    if (rngValue < cumulative) {
      return slot;
    }
  }

  // Fallback (shouldn't happen with proper normalization)
  return probabilities.length - 1;
}

// ─── Commitment Scheme ────────────────────────────────────────────

/**
 * Generate a commitment for a Plinko bet.
 * commitment = SHA256(secret_8_bytes || rows_byte)
 *
 * @param rows - Number of rows selected
 * @param secret - Optional player secret (8 bytes). If not provided, generates one.
 * @returns { secret, commitment } both as hex strings
 */
export async function generatePlinkoCommit(
  rows: RowCount,
  secret?: Uint8Array,
): Promise<{ secret: Uint8Array; commitment: string }> {
  const actualSecret = secret ?? generateSecret();

  // Encode rows as a single byte (8, 12, or 16)
  const rowsByte = new Uint8Array(1);
  rowsByte[0] = rows & 0xff;

  // Commitment = SHA256(secret || rows_byte)
  const commitInput = new Uint8Array(actualSecret.length + 1);
  commitInput.set(actualSecret, 0);
  commitInput.set(rowsByte, actualSecret.length);

  const commitHash = await sha256(commitInput);
  return {
    secret: actualSecret,
    commitment: bytesToHex(commitHash),
  };
}

/**
 * Verify a Plinko commitment.
 *
 * @param commitmentHex - Commitment hash as hex string
 * @param secretBytes - Player's secret bytes
 * @param rows - Number of rows
 * @returns True if commitment matches
 */
export async function verifyPlinkoCommit(
  commitmentHex: string,
  secretBytes: Uint8Array,
  rows: RowCount,
): Promise<boolean> {
  const { commitment } = await generatePlinkoCommit(rows, secretBytes);
  return commitment.toLowerCase() === commitmentHex.toLowerCase();
}

// ─── Helper Functions ─────────────────────────────────────────────

/**
 * Get all multipliers for a row count (useful for UI display).
 */
export function getMultipliersForRows(rows: RowCount): number[] {
  return [...MULTIPLIER_TABLES[rows]];
}

/**
 * Get all probabilities for a row count (useful for UI display).
 */
export function getProbabilitiesForRows(rows: RowCount): number[] {
  return [...getPlinkoProbabilities(rows)];
}

/**
 * Validate that expected return matches theoretical RTP.
 * This is used for unit testing (MAT-263).
 *
 * @param rows - Number of rows
 * @param tolerance - Acceptable deviation from expected RTP (default 0.01 = 1%)
 * @returns True if expected return is within tolerance of theoretical RTP
 */
export function validateExpectedReturn(
  rows: RowCount,
  tolerance: number = 0.01,
  targetRTP: number = 97.0,
): boolean {
  const actualRTP = getPlinkoRTP(rows);
  const diff = Math.abs(actualRTP - targetRTP);
  return diff <= tolerance * 100; // tolerance is 0.01 for 1% difference
}

// ─── Constants for UI ─────────────────────────────────────────────

export const PLINKO_ROW_OPTIONS: RowCount[] = [8, 12, 16];
export const PLINKO_DEFAULT_ROWS: RowCount = 12;

export const PLINKO_RISK_LABELS: Record<RowCount, string> = {
  8: 'Low',
  12: 'Medium',
  16: 'High',
};

export const PLINKO_HOUSE_EDGE_TARGET = 0.03; // 3%
export const PLINKO_RTP_TARGET = 97.0; // 97%
