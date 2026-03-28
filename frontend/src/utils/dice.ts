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

import { sha256, bytesToHex, hexToBytes, generateSecret } from './crypto';

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
 * outcome = rejection sampling from SHA256(blockHash_as_utf8 || secret_bytes)
 *
 * Returns a value 0-99. Player wins if outcome < rollTarget.
 *
 * Note: Uses the SAME block hash encoding as coinflip (UTF-8 string)
 * for consistency and shared RNG infrastructure.
 * 
 * IMPORTANT: Uses rejection sampling to avoid modulo bias. Since 256 is not
 * divisible by 100, we reject values >= 200 and retry with more entropy.
 */
export async function computeDiceRng(
  blockHash: string,
  secretBytes: Uint8Array,
): Promise<number> {
  const blockHashBuffer = new TextEncoder().encode(blockHash);

  // Initial RNG input
  let rngInput = new Uint8Array(blockHashBuffer.length + secretBytes.length);
  rngInput.set(blockHashBuffer, 0);
  rngInput.set(secretBytes, blockHashBuffer.length);

  let rngHash = await sha256(rngInput);
  
  // Rejection sampling to avoid modulo bias
  // We can only use values 0-199 (200 values) to get uniform distribution
  // For each byte, if it's < 200, we use byte % 100
  // If it's >= 200, we reject and continue to next byte
  for (let i = 0; i < rngHash.length; i++) {
    const byte = rngHash[i];
    if (byte < 200) {
      return byte % 100; // Uniform distribution 0-99
    }
  }
  
  // Extremely unlikely: all 32 bytes were >= 200
  // Hash the hash to get more entropy and try again
  let secondHash = await sha256(rngHash);
  for (let i = 0; i < secondHash.length; i++) {
    const byte = secondHash[i];
    if (byte < 200) {
      return byte % 100;
    }
  }
  
  // If we still haven't found a valid byte (probability ~1e-78), 
  // fall back to the first byte mod 100 (this should never happen)
  return rngHash[0] % 100;
}

/**
 * Determine if the player won the dice bet.
 */
export function isDiceWin(rngOutcome: number, rollTarget: number): boolean {
  return rngOutcome < rollTarget;
}

// ─── Sigma-State Serialization Helpers ─────────────────────────

/**
 * Encode an integer as an ErgoScript IntConstant SValue hex.
 * Used for rollTarget in R6.
 */
export function encodeIntConstant(value: number): string {
  // ZigZag encode
  const zigzag = (value << 1) ^ (value >> 31);
  // Convert to unsigned 32-bit
  const unsigned = zigzag >>> 0;
  // VLQ encode
  const vlq = encodeVLQ(unsigned);
  return `02${vlq}`;
}

/**
 * Encode a bigint as an ErgoScript LongConstant SValue hex.
 * Used for player secret in R7.
 */
export function encodeLongConstant(value: bigint): string {
  // ZigZag encode for i64
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

// ─── Internal VLQ helpers ──────────────────────────────────────

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
