/**
 * Plinko game utilities with symmetric multiplier calculations.
 * 
 * Implements the same power-law formula as the backend:
 * multiplier(k) = A * (1/P(k))^alpha
 * where:
 * - P(k) = C(n, k) / 2^n (binomial probability)
 * - A = (1 - house_edge) / sum(P(j)^(1-alpha)) (normalization constant)
 * - alpha = 0.5 (risk parameter)
 */

export interface PlinkoMultiplierTable {
  [key: string]: number[];
}

export interface PlinkoConfig {
  houseEdge: number;
  alpha: number;
  multiplierTables: PlinkoMultiplierTable;
}

/**
 * Calculate binomial coefficient C(n, k)
 */
function binomialCoefficient(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;
  
  let result = 1;
  for (let i = 1; i <= Math.min(k, n - k); i++) {
    result = (result * (n - i + 1)) / i;
  }
  
  return result;
}

/**
 * Calculate binomial probability P(k) = C(n, k) / 2^n
 */
function binomialProbability(n: number, k: number): number {
  return binomialCoefficient(n, k) / Math.pow(2, n);
}

/**
 * Calculate symmetric multipliers for Plinko game
 */
function calculateMultipliers(rows: number, houseEdge: number = 0.03, alpha: number = 0.5): number[] {
  if (rows !== 8 && rows !== 12 && rows !== 16) {
    throw new Error(`Invalid number of rows: ${rows}. Must be 8, 12, or 16.`);
  }
  
  const n = rows;
  const slots = n + 1; // Number of landing slots
  
  // Calculate probabilities for each slot
  const probabilities: number[] = [];
  for (let k = 0; k < slots; k++) {
    probabilities.push(binomialProbability(n, k));
  }
  
  // Calculate normalization constant A
  const numerator = 1.0 - houseEdge;
  let denominator = 0.0;
  
  for (const prob of probabilities) {
    denominator += Math.pow(prob, 1.0 - alpha);
  }
  
  const A = numerator / denominator;
  
  // Calculate multipliers using power-law formula
  const multipliers: number[] = [];
  for (let k = 0; k < slots; k++) {
    const prob = probabilities[k];
    if (prob > 0) {
      const multiplier = A * Math.pow(1.0 / prob, alpha);
      multipliers.push(multiplier);
    } else {
      multipliers.push(0.0);
    }
  }
  
  // Verify symmetry: multiplier[i] should equal multiplier[rows-i]
  for (let i = 0; i < slots / 2; i++) {
    if (Math.abs(multipliers[i] - multipliers[n - i]) > 1e-10) {
      throw new Error(`Symmetry violation at slot ${i}: ${multipliers[i]} !== ${multipliers[n - i]}`);
    }
  }
  
  return multipliers;
}

/**
 * Get Plinko game configuration with multiplier tables
 */
export function getPlinkoConfig(): PlinkoConfig {
  return {
    houseEdge: 0.03,
    alpha: 0.5,
    multiplierTables: {
      '8': calculateMultipliers(8),
      '12': calculateMultipliers(12),
      '16': calculateMultipliers(16),
    },
  };
}

/**
 * Get multipliers for a specific row count
 */
export function getMultipliersForRows(rows: number): number[] {
  const config = getPlinkoConfig();
  const multipliers = config.multiplierTables[rows.toString()];
  
  if (!multipliers) {
    throw new Error(`No multiplier table found for ${rows} rows`);
  }
  
  return multipliers;
}

/**
 * Calculate potential payout for a bet
 */
export function calculatePayout(betAmount: number, slot: number, rows: number): number {
  const multipliers = getMultipliersForRows(rows);
  
  if (slot < 0 || slot >= multipliers.length) {
    throw new Error(`Invalid slot ${slot} for ${rows} rows (0-${multipliers.length - 1})`);
  }
  
  const multiplier = multipliers[slot];
  return betAmount * multiplier;
}

/**
 * Calculate expected value for a multiplier table
 */
export function calculateExpectedValue(multipliers: number[], houseEdge: number = 0.03): number {
  const n = multipliers.length - 1; // Number of rows
  let expectedValue = 0.0;
  
  for (let k = 0; k < multipliers.length; k++) {
    const prob = binomialProbability(n, k);
    expectedValue += prob * multipliers[k];
  }
  
  return expectedValue;
}

/**
 * Format multiplier for display
 */
export function formatMultiplier(multiplier: number): string {
  if (multiplier >= 100) {
    return `${multiplier.toFixed(0)}x`;
  } else if (multiplier >= 10) {
    return `${multiplier.toFixed(1)}x`;
  } else {
    return `${multiplier.toFixed(2)}x`;
  }
}

/**
 * Get slot probabilities for display
 */
export function getSlotProbabilities(rows: number): number[] {
  const slots = rows + 1;
  const probabilities: number[] = [];
  
  for (let k = 0; k < slots; k++) {
    probabilities.push(binomialProbability(rows, k));
  }
  
  return probabilities;
}

/**
 * Validate that multiplier tables are symmetric
 */
export function validateSymmetry(multipliers: number[]): boolean {
  for (let i = 0; i < multipliers.length / 2; i++) {
    const j = multipliers.length - 1 - i;
    if (Math.abs(multipliers[i] - multipliers[j]) > 1e-10) {
      return false;
    }
  }
  return true;
}

/**
 * Get risk level description based on row count
 */
export function getRiskLevel(rows: number): string {
  switch (rows) {
    case 8:
      return 'Low Risk';
    case 12:
      return 'Medium Risk';
    case 16:
      return 'High Risk';
    default:
      return 'Unknown';
  }
}

/**
 * Get color class for a slot based on its multiplier
 */
export function getSlotColorClass(slot: number, rows: number): string {
  const multipliers = getMultipliersForRows(rows);
  const multiplier = multipliers[slot];
  
  // Higher multipliers get "hotter" colors
  if (multiplier >= 50) return 'slot-red';
  if (multiplier >= 20) return 'slot-orange';
  if (multiplier >= 10) return 'slot-yellow';
  if (multiplier >= 5) return 'slot-green';
  return 'slot-blue';
}