/**
 * DuckPools SDK - Commit-Reveal Protocol Example
 *
 * This example demonstrates the commit-reveal RNG mechanism:
 * - Generate random secret
 * - Create commitment hash
 * - Verify commitment matches reveal
 * - Compute provably-fair outcome
 */

import {
  generateSecret,
  generateCommit,
  verifyCommit,
  computeRng,
  formatSecret,
  formatHash,
} from '../src/index.js';

async function main() {
  console.log('=== Commit-Reveal Protocol Example ===\n');

  // 1. Generate random secret
  console.log('1. Generating random secret...');
  const secret = generateSecret();
  console.log(`   Secret (hex): ${secret}`);
  console.log(`   Secret (formatted): ${formatSecret(secret)}`);
  console.log();

  // 2. Generate commitment
  console.log('2. Creating commitment...');
  const choice = 0; // 0 = heads, 1 = tails
  const { commitment } = await generateCommit(secret, choice);
  console.log(`   Choice: ${choice === 0 ? 'heads' : 'tails'}`);
  console.log(`   Commitment (hash): ${formatHash(commitment)}`);
  console.log();

  // 3. Verify commitment
  console.log('3. Verifying commitment matches...');
  const isValid = await verifyCommit(commitment, secret, choice);
  console.log(`   Valid: ${isValid}`);
  console.log();

  // 4. Wrong secret should fail verification
  console.log('4. Verifying with wrong secret should fail...');
  const wrongSecret = generateSecret();
  const isInvalid = await verifyCommit(commitment, wrongSecret, choice);
  console.log(`   Wrong secret valid: ${isInvalid} (should be false)`);
  console.log();

  // 5. Wrong choice should fail verification
  console.log('5. Verifying with wrong choice should fail...');
  const isInvalid2 = await verifyCommit(commitment, secret, 1);
  console.log(`   Wrong choice valid: ${isInvalid2} (should be false)`);
  console.log();

  // 6. Compute RNG outcome from block hash
  console.log('6. Computing provably-fair outcome...');
  const blockHashes = [
    '0000000000000000000000000000000000000000000000000000000000000000',
    '1111111111111111111111111111111111111111111111111111111111111111',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  ];

  for (const hash of blockHashes) {
    const outcome = await computeRng(hash, secret);
    console.log(`   Block: ${hash.substring(0, 16)}...`);
    console.log(`   Outcome: ${outcome === 0 ? 'heads' : 'tails'}`);
  }
  console.log();

  // 7. Demonstrate provable fairness
  console.log('7. Provable fairness demo...');
  console.log('   - Commitment is submitted BEFORE the block is mined');
  console.log('   - Block hash is unpredictable when commitment is made');
  console.log('   - Player cannot change secret after seeing block hash');
  console.log('   - House cannot influence block hash');
  console.log('   - Outcome: SHA256(blockHash || secret)[0] % 2');
  console.log();

  console.log('=== Example completed ===');
}

main().catch(console.error);
