/**
 * DuckPools SDK - Pool Tests
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  calculateAPY,
  calculateDepositShares,
  calculateWithdrawErg,
  calculatePricePerShare,
} from '../src/pool/index.js';

describe('Pool', () => {
  describe('calculateAPY', () => {
    it('should calculate APY correctly', () => {
      const apy = calculateAPY(
        300, // house edge in basis points (3%)
        1_000_000_000n, // average bet size (1 ERG)
        1, // bets per block
        100_000_000_000_000n // bankroll (100,000 ERG)
      );
      assert.ok(apy > 0);
      assert.ok(apy < 100);
    });

    it('should return 0 APY when bankroll is 0', () => {
      const apy = calculateAPY(300, 1_000_000_000n, 1, 0n);
      assert.strictEqual(apy, 0);
    });

    it('should return 0 APY when house edge is 0', () => {
      const apy = calculateAPY(0, 1_000_000_000n, 1, 100_000_000_000_000n);
      assert.strictEqual(apy, 0);
    });

    it('should increase APY with higher bet size', () => {
      const apy1 = calculateAPY(300, 1_000_000_000n, 1, 100_000_000_000_000n);
      const apy2 = calculateAPY(300, 10_000_000_000n, 1, 100_000_000_000_000n);
      assert.ok(apy2 > apy1);
    });

    it('should increase APY with higher house edge', () => {
      const apy1 = calculateAPY(100, 1_000_000_000n, 1, 100_000_000_000_000n);
      const apy2 = calculateAPY(500, 1_000_000_000n, 1, 100_000_000_000_000n);
      assert.ok(apy2 > apy1);
    });

    it('should decrease APY with higher bankroll', () => {
      const apy1 = calculateAPY(300, 1_000_000_000n, 1, 10_000_000_000_000n);
      const apy2 = calculateAPY(300, 1_000_000_000n, 1, 100_000_000_000_000n);
      assert.ok(apy1 > apy2);
    });
  });

  describe('calculateDepositShares', () => {
    it('should calculate shares correctly for proportional deposit', () => {
      const result = calculateDepositShares(
        10_000_000_000n, // 10 ERG
        100_000_000_000_000n, // 100,000 ERG total value
        1_000_000_000_000n // 1,000 total shares
      );
      // Expected: 10 / 100000 * 1000 = 100 shares
      assert.strictEqual(result, 100n);
    });

    it('should return deposit amount as shares for first deposit', () => {
      const result = calculateDepositShares(
        10_000_000_000n, // 10 ERG
        0n, // 0 total value (first deposit)
        0n // 0 total shares (first deposit)
      );
      // When no shares exist, shares should equal amount (initial deposit)
      assert.strictEqual(result, 10_000_000_000n);
    });

    it('should calculate proportional shares correctly', () => {
      const totalValue = 100_000_000_000_000n;
      const totalSupply = 1_000_000_000_000n;
      const deposit1 = calculateDepositShares(10_000_000_000n, totalValue, totalSupply);
      const deposit2 = calculateDepositShares(20_000_000_000n, totalValue, totalSupply);
      // deposit2 should be exactly 2x deposit1
      assert.strictEqual(deposit2, deposit1 * 2n);
    });
  });

  describe('calculateWithdrawErg', () => {
    it('should calculate withdraw amount correctly', () => {
      const result = calculateWithdrawErg(
        100n, // 100 shares to burn
        100_000_000_000_000n, // 100,000 ERG total value
        1_000_000_000_000n // 1,000 total shares
      );
      // Expected: 100 / 1000 * 100000 = 10,000 ERG
      assert.strictEqual(result, 10_000_000_000_000n);
    });

    it('should withdraw all value for all shares', () => {
      const result = calculateWithdrawErg(
        1_000_000_000_000n,
        100_000_000_000_000n,
        1_000_000_000_000n
      );
      assert.strictEqual(result, 100_000_000_000_000n);
    });

    it('should return 0 for 0 shares', () => {
      const result = calculateWithdrawErg(
        0n,
        100_000_000_000_000n,
        1_000_000_000_000n
      );
      assert.strictEqual(result, 0n);
    });

    it('should return 0 when total supply is 0', () => {
      const result = calculateWithdrawErg(
        100n,
        100_000_000_000_000n,
        0n
      );
      assert.strictEqual(result, 0n);
    });
  });

  describe('calculatePricePerShare', () => {
    it('should calculate price per share correctly', () => {
      const result = calculatePricePerShare(
        100_000_000_000_000n, // 100,000 ERG total value
        1_000_000_000_000n // 1,000 total shares
      );
      // Expected: 100000 / 1000 * 1e9 = 1e14 = 100 ERG per share with PRECISION factor
      // But PRECISION is 1e9, so: (100000 * 1e9) / 1000 = 100e9 = 100_000_000_000n
      assert.strictEqual(result, 100_000_000_000n);
    });

    it('should return PRECISION for first deposit', () => {
      const result = calculatePricePerShare(
        0n, // 0 total value
        0n // 0 total shares
      );
      assert.strictEqual(result, 1_000_000_000n); // PRECISION
    });

    it('should decrease price per share as shares increase', () => {
      const totalValue = 100_000_000_000_000n;
      const price1 = calculatePricePerShare(totalValue, 1_000_000_000_000n);
      const price2 = calculatePricePerShare(totalValue, 2_000_000_000_000n);
      assert.ok(price2 < price1);
    });
  });

  describe('Share price consistency', () => {
    it('should maintain consistent share price across deposits and withdrawals', () => {
      const totalValue = 100_000_000_000_000n;
      const totalSupply = 1_000_000_000_000n;
      const price1 = calculatePricePerShare(totalValue, totalSupply);

      // Deposit
      const depositAmount = 10_000_000_000n;
      const newShares = calculateDepositShares(depositAmount, totalValue, totalSupply);
      const newTotalValue = totalValue + depositAmount;
      const newTotalSupply = totalSupply + newShares;
      const price2 = calculatePricePerShare(newTotalValue, newTotalSupply);

      // Withdraw same amount (equivalent shares)
      const withdrawAmount = calculateWithdrawErg(newShares, newTotalValue, newTotalSupply);
      const finalTotalValue = newTotalValue - withdrawAmount;
      const finalTotalSupply = newTotalSupply - newShares;
      const price3 = calculatePricePerShare(finalTotalValue, finalTotalSupply);

      // Price should stay approximately the same
      const epsilon = 1n; // Allow 1 nanoERG difference due to rounding
      assert.ok(Math.abs(Number(price2 - price1)) <= Number(epsilon));
      assert.ok(Math.abs(Number(price3 - price1)) <= Number(epsilon));
    });
  });
});

