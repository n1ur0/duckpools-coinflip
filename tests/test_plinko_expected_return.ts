/**
 * Unit Tests for Plinko Expected Return Calculation
 *
 * MAT-263: Verify that computeExpectedReturn uses probability-weighted
 * expected value (correct) NOT arithmetic mean (incorrect).
 *
 * Run with: npm test -- tests/test_plinko_expected_return.ts
 */

import {
  computeExpectedReturn,
  getPlinkoHouseEdge,
  getPlinkoRTP,
  getMultipliersForRows,
  getProbabilitiesForRows,
  validateExpectedReturn,
  getPlinkoMultiplier,
} from '../frontend/src/utils/plinko';

// ─── Test Utilities ───────────────────────────────────────────────

function assertApproximatelyEqual(
  actual: number,
  expected: number,
  tolerance: number = 0.01,
  message: string
): void {
  const diff = Math.abs(actual - expected);
  if (diff > tolerance) {
    throw new Error(
      `${message}\n  Expected: ${expected}\n  Actual: ${actual}\n  Diff: ${diff}\n  Tolerance: ${tolerance}`
    );
  }
}

function test(testName: string, testFn: () => void): void {
  try {
    testFn();
    console.log(`✅ PASS: ${testName}`);
  } catch (error) {
    console.error(`❌ FAIL: ${testName}`);
    console.error(`  ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  }
}

// ─── Core Expected Return Tests ──────────────────────────────────

test('8 rows: Expected return should be ~0.97 (97% RTP)', () => {
  const expectedReturn = computeExpectedReturn(8);
  assertApproximatelyEqual(
    expectedReturn,
    0.97,
    0.01,
    '8 rows expected return should be ~0.97'
  );
});

test('12 rows: Expected return should be ~0.97 (97% RTP)', () => {
  const expectedReturn = computeExpectedReturn(12);
  assertApproximatelyEqual(
    expectedReturn,
    0.97,
    0.01,
    '12 rows expected return should be ~0.97'
  );
});

test('16 rows: Expected return should be ~0.97 (97% RTP)', () => {
  const expectedReturn = computeExpectedReturn(16);
  assertApproximatelyEqual(
    expectedReturn,
    0.97,
    0.01,
    '16 rows expected return should be ~0.97'
  );
});

// ─── House Edge Tests ───────────────────────────────────────────────

test('8 rows: House edge should be ~0.03 (3%)', () => {
  const houseEdge = getPlinkoHouseEdge(8);
  assertApproximatelyEqual(
    houseEdge,
    0.03,
    0.01,
    '8 rows house edge should be ~0.03'
  );
});

test('12 rows: House edge should be ~0.03 (3%)', () => {
  const houseEdge = getPlinkoHouseEdge(12);
  assertApproximatelyEqual(
    houseEdge,
    0.03,
    0.01,
    '12 rows house edge should be ~0.03'
  );
});

test('16 rows: House edge should be ~0.03 (3%)', () => {
  const houseEdge = getPlinkoHouseEdge(16);
  assertApproximatelyEqual(
    houseEdge,
    0.03,
    0.01,
    '16 rows house edge should be ~0.03'
  );
});

// ─── RTP Tests ─────────────────────────────────────────────────────

test('8 rows: RTP should be ~97%', () => {
  const rtp = getPlinkoRTP(8);
  assertApproximatelyEqual(rtp, 97.0, 1.0, '8 rows RTP should be ~97%');
});

test('12 rows: RTP should be ~97%', () => {
  const rtp = getPlinkoRTP(12);
  assertApproximatelyEqual(rtp, 97.0, 1.0, '12 rows RTP should be ~97%');
});

test('16 rows: RTP should be ~97%', () => {
  const rtp = getPlinkoRTP(16);
  assertApproximatelyEqual(rtp, 97.0, 1.0, '16 rows RTP should be ~97%');
});

// ─── Probability-Weighted vs Arithmetic Mean Test (CRITICAL) ─────

test('CRITICAL: Probability-weighted mean differs from arithmetic mean', () => {
  // This test verifies that we're using the CORRECT method
  // (probability-weighted) and not the INCORRECT method (arithmetic mean)

  const multipliers = getMultipliersForRows(12);
  const probabilities = getProbabilitiesForRows(12);

  // INCORRECT: Arithmetic mean (what the bug was doing)
  const arithmeticMean = multipliers.reduce((sum, m) => sum + m, 0) / multipliers.length;

  // CORRECT: Probability-weighted mean (what the fix does)
  const probabilityWeightedMean = computeExpectedReturn(12);

  // These should be SIGNIFICANTLY different
  // Arithmetic mean ignores that outer slots are rare
  const difference = Math.abs(arithmeticMean - probabilityWeightedMean);

  console.log(`  Arithmetic mean (WRONG): ${arithmeticMean.toFixed(4)}`);
  console.log(`  Probability-weighted mean (CORRECT): ${probabilityWeightedMean.toFixed(4)}`);
  console.log(`  Difference: ${difference.toFixed(4)}`);

  if (difference < 0.1) {
    throw new Error(
      'Probability-weighted mean should differ significantly from arithmetic mean. ' +
      'If they are similar, the calculation may still be wrong.'
    );
  }
});

// ─── Validate Expected Return Function Tests ─────────────────────

test('8 rows: validateExpectedReturn should pass with 1% tolerance', () => {
  const isValid = validateExpectedReturn(8, 0.01, 97.0);
  if (!isValid) {
    throw new Error('8 rows expected return validation should pass');
  }
});

test('12 rows: validateExpectedReturn should pass with 1% tolerance', () => {
  const isValid = validateExpectedReturn(12, 0.01, 97.0);
  if (!isValid) {
    throw new Error('12 rows expected return validation should pass');
  }
});

test('16 rows: validateExpectedReturn should pass with 1% tolerance', () => {
  const isValid = validateExpectedReturn(16, 0.01, 97.0);
  if (!isValid) {
    throw new Error('16 rows expected return validation should pass');
  }
});

test('validateExpectedReturn should fail with extremely tight tolerance', () => {
  // With 0.001 tolerance, the small deviations should fail
  const isValid = validateExpectedReturn(12, 0.001, 97.0);
  if (isValid) {
    throw new Error('Expected return validation should fail with 0.1% tolerance');
  }
});

// ─── Multiplier and Probability Array Tests ───────────────────────

test('12 rows: Should have 12 multipliers', () => {
  const multipliers = getMultipliersForRows(12);
  if (multipliers.length !== 12) {
    throw new Error(`Expected 12 multipliers, got ${multipliers.length}`);
  }
});

test('12 rows: Should have 12 probabilities', () => {
  const probabilities = getProbabilitiesForRows(12);
  if (probabilities.length !== 12) {
    throw new Error(`Expected 12 probabilities, got ${probabilities.length}`);
  }
});

test('12 rows: Probabilities should sum to 1', () => {
  const probabilities = getProbabilitiesForRows(12);
  const sum = probabilities.reduce((s, p) => s + p, 0);
  assertApproximatelyEqual(sum, 1.0, 0.0001, 'Probabilities should sum to 1');
});

test('8 rows: Probabilities should sum to 1', () => {
  const probabilities = getProbabilitiesForRows(8);
  const sum = probabilities.reduce((s, p) => s + p, 0);
  assertApproximatelyEqual(sum, 1.0, 0.0001, 'Probabilities should sum to 1');
});

test('16 rows: Probabilities should sum to 1', () => {
  const probabilities = getProbabilitiesForRows(16);
  const sum = probabilities.reduce((s, p) => s + p, 0);
  assertApproximatelyEqual(sum, 1.0, 0.0001, 'Probabilities should sum to 1');
});

// ─── Multiplier Symmetry Tests ────────────────────────────────────

test('12 rows: Multipliers should be symmetric', () => {
  const multipliers = getMultipliersForRows(12);
  const mid = Math.floor(multipliers.length / 2);

  for (let i = 0; i < mid; i++) {
    const left = multipliers[i];
    const right = multipliers[multipliers.length - 1 - i];
    if (Math.abs(left - right) > 0.01) {
      throw new Error(
        `Multipliers should be symmetric. Multipliers[${i}]=${left} != Multipliers[${multipliers.length - 1 - i}]=${right}`
      );
    }
  }
});

test('8 rows: Multipliers should be symmetric', () => {
  const multipliers = getMultipliersForRows(8);
  const mid = Math.floor(multipliers.length / 2);

  for (let i = 0; i < mid; i++) {
    const left = multipliers[i];
    const right = multipliers[multipliers.length - 1 - i];
    if (Math.abs(left - right) > 0.01) {
      throw new Error(
        `Multipliers should be symmetric. Multipliers[${i}]=${left} != Multipliers[${multipliers.length - 1 - i}]=${right}`
      );
    }
  }
});

// ─── Probability Distribution Tests ─────────────────────────────────

test('12 rows: Center slots should have higher probability', () => {
  const probabilities = getProbabilitiesForRows(12);
  const centerIndex = Math.floor(probabilities.length / 2);
  const edgeIndex = 0;

  if (probabilities[centerIndex] <= probabilities[edgeIndex]) {
    throw new Error(
      `Center slot (prob=${probabilities[centerIndex]}) should have higher probability than edge slot (prob=${probabilities[edgeIndex]})`
    );
  }
});

test('12 rows: Probability should decrease from center to edges', () => {
  const probabilities = getProbabilitiesForRows(12);
  const centerIndex = Math.floor(probabilities.length / 2);

  // Check moving outward from center
  for (let i = 0; i < centerIndex; i++) {
    const innerProb = probabilities[centerIndex - i];
    const outerProb = probabilities[centerIndex - i - 1];
    if (outerProb > innerProb) {
      throw new Error(
        `Probability should decrease from center to edges. ` +
        `At distance ${i} from center: inner=${innerProb}, outer=${outerProb}`
      );
    }
  }
});

// ─── Invalid Input Tests ─────────────────────────────────────────

test('getPlinkoMultiplier should throw for invalid slot index', () => {
  try {
    getPlinkoMultiplier(12, 99);
    throw new Error('Should have thrown an error for invalid slot index');
  } catch (error) {
    if (!(error instanceof Error && error.message.includes('Invalid slotIndex'))) {
      throw new Error(`Wrong error type: ${error}`);
    }
  }
});

test('getPlinkoMultiplier should throw for negative slot index', () => {
  try {
    getPlinkoMultiplier(12, -1);
    throw new Error('Should have thrown an error for negative slot index');
  } catch (error) {
    if (!(error instanceof Error && error.message.includes('Invalid slotIndex'))) {
      throw new Error(`Wrong error type: ${error}`);
    }
  }
});

// ─── Summary ─────────────────────────────────────────────────────

console.log('\n✅ All Plinko expected return tests passed!');
console.log('\nKey verification points:');
console.log('  ✓ Expected returns use PROBABILITY-WEIGHTED mean (not arithmetic mean)');
console.log('  ✓ House edge is ~3% for all row counts');
console.log('  ✓ RTP is ~97% for all row counts');
console.log('  ✓ Probability distributions are normalized (sum to 1)');
console.log('  ✓ Multipliers are symmetric');
console.log('  ✓ Center slots have higher probability than edges');
