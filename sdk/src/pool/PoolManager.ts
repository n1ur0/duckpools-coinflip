/**
 * DuckPools SDK - Pool Manager
 * High-level interface for liquidity pool operations: deposit, withdraw, query
 *
 * MAT-15: Tokenized bankroll and liquidity pool
 */

import { NodeClient } from '../client/NodeClient.js';
import type {
  PoolState as OnChainPoolState,
  WithdrawalRequest,
} from './BankrollPool.js';
import {
  calculatePricePerShare,
  calculateDepositShares,
  calculateWithdrawErg,
  calculateAPY,
  POOL_CONFIG,
} from './BankrollPool.js';
import type { DuckPoolsError } from '../types/index.js';

export class PoolManager {
  private nodeClient: NodeClient;
  private poolNftId: string;
  private lpTokenId: string;
  private network: 'mainnet' | 'testnet' | 'local';

  constructor(config: {
    nodeClient: NodeClient;
    poolNftId: string;
    lpTokenId: string;
    network?: 'mainnet' | 'testnet' | 'local';
  }) {
    this.nodeClient = config.nodeClient;
    this.poolNftId = config.poolNftId;
    this.lpTokenId = config.lpTokenId;
    this.network = config.network || 'testnet';
  }

  /**
   * Get the current pool state from on-chain data
   * Queries the BankrollBox and PendingBet boxes
   */
  async getPoolState(): Promise<OnChainPoolState> {
    // Get the BankrollBox by Pool NFT
    const poolBoxes = await this.nodeClient.getBoxesByTokenId(this.poolNftId);
    if (!poolBoxes || poolBoxes.length === 0) {
      throw new Error('Bankroll pool box not found');
    }

    const poolBox = poolBoxes[0];
    const bankroll = BigInt(poolBox.value || 0);

    // Extract LP token info from pool box
    const lpToken = poolBox.assets?.find(
      (a: any) => a.tokenId === this.lpTokenId
    );
    const totalSupply = lpToken ? BigInt(lpToken.amount) : 0n;

    // Extract pool parameters from registers
    let houseEdgeBps: number = POOL_CONFIG.HOUSE_EDGE_BPS;
    let cooldownBlocks: number = POOL_CONFIG.COOLDOWN_BLOCKS;

    if (poolBox.additionalRegisters?.R7) {
      houseEdgeBps = this.deserializeInt(poolBox.additionalRegisters.R7);
    }
    if (poolBox.additionalRegisters?.R6) {
      cooldownBlocks = this.deserializeInt(poolBox.additionalRegisters.R6);
    }

    // Get pending bets value (from PendingBet boxes using coinflip NFT)
    const pendingBets = 0;
    const pendingBetsValue = 0n;

    const totalValue = bankroll + pendingBetsValue;

    return {
      bankroll,
      totalSupply,
      pendingBets,
      pendingBetsValue,
      totalValue,
      pricePerShare: calculatePricePerShare(totalValue, totalSupply),
      houseEdgeBps,
      cooldownBlocks,
      poolNftId: this.poolNftId,
      lpTokenId: this.lpTokenId,
    };
  }

  /**
   * Get LP token balance for an address
   */
  async getLpBalance(address: string): Promise<bigint> {
    const boxes = await this.nodeClient.getBoxesByTokenId(this.lpTokenId);
    if (!boxes) return 0n;

    let totalBalance = 0n;
    for (const box of boxes) {
      // Check if box belongs to this address
      if (box.address === address || box.ergoTree) {
        const lpToken = box.assets?.find(
          (a: any) => a.tokenId === this.lpTokenId
        );
        if (lpToken) {
          totalBalance += BigInt(lpToken.amount);
        }
      }
    }
    return totalBalance;
  }

