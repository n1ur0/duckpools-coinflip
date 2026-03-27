/**
 * DuckPools SDK - Main Client
 * High-level client for interacting with DuckPools Coinflip protocol
 */

import { NodeClient } from './NodeClient';
import { TransactionBuilder } from '../transaction/TransactionBuilder';
import { BetManager } from '../bet/BetManager';
import { generateCommit, computeRng, generateSecret } from '../crypto';
import type {
  DuckPoolsClientConfig,
  NodeInfo,
  PoolState,
  PlaceBetOptions,
  PlaceBetResult,
  RevealBetOptions,
  RevealBetResult,
  RefundBetOptions,
  RefundBetResult,
  BetInfo,
  PendingBetBox,
  WalletBalance,
} from '../types';

export class DuckPoolsClient {
  private nodeClient: NodeClient;
  private txBuilder: TransactionBuilder;
  private betManager: BetManager;
  private network: 'mainnet' | 'testnet' | 'local';
  private houseAddress: string;
  private coinflipNftId: string;
  private pendingBetAddress: string;

  constructor(config: DuckPoolsClientConfig) {
    this.network = config.network;
    this.houseAddress = config.houseAddress || '3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26';
    this.coinflipNftId = config.coinflipNftId || '';
    this.pendingBetAddress = config.pendingBetAddress || '';

    // Initialize node client
    this.nodeClient = new NodeClient({
      url: config.url,
      apiKey: config.apiKey,
      timeout: config.timeout,
    });

    // Initialize transaction builder
    this.txBuilder = new TransactionBuilder();

    // Initialize bet manager
    this.betManager = new BetManager({
      nodeClient: this.nodeClient,
      txBuilder: this.txBuilder,
      pendingBetAddress: this.pendingBetAddress,
      houseAddress: this.houseAddress,
      network: this.network,
    });
  }

  /**
   * Create a new DuckPools client instance
   */
  static create(config: DuckPoolsClientConfig): DuckPoolsClient {
    return new DuckPoolsClient(config);
  }

  /**
   * Get node info
   */
  async getNodeInfo(): Promise<NodeInfo> {
    return this.nodeClient.getInfo();
  }

  /**
   * Get current blockchain height
   */
  async getCurrentHeight(): Promise<number> {
    return this.nodeClient.getCurrentHeight();
  }

  /**
   * Get pool state
   */
  async getPoolState(): Promise<PoolState> {
    // In production, this would query the GameState box
    // For now, return a placeholder
    return {
      liquidity: 10000000000000n, // 10,000 ERG
      houseEdge: 0.03,
      totalValueLocked: 10000000000000n,
      pendingBets: 0,
      completedBets: 0,
    };
  }

  /**
   * Get pending bets
   */
  async getPendingBets(): Promise<PendingBetBox[]> {
    // Query boxes by NFT ID (coinflip NFT)
    if (!this.coinflipNftId) {
      return [];
    }

    const boxes = await this.nodeClient.getUnspentBoxesByTokenId(this.coinflipNftId);
    return boxes as PendingBetBox[];
  }

  /**
   * Get bet by ID
   */
  async getBetById(betId: string): Promise<BetInfo | null> {
    // In production, this would query by bet ID
    // For now, return null
    return null;
  }

  /**
   * Get bet history for address
   */
  async getBetHistory(_address: string, _limit = 20): Promise<BetInfo[]> {
    // In production, this would query blockchain for all bets involving address
    // For now, return empty array
    return [];
  }

  /**
   * Place a bet
   */
  async placeBet(options: PlaceBetOptions): Promise<PlaceBetResult> {
    return this.betManager.placeBet(options);
  }

  /**
   * Reveal a bet
   */
  async revealBet(options: RevealBetOptions): Promise<RevealBetResult> {
    return this.betManager.revealBet(options);
  }

  /**
   * Refund expired bet
   */
  async refundBet(options: RefundBetOptions): Promise<RefundBetResult> {
    return this.betManager.refundBet(options);
  }

  /**
   * Generate commitment for bet
   */
  async generateCommitment(secret: string | undefined, choice: number): Promise<{
    secret: string;
    commitment: string;
  }> {
    return generateCommit(secret, choice);
  }

  /**
   * Verify commitment matches
   */
  async verifyCommitment(
    commitment: string,
    secret: string,
    choice: number
  ): Promise<boolean> {
    const { commitment: computed } = await generateCommit(secret, choice);
    return commitment.toLowerCase() === computed.toLowerCase();
  }

  /**
   * Compute RNG outcome
   */
  async computeOutcome(blockHash: string, secret: string): Promise<number> {
    return computeRng(blockHash, secret);
  }

  /**
   * Generate random secret
   */
  generateSecret(): string {
    return generateSecret();
  }

  /**
   * Get wallet balance
   */
  async getWalletBalance(): Promise<WalletBalance> {
    return this.nodeClient.getWalletBalance();
  }

  /**
   * Get unspent boxes
   */
  async getUnspentBoxes(): Promise<any[]> {
    return this.nodeClient.getUnspentBoxes();
  }

  /**
   * Unlock wallet
   */
  async unlockWallet(password: string): Promise<void> {
    await this.nodeClient.unlockWallet(password);
  }

  /**
   * Get house address
   */
  getHouseAddress(): string {
    return this.houseAddress;
  }

  /**
   * Get coinflip NFT ID
   */
  getCoinflipNftId(): string {
    return this.coinflipNftId;
  }

  /**
   * Get pending bet address
   */
  getPendingBetAddress(): string {
    return this.pendingBetAddress;
  }

  /**
   * Get network type
   */
  getNetwork(): 'mainnet' | 'testnet' | 'local' {
    return this.network;
  }

  /**
   * Get node client (for advanced usage)
   */
  getNodeClient(): NodeClient {
    return this.nodeClient;
  }

  /**
   * Get transaction builder (for advanced usage)
   */
  getTransactionBuilder(): TransactionBuilder {
    return this.txBuilder;
  }

  /**
   * Get bet manager (for advanced usage)
   */
  getBetManager(): BetManager {
    return this.betManager;
  }
}
