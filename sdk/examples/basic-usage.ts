/**
 * DuckPools SDK - Basic Usage Example
 *
 * This example demonstrates the core functionality of the DuckPools SDK:
 * - Creating a client
 * - Generating commitments
 * - Placing bets
 * - Revealing bets
 * - Computing RNG outcomes
 */

import {
  DuckPoolsClient,
  generateSecret,
  generateCommit,
  verifyCommit,
  computeRng,
  formatErg,
} from '../src/index.js';

async function main() {
  console.log('=== DuckPools SDK - Basic Usage Example ===\n');

  // 1. Create client
  console.log('1. Creating DuckPoolsClient...');
  const client = DuckPoolsClient.create({
    url: 'http://localhost:9052',
    apiKey: 'your-api-key',
    network: 'testnet',
    houseAddress: '3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26',
    coinflipNftId: 'your-coinflip-nft-id',
    pendingBetAddress: 'your-pending-bet-address',
  });
  console.log('Client created successfully!\n');

  // 2. Check node status
  console.log('2. Checking node status...');
  try {
    const info = await client.getNodeInfo();
    console.log(`   Node height: ${info.fullHeight}`);
    console.log(`   Network: ${info.networkType}`);
    console.log();
  } catch (error) {
    console.log(`   Node not available (expected in example): ${error}\n`);
  }

  // 3. Generate commitment
  console.log('3. Generating commitment...');
  const choice = 0; // 0 = heads, 1 = tails
  const { secret, commitment } = await generateCommit(undefined, choice);
  console.log(`   Choice: ${choice === 0 ? 'heads' : 'tails'}`);
  console.log(`   Secret: ${secret}`);
  console.log(`   Commitment: ${commitment}`);
  console.log();

  // 4. Verify commitment
  console.log('4. Verifying commitment...');
  const isValid = await verifyCommit(commitment, secret, choice);
  console.log(`   Commitment valid: ${isValid}`);
  console.log();

  // 5. Place a bet (commented out - requires real node)
  console.log('5. Place a bet (requires unlocked wallet)...');
  try {
    await client.unlockWallet('your-wallet-password');

    const result = await client.placeBet({
      amount: 1_000_000_000n, // 1 ERG in nanoERG
      choice: 0, // heads
      timeoutDelta: 100, // blocks until refund
    });

    console.log(`   Bet placed!`);
    console.log(`   Transaction ID: ${result.transactionId}`);
    console.log(`   Box ID: ${result.boxId}`);
    console.log(`   Commitment: ${result.commitment}`);
    console.log(`   Timeout height: ${result.timeoutHeight}`);
    console.log();
  } catch (error) {
    console.log(`   Skipped: ${error}\n`);
  }

  // 6. Compute RNG outcome
  console.log('6. Computing RNG outcome...');
  const blockHash = 'example-block-hash-32-bytes';
  const outcome = await computeRng(blockHash, secret);
  console.log(`   Block hash: ${blockHash}`);
  console.log(`   Secret: ${secret}`);
  console.log(`   Outcome: ${outcome === 0 ? 'heads' : 'tails'}`);
  console.log();

  // 7. Reveal bet (commented out - requires real bet)
  console.log('7. Reveal bet (requires pending bet box)...');
  try {
    const boxId = 'pending-bet-box-id';
    const reveal = await client.revealBet({
      boxId,
      secret,
      choice,
    });
    console.log(`   Result: ${reveal.result}`);
    console.log(`   Payout: ${formatErg(reveal.payout)} ERG`);
    console.log();
  } catch (error) {
    console.log(`   Skipped: ${error}\n`);
  }

  console.log('=== Example completed ===');
}

main().catch(console.error);
