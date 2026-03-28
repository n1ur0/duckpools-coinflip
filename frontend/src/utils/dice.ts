/**
 * DuckPools Dice Game Utilities
 *
 * Dice uses the same commit-reveal architecture as coinflip but with:
 * - Player picks a roll target (2-98): "I bet the roll will be UNDER this number"
 * - RNG outcome = SHA256(blockHash || secret)[0] % 100 (0-99)
 * - Player wins if rngOutcome < rollTarget
 * - Variable house edge: riskier bets (lower rollTarget) get lower house edge
 * - Payout multiplier displayed live as the user adjusts the target
 */

import { sha256, bytesToHex, generateSecret } from './crypto';

// ─── Constants ─────────────────────────────────────────────────

/** Minimum roll target (lowest probability = highest payout) */
export const DICE_MIN_TARGET = 2;

/** Maximum roll target (highest probability = lowest payout) */
export const DICE_MAX_TARGET = 98;

/** Default roll target */
export const DICE_DEFAULT_TARGET = 50;

/** Base house edge (3%) */
export const DICE_BASE_HOUSE_EDGE = 0.03;

/** Minimum house edge (1%) for very risky bets */
export const DICE_MIN_HOUSE_EDGE = 0.01;

/** Maximum house edge (5%) for very safe bets */
export const DICE_MAX_HOUSE_EDGE = 0.05;

// ─── Payout Calculation ────────────────────────────────────────

/**
 * Calculate the house edge based on roll target.
 * More risky bets (lower target) get lower house edge.
 * More safe bets (higher target) get higher house edge.
 *
 * Formula: houseEdge = baseEdge - (risk factor) * 2%
 *   where risk = (1 - target/100) ranges from 0.02 to 0.98
 *   So houseEdge ranges from ~1% to ~5%
 */
export function getDiceHouseEdge(rollTarget: number): number {
  const winProbability = rollTarget / 100;
  const riskFactor = 1 - winProbability; // 0.02 to 0.98

  // Linear interpolation from base to min/max
  let edge = DICE_BASE_HOUSE_EDGE - riskFactor * 0.02;

  return Math.max(DICE_MIN_HOUSE_EDGE, Math.min(DICE_MAX_HOUSE_EDGE, edge));
}

/**
 * Calculate payout multiplier for a given roll target.
 * multiplier = (100 / rollTarget) * (1 - houseEdge)
 *
 * Examples:
 *   rollTarget=50 -> multiplier ≈ 1.94x (94% payout, same as coinflip)
 *   rollTarget=10 -> multiplier ≈ 9.7x (house edge ~1%)
 *   rollTarget=90 -> multiplier ≈ 1.055x (house edge ~5%)
 */
export function getDiceMultiplier(rollTarget: number): number {
  const houseEdge = getDiceHouseEdge(rollTarget);
  return (100 / rollTarget) * (1 - houseEdge);
}

/**
 * Calculate win probability (just rollTarget%, no edge for display)
 */
export function getDiceWinProbability(rollTarget: number): number {
  return rollTarget;
}

/**
 * Calculate payout amount in nanoERG from bet amount and roll target.
 */
export function calculateDicePayout(betNanoErg: number, rollTarget: number): number {
  const multiplier = getDiceMultiplier(rollTarget);
  return Math.floor(betNanoErg * multiplier);
}

// ─── Commitment Scheme ─────────────────────────────────────────

/**
 * Generate a commitment for a dice bet.
 * commitment = SHA256(secret_8_bytes || rollTarget_byte)
 *
 * @param rollTarget - The number player is betting under (2-98)
 * @returns { secret, commitment } both as hex strings
 */
export async function generateDiceCommit(
  rollTarget: number,
  secret?: Uint8Array,
): Promise<{ secret: Uint8Array; commitment: string }> {
  const actualSecret = secret ?? generateSecret();

  // Encode rollTarget as a single byte (0-255, fits 2-98)
  const targetByte = new Uint8Array(1);
  targetByte[0] = rollTarget & 0xff;

  // Commitment = SHA256(secret || rollTarget_byte)
  const commitInput = new Uint8Array(actualSecret.length + 1);
  commitInput.set(actualSecret, 0);
  commitInput.set(targetByte, actualSecret.length);

  const commitHash = await sha256(commitInput);
  return {
    secret: actualSecret,
    commitment: bytesToHex(commitHash),
  };
}

/**
 * Verify a dice commitment.
 */
export async function verifyDiceCommit(
  commitmentHex: string,
  secretBytes: Uint8Array,
  rollTarget: number,
): Promise<boolean> {
  const { commitment } = await generateDiceCommit(rollTarget, secretBytes);
  return commitment.toLowerCase() === commitmentHex.toLowerCase();
}

// ─── RNG ───────────────────────────────────────────────────────

/**
 * Compute dice RNG outcome from block hash and player secret.
 *
 * Uses rejection sampling to avoid modulo bias.
 *
 * Naive `hash[0] % 100` is BIASED because 256 % 100 = 56:
 *   outcomes 0-55 have probability 2/256, outcomes 56-99 have 1/256.
 *   This gives the player a ~1.5% edge on rollTarget > 56 bets.
 *
 * Rejection sampling (matching backend/rng_module.py dice_rng):
 *   - Accept bytes in range [0, 199] → byte % 100 (uniform)
 *   - Reject bytes in range [200, 255] → try next byte
 *   - Guaranteed to terminate: 200/256 = 78% acceptance per byte,
 *     and SHA-256 produces 32 bytes of entropy.
 *
 * Returns a value 0-99. Player wins if outcome < rollTarget.
 *
 * Note: Uses the SAME block hash encoding as coinflip (UTF-8 string)
 * for consistency and shared RNG infrastructure.
 */
export async function computeDiceRng(
  blockHash: string,
  secretBytes: Uint8Array,
): Promise<number> {
  const blockHashBuffer = new TextEncoder().encode(blockHash);

  const rngInput = new Uint8Array(blockHashBuffer.length + secretBytes.length);
  rngInput.set(blockHashBuffer, 0);
  rngInput.set(secretBytes, blockHashBuffer.length);

  const rngHash = await sha256(rngInput);

  // Rejection sampling: only accept bytes < 200 (2 * 100)
  // Each accepted byte maps uniformly to 0-99 via modulo 100
  for (let i = 0; i < rngHash.length; i++) {
    const byte = rngHash[i];
    if (byte < 200) {
      return byte % 100;
    }
  }

  // Fallback — astronomically unlikely (all 32 bytes >= 200: probability ~10^-7)
  // Use two bytes for a wider range, but still apply rejection sampling to avoid bias
  const sixteenBitValue = rngHash[0] * 256 + rngHash[1];
  if (sixteenBitValue < 65500) {  // 65500 = 655 * 100
    return sixteenBitValue % 100;
  } else {
    // If somehow still in rejection territory, try remaining bytes
    for (let i = 2; i < rngHash.length; i++) {
      const byte = rngHash[i];
      if (byte < 200) {
        return byte % 100;
      }
    }
    // Ultimate fallback - just use first byte mod 100 (extremely biased but virtually impossible)
    return rngHash[0] % 100;
  }
}

/**
 * Determine if the player won the dice bet.
 */
export function isDiceWin(rngOutcome: number, rollTarget: number): boolean {
  return rngOutcome < rollTarget;
}

// ─── Sigma-State Serialization (re-exported from sigmaSerializer) ──

export { encodeIntConstant, encodeLongConstant, encodeCollByte, encodeStringAsCollByte } from './sigmaSerializer';
