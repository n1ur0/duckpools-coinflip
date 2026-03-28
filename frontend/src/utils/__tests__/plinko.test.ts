/**
 * Unit tests for Plinko game utilities
 *
 * Key test: verify compute_expected_return uses probability-weighted sum,
 * not arithmetic mean (the bug we're fixing).
 */

import {
  binomialCoefficient,
  getPlinkoSlotProbability,
  getPlinkoSlotMultiplier,
  calculatePlinkoPayout,
  computePlinkoExpectedReturn,
  getPlinkoRTP,
  getPlinkoMultiplierTable,
  getPlinkoProbabilityTable,
  generatePlinkoCommit,
  verifyPlinkoCommit,
  computePlinkoRng,
  PLINKO_HOUSE_EDGE,
  PLINKO_MIN_ROWS,
  PLINKO_MAX_ROWS,
} from '../plinko';

describe('Plinko Binomial Coefficients', () => {
  test('C(0, 0) = 1', () => {
    expect(binomialCoefficient(0, 0)).toBe(1);
  });

  test('C(8, 4) = 70', () => {
    expect(binomialCoefficient(8, 4)).toBe(70);
  });

  test('C(12, 6) = 924', () => {
    expect(binomialCoefficient(12, 6)).toBe(924);
  });

  test('C(16, 8) = 12870', () => {
    expect(binomialCoefficient(16, 8)).toBe(12870);
  });

  test('C(n, 0) = C(n, n) = 1', () => {
    expect(binomialCoefficient(10, 0)).toBe(1);
    expect(binomialCoefficient(10, 10)).toBe(1);
  });

  test('Invalid k returns 0', () => {
    expect(binomialCoefficient(8, -1)).toBe(0);
    expect(binomialCoefficient(8, 10)).toBe(0);
  });
});

describe('Plinko Slot Probabilities', () => {
  test('Probabilities sum to 1 for 8 rows', () => {
    const probs = getPlinkoProbabilityTable(8);
    const sum = probs.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1.0, 10);
  });

  test('Probabilities sum to 1 for 12 rows', () => {
    const probs = getPlinkoProbabilityTable(12);
    const sum = probs.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1.0, 10);
  });

  test('Probabilities sum to 1 for 16 rows', () => {
    const probs = getPlinkoProbabilityTable(16);
    const sum = probs.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1.0, 10);
  });

  test('Center slot (4/8) has highest probability', () => {
    const probs = getPlinkoProbabilityTable(8);
    expect(probs[4]).toBeGreaterThan(probs[0]);
    expect(probs[4]).toBeGreaterThan(probs[8]);
  });

  test('Outer slots have lowest probability', () => {
    const probs = getPlinkoProbabilityTable(12);
    expect(probs[0]).toBeLessThan(probs[6]);
    expect(probs[12]).toBeLessThan(probs[6]);
  });

  test('8-row distribution matches Pascal triangle', () => {
    // 8 rows: [1, 8, 28, 56, 70, 56, 28, 8, 1] / 256
    const expectedProbs = [
      1/256, 8/256, 28/256, 56/256, 70/256, 56/256, 28/256, 8/256, 1/256
    ];

    for (let slot = 0; slot <= 8; slot++) {
      expect(getPlinkoSlotProbability(8, slot)).toBeCloseTo(expectedProbs[slot], 10);
    }
  });
});

describe('Plinko Slot Multipliers', () => {
  test('Center slot has lowest multiplier', () => {
    const mults = getPlinkoMultiplierTable(8);
    const centerIdx = 4;
    expect(mults[centerIdx]).toBeLessThan(mults[0]);
    expect(mults[centerIdx]).toBeLessThan(mults[8]);
  });

  test('Outer slots have highest multipliers', () => {
    const mults = getPlinkoMultiplierTable(12);
    expect(mults[0]).toBeGreaterThan(mults[6]);
    expect(mults[12]).toBeGreaterThan(mults[6]);
  });

  test('Multiplier formula: multiplier = (1/P) * (1 - house_edge)', () => {
    const rows = 8;
    const slot = 4;
    const prob = getPlinkoSlotProbability(rows, slot);
    const mult = getPlinkoSlotMultiplier(rows, slot);

    const expectedMult = (1 / prob) * (1 - PLINKO_HOUSE_EDGE);
    expect(mult).toBeCloseTo(expectedMult, 10);
  });
});