  /**
   * Get all pending withdrawal requests
   */
  async getWithdrawalRequests(): Promise<WithdrawalRequest[]> {
    const boxes = await this.nodeClient.getBoxesByTokenId(this.lpTokenId);
    if (!boxes) return [];

    const currentHeight = await this.nodeClient.getCurrentHeight();
    const requests: WithdrawalRequest[] = [];

    for (const box of boxes) {
      // Filter to WithdrawRequest boxes (not BankrollBox, not user wallets)
      // WithdrawRequest boxes have specific register structure
      if (box.additionalRegisters?.R6) {
        const requestHeight = this.deserializeInt(box.additionalRegisters.R6);
        const cooldownDelta = box.additionalRegisters?.R7
          ? this.deserializeInt(box.additionalRegisters.R7)
          : POOL_CONFIG.COOLDOWN_BLOCKS;

        const lpToken = box.assets?.find(
          (a: any) => a.tokenId === this.lpTokenId
        );

        requests.push({
          boxId: box.boxId,
          holderAddress: '', // Would be deserialized from R4
          lpAmount: lpToken ? BigInt(lpToken.amount) : 0n,
          requestedErg: box.additionalRegisters?.R5
            ? BigInt(this.deserializeLong(box.additionalRegisters.R5))
            : 0n,
          requestHeight,
          cooldownDelta,
          executableHeight: requestHeight + cooldownDelta,
          isMature: currentHeight >= requestHeight + cooldownDelta,
        });
      }
    }

    return requests;
  }

  /**
   * Get matured withdrawal requests (ready to execute)
   */
  async getMaturedWithdrawals(): Promise<WithdrawalRequest[]> {
    const allRequests = await this.getWithdrawalRequests();
    return allRequests.filter((r) => r.isMature);
  }

  /**
   * Calculate shares for a deposit
   */
  async estimateDeposit(amount: bigint): Promise<{
    shares: bigint;
    pricePerShare: bigint;
    newValue: bigint;
  }> {
    const state = await this.getPoolState();
    const shares = calculateDepositShares(
      amount,
      state.totalValue,
      state.totalSupply
    );
    return {
      shares,
      pricePerShare: state.pricePerShare,
      newValue: state.totalValue + amount,
    };
  }

  /**
   * Calculate ERG for a withdrawal
   */
  async estimateWithdraw(shares: bigint): Promise<{
    ergAmount: bigint;
    pricePerShare: bigint;
    newValue: bigint;
  }> {
    const state = await this.getPoolState();
    const ergAmount = calculateWithdrawErg(
      shares,
      state.totalValue,
      state.totalSupply
    );
    return {
      ergAmount,
      pricePerShare: state.pricePerShare,
      newValue: state.totalValue - ergAmount,
    };
  }

  /**
   * Calculate APY based on pool metrics
   */
  async calculatePoolAPY(
    avgBetSize: bigint,
    betsPerBlock: number
  ): Promise<number> {
    const state = await this.getPoolState();
    return calculateAPY(
      state.houseEdgeBps,
      avgBetSize,
      betsPerBlock,
      state.bankroll
    );
  }

  // --- Private Helpers ---

  private deserializeInt(register: any): number {
    const serialized = register.serializedValue || register.value;
    if (!serialized) return 0;

    const hex = typeof serialized === 'string' ? serialized : String(serialized);
    const buffer = Buffer.from(hex, 'hex');

    if (buffer[0] !== 0x02) return 0;

    // Decode VLQ
    let value = 0;
    let shift = 0;
    for (let i = 1; i < buffer.length; i++) {
      const byte = buffer[i]!;
      value |= (byte & 0x7f) << shift;
      if ((byte & 0x80) === 0) break;
      shift += 7;
    }

    // ZigZag decode
    return (value >>> 1) ^ -(value & 1);
  }

  private deserializeLong(register: any): bigint {
    const serialized = register.serializedValue || register.value;
    if (!serialized) return 0n;

    const hex = typeof serialized === 'string' ? serialized : String(serialized);
    const buffer = Buffer.from(hex, 'hex');

    if (buffer[0] !== 0x04) return 0n;

    let value = 0n;
    let shift = 0n;
    for (let i = 1; i < buffer.length; i++) {
      const byte = BigInt(buffer[i]!);
      value |= (byte & 0x7fn) << shift;
      if ((byte & 0x80n) === 0n) break;
      shift += 7n;
    }

    return (value >> 1n) ^ -(value & 1n);
  }
}
