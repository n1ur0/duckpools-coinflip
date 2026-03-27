/**
 * DuckPools SDK - Pool Management Example
 *
 * This example demonstrates LP pool operations:
 * - Query pool state
 * - Calculate APY
 * - Estimate deposit/withdraw
 * - Format pool data
 */

import {
  PoolManager,
  PoolClient,
  PoolFormatters,
  calculateAPY,
  calculateDepositShares,
  calculateWithdrawAmount,
  formatNanoErgToErg,
  formatErgToNanoErg,
} from '../src/index.js';

async function main() {
  console.log('=== Pool Management Example ===\n');

  // Note: This example uses mock data since it requires a real Ergo node
  // In production, you would initialize with actual node client

  // 1. Calculate APY
  console.log('1. Calculating APY...');
  const apy = calculateAPY(
    300, // days per year
    1_000_000_000n, // daily volume (1 ERG)
    0.03, // house edge (3%)
    100_000_000_000_000n // TVL (100,000 ERG)
  );
  console.log(`   Daily volume: 1 ERG`);
  console.log(`   House edge: 3%`);
  console.log(`   TVL: 100,000 ERG`);
  console.log(`   APY: ${apy.toFixed(2)}%`);
  console.log();

  // 2. Calculate deposit shares
  console.log('2. Calculating deposit shares...');
  const deposit = calculateDepositShares(
    10_000_000_000n, // deposit amount (10 ERG)
    1_000_000_000_000n, // total LP tokens (1,000)
    100_000_000_000_000n // total liquidity (100,000 ERG)
  );
  console.log(`   Deposit amount: ${formatNanoErgToErg(deposit.amount)} ERG`);
  console.log(`   Shares received: ${deposit.shares}`);
  console.log(`   Price per share: ${formatNanoErgToErg(deposit.pricePerShare)} ERG`);
  console.log();

  // 3. Calculate withdraw amount
  console.log('3. Calculating withdraw amount...');
  const withdraw = calculateWithdrawAmount(
    100n, // LP shares to withdraw
    1_000_000_000_000n, // total LP tokens (1,000)
    100_000_000_000_000n // total liquidity (100,000 ERG)
  );
  console.log(`   LP shares: ${withdraw.shares}`);
  console.log(`   Withdraw amount: ${formatNanoErgToErg(withdraw.amount)} ERG`);
  console.log();

  // 4. Format pool data
  console.log('4. Formatting pool data for display...');
  const poolState = {
    liquidity: 100_000_000_000_000n, // 100,000 ERG
    houseEdge: 0.03,
    totalValueLocked: 100_000_000_000_000n,
    pendingBets: 5,
    completedBets: 1250,
    lpTokenSupply: 1_000_000_000_000n,
  };

  console.log(`   TVL: ${PoolFormatters.nanoErgToErg(poolState.totalValueLocked)} ERG`);
  console.log(`   House edge: ${PoolFormatters.houseEdgeToPercent(poolState.houseEdge)}%`);
  console.log(`   Pending bets: ${poolState.pendingBets}`);
  console.log(`   Completed bets: ${poolState.completedBets}`);
  console.log(`   LP token supply: ${PoolFormatters.lpTokenToUnits(poolState.lpTokenSupply)}`);
  console.log();

  // 5. Different deposit scenarios
  console.log('5. Deposit scenarios...');
  const depositAmounts = [1_000_000_000n, 10_000_000_000n, 100_000_000_000n];
  const baseLiquidity = 100_000_000_000_000n;
  const baseShares = 1_000_000_000_000n;

  for (const amount of depositAmounts) {
    const depositCalc = calculateDepositShares(amount, baseShares, baseLiquidity);
    console.log(
      `   Deposit ${formatNanoErgToErg(amount).padStart(6)} ERG -> ` +
      `${depositCalc.shares} shares (${formatNanoErgToErg(depositCalc.pricePerShare)} ERG/share)`
    );
  }
  console.log();

  // 6. APY sensitivity analysis
  console.log('6. APY sensitivity analysis...');
  const dailyVolumes = [
    100_000_000n, // 0.1 ERG
    1_000_000_000n, // 1 ERG
    10_000_000_000n, // 10 ERG
    100_000_000_000n, // 100 ERG
  ];

  for (const volume of dailyVolumes) {
    const apyResult = calculateAPY(365, volume, 0.03, 100_000_000_000_000n);
    console.log(
      `   Daily: ${formatNanoErgToErg(volume).padStart(6)} ERG -> ` +
      `APY: ${apyResult.toFixed(2).padStart(6)}%`
    );
  }
  console.log();

  console.log('=== Example completed ===');
  console.log('\nNote: This example uses mock data. In production, initialize PoolManager');
  console.log('with a NodeClient and pool contract configuration for on-chain queries.');
}

main().catch(console.error);