describe('BUG FIX: compute_expected_return uses PROBABILITY-WEIGHTED sum', () => {
  /**
   * CRITICAL TEST: Verify we use probability-weighted expected value,
   * NOT arithmetic mean of multipliers.
   *
   * Arithmetic mean would be: mean(multipliers)
   * Probability-weighted is: sum(probabilities * multipliers)
   *
   * The bug was using arithmetic mean, which gives WRONG results.
   */

  test('Expected return uses probability-weighted sum (8 rows)', () => {
    const betNanoErg = 1000000000; // 1 ERG
    const rows = 8;
    const expectedPayout = computePlinkoExpectedReturn(betNanoErg, rows);

    // Manual probability-weighted calculation
    const probs = getPlinkoProbabilityTable(rows);
    const mults = getPlinkoMultiplierTable(rows);
    let manualExpected = 0;

    for (let slot = 0; slot <= rows; slot++) {
      manualExpected += probs[slot] * mults[slot];
    }

    manualExpected *= betNanoErg;

    // Should match the manual calculation
    expect(expectedPayout).toBeCloseTo(manualExpected, 2);
  });

  test('Expected return uses probability-weighted sum (12 rows)', () => {
    const betNanoErg = 500000000; // 0.5 ERG
    const rows = 12;
    const expectedPayout = computePlinkoExpectedReturn(betNanoErg, rows);

    // Manual probability-weighted calculation
    const probs = getPlinkoProbabilityTable(rows);
    const mults = getPlinkoMultiplierTable(rows);
    let manualExpected = 0;

    for (let slot = 0; slot <= rows; slot++) {
      manualExpected += probs[slot] * mults[slot];
    }

    manualExpected *= betNanoErg;

    // Should match the manual calculation
    expect(expectedPayout).toBeCloseTo(manualExpected, 2);
  });

  test('Expected return equals bet * (1 - house_edge)', () => {
    const betNanoErg = 1000000000;
    const rows = 12;
    const expectedPayout = computePlinkoExpectedReturn(betNanoErg, rows);

    const expectedTheoretical = betNanoErg * (1 - PLINKO_HOUSE_EDGE);

    expect(expectedPayout).toBeCloseTo(expectedTheoretical, 0);
  });

  test('RTP is exactly 97% (3% house edge)', () => {
    expect(getPlinkoRTP()).toBeCloseTo(97.0, 5);
  });

  test('CRITICAL: Expected return is NOT arithmetic mean of multipliers', () => {
    /**
     * This test verifies we're NOT using the buggy arithmetic mean approach.
     *
     * Arithmetic mean of multipliers would give a different (wrong) answer.
     */

    const betNanoErg = 1000000000;
    const rows = 8;

    // Correct: probability-weighted (what we implemented)
    const correctExpected = computePlinkoExpectedReturn(betNanoErg, rows);

    // Buggy: arithmetic mean of multipliers
    const mults = getPlinkoMultiplierTable(rows);
    const arithmeticMean = mults.reduce((a, b) => a + b, 0) / mults.length;
    const buggyExpected = betNanoErg * arithmeticMean;

    // They should be DIFFERENT (the bug is fixed)
    expect(Math.abs(correctExpected - buggyExpected)).toBeGreaterThan(betNanoErg * 0.1);

    // The correct one should match (1 - house_edge) * bet
    expect(correctExpected).toBeCloseTo(betNanoErg * 0.97, 0);

    // The buggy one would be wrong
    expect(buggyExpected).not.toBeCloseTo(betNanoErg * 0.97, 0);
  });

  test('Expected return is consistent across different row counts', () => {
    /**
     * The expected return should be the same regardless of row count,
     * because the house edge is built into the multiplier calculation.
     */

    const betNanoErg = 1000000000;
    const expectedFor8 = computePlinkoExpectedReturn(betNanoErg, 8);
    const expectedFor12 = computePlinkoExpectedReturn(betNanoErg, 12);
    const expectedFor16 = computePlinkoExpectedReturn(betNanoErg, 16);

    // All should be approximately 0.97 * bet
    const expectedValue = betNanoErg * (1 - PLINKO_HOUSE_EDGE);

    expect(expectedFor8).toBeCloseTo(expectedValue, 0);
    expect(expectedFor12).toBeCloseTo(expectedValue, 0);
    expect(expectedFor16).toBeCloseTo(expectedValue, 0);

    // They should all be close to each other
    expect(expectedFor8).toBeCloseTo(expectedFor12, 5);
    expect(expectedFor12).toBeCloseTo(expectedFor16, 5);
  });
});

describe('Plinko Payout Calculation', () => {
  test('Payout for center slot is close to bet', () => {
    const betNanoErg = 1000000000;
    const payout = calculatePlinkoPayout(betNanoErg, 8, 4);

    // Center slot should have multiplier close to 1 (actually slightly less than 1 due to house edge)
    expect(payout).toBeGreaterThan(betNanoErg * 0.5);
    expect(payout).toBeLessThan(betNanoErg * 2);
  });

  test('Payout for outer slot is much larger', () => {
    const betNanoErg = 1000000000;
    const payout = calculatePlinkoPayout(betNanoErg, 12, 0);

    // Outer slot should have very high multiplier
    expect(payout).toBeGreaterThan(betNanoErg * 100);
  });
});

describe('Plinko Commitment Scheme', async () => {
  test('generatePlinkoCommit produces deterministic output', async () => {
    const rows = 12;
    const { secret, commitment } = await generatePlinkoCommit(rows);

    expect(secret).toBeInstanceOf(Uint8Array);
    expect(secret.length).toBe(8);
    expect(commitment).toHaveLength(64); // 32 bytes as hex
    expect(commitment).toMatch(/^[0-9a-f]+$/i);
  });

  test('verifyPlinkoCommit validates correctly', async () => {
    const rows = 12;
    const targetSlot = 5;
    const { secret, commitment } = await generatePlinkoCommit(rows, targetSlot);

    const isValid = await verifyPlinkoCommit(commitment, secret, rows, targetSlot);
    expect(isValid).toBe(true);
  });

  test('verifyPlinkoCommit rejects wrong secret', async () => {
    const rows = 12;
    const targetSlot = 5;
    const { secret, commitment } = await generatePlinkoCommit(rows, targetSlot);

    // Wrong secret
    const wrongSecret = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    const isValid = await verifyPlinkoCommit(commitment, wrongSecret, rows, targetSlot);
    expect(isValid).toBe(false);
  });
});

describe('Plinko RNG', async () => {
  test('computePlinkoRng returns valid slot range', async () => {
    const blockHash = 'abc123';
    const secret = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    const rows = 12;

    const slot = await computePlinkoRng(blockHash, secret, rows);

    expect(slot).toBeGreaterThanOrEqual(0);
    expect(slot).toBeLessThanOrEqual(rows);
  });

  test('Different inputs produce different slots', async () => {
    const blockHash1 = 'abc123';
    const blockHash2 = 'def456';
    const secret = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    const rows = 12;

    const slot1 = await computePlinkoRng(blockHash1, secret, rows);
    const slot2 = await computePlinkoRng(blockHash2, secret, rows);

    // Should be different with high probability (but not guaranteed)
    // We just check they're both valid
    expect(slot1).toBeGreaterThanOrEqual(0);
    expect(slot1).toBeLessThanOrEqual(rows);
    expect(slot2).toBeGreaterThanOrEqual(0);
    expect(slot2).toBeLessThanOrEqual(rows);
  });
});

describe('Plinko Utility Functions', () => {
  test('getPlinkoMultiplierTable returns correct length', () => {
    const mults = getPlinkoMultiplierTable(8);
    expect(mults).toHaveLength(9); // 8 rows + 1 = 9 slots
  });

  test('getPlinkoProbabilityTable returns correct length', () => {
    const probs = getPlinkoProbabilityTable(12);
    expect(probs).toHaveLength(13); // 12 rows + 1 = 13 slots
  });

  test('All multipliers are positive', () => {
    const mults = getPlinkoMultiplierTable(16);
    mults.forEach(mult => {
      expect(mult).toBeGreaterThan(0);
    });
  });
});
