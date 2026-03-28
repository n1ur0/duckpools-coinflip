/**
 * DuckPools SDK - Bet Manager
 * High-level interface for bet operations: place, reveal, refund
 */

import type {
  PlaceBetOptions,
  PlaceBetResult,
  RevealBetOptions,
  RevealBetResult,
  RefundBetOptions,
  RefundBetResult,
  PendingBetBox,
  BetResult,
} from '../types';
import { BetError } from '../types';
import { NodeClient } from '../client/NodeClient';
import { TransactionBuilder } from '../transaction/TransactionBuilder';
import { generateSecret, generateCommit, computeRng } from '../crypto';

export class BetManager {
  private nodeClient: NodeClient;
  private txBuilder: TransactionBuilder;
  private pendingBetAddress: string;
  private houseAddress: string;
  private houseEdge: number;
  private network: 'mainnet' | 'testnet' | 'local';

  constructor(config: {
    nodeClient: NodeClient;
    txBuilder?: TransactionBuilder;
    pendingBetAddress: string;
    houseAddress: string;
    houseEdge?: number;
    network?: 'mainnet' | 'testnet' | 'local';
  }) {
    this.nodeClient = config.nodeClient;
    this.txBuilder = config.txBuilder || new TransactionBuilder();
    this.pendingBetAddress = config.pendingBetAddress;
    this.houseAddress = config.houseAddress;
    this.houseEdge = config.houseEdge || 0.03;
    this.network = config.network || 'testnet';
  }

  /**
   * Place a bet (commit phase)
   *
   * Process:
   * 1. Generate random secret (if not provided)
   * 2. Compute commitment: blake2b256(secret || choice)
   * 3. Build transaction creating PendingBetBox
   * 4. Submit transaction
   *
   * @param options - Bet placement options
   * @returns Bet placement result with transaction ID and commitment
   */
  async placeBet(options: PlaceBetOptions): Promise<PlaceBetResult> {
    // Validate bet amount
    if (options.amount <= 0n) {
      throw new BetError('Bet amount must be positive');
    }

    // Validate choice
    if (options.choice !== 0 && options.choice !== 1) {
      throw new BetError('Bet choice must be 0 (heads) or 1 (tails)');
    }

    // Generate secret if not provided
    const secret = options.secret || generateSecret();

    // Compute commitment
    const { commitment } = await generateCommit(secret, options.choice);

    // Generate bet ID (SHA256 of commitment + timestamp)
    const betId = await this.generateBetId(commitment);

    // Get current height for timeout
    const currentHeight = await this.nodeClient.getCurrentHeight();
    const timeoutDelta = options.timeoutDelta || 100;
    const timeoutHeight = currentHeight + timeoutDelta;

    // Build bet transaction
    const tx = this.txBuilder.buildPlaceBetTransaction({
      playerAddress: this.pendingBetAddress,
      pendingBetAddress: this.pendingBetAddress,
      amount: options.amount,
      commitment,
      choice: options.choice,
      secret,
      betId,
      timeoutHeight,
      inputBoxId: '', // Will be filled by wallet
      inputBoxValue: 0n, // Will be filled by wallet
    });

    // Submit transaction
    const txResult = await this.nodeClient.submitTransaction(
      this.txBuilder.toWalletFormat(tx)
    );

    return {
      betId,
      boxId: '', // Will be filled from transaction outputs
      transactionId: txResult.txId,
      commitment,
      secret,
      timeoutHeight,
    };
  }

  /**
   * Reveal a bet (reveal phase)
   *
   * Process:
   * 1. Get bet box from blockchain
   * 2. Verify secret and commitment match
   * 3. Get block hash for RNG
   * 4. Compute outcome: blake2b256(blockHash || secret)[0] % 2
   * 5. Build settlement transaction
   * 6. Submit transaction
   *
   * @param options - Reveal options
   * @returns Reveal result with outcome and payout
   */
  async revealBet(options: RevealBetOptions): Promise<RevealBetResult> {
    // Get bet box
    const betBox = await this.getBetBox(options.boxId);
    if (!betBox) {
      throw new BetError(`Bet box ${options.boxId} not found`);
    }

    // Verify commitment matches
    const r5Value = betBox.additionalRegisters.R5.serializedValue;
    const commitment = r5Value; // Placeholder
    const betChoice = options.choice;

    // Verify commitment
    const isValid = await this.verifyCommit(commitment, options.secret, betChoice);
    if (!isValid) {
      throw new BetError('Secret does not match commitment');
    }

    // Get block hash for RNG — use bet confirmation height, not current height
    // Using current height gives the bot a timing attack (SDK-SEC-2).
    // The PendingBetBox creationHeight is deterministic and unchangeable.
    const rngHeight = betBox.creationHeight;
    const blockHash = await this.getBlockHash(rngHeight);

    // Compute outcome
    const outcome = await computeRng(blockHash, options.secret);
    const result: BetResult = outcome === betChoice ? 'win' : 'lose';

    // Calculate payout
    const betAmount = betBox.value;
    const payout = this.calculatePayout(betAmount, result);

    // Build reveal transaction
    const tx = this.txBuilder.buildRevealTransaction({
      betBoxId: options.boxId,
      betBoxValue: betBox.value,
      houseAddress: this.houseAddress,
      playerAddress: '', // Will be filled from R4 register
      betAmount,
      result,
      houseEdge: this.houseEdge,
      blockHash,
      secret: options.secret,
    });

    // Submit transaction
    const txResult = await this.nodeClient.submitTransaction(
      this.txBuilder.toWalletFormat(tx)
    );

    // Calculate RNG hash for reference
    const rngHash = await this.computeRngHash(blockHash, options.secret);

    return {
      transactionId: txResult.txId,
      betId: betBox.additionalRegisters.R8.serializedValue,
      result,
      payout,
      blockHash,
      rngHeight,
      rngHash,
    };
  }

  /**
   * Refund expired bet
   *
   * Process:
   * 1. Get bet box from blockchain
   * 2. Verify timeout has passed
   * 3. Build refund transaction
   * 4. Submit transaction
   *
   * @param options - Refund options
   * @returns Refund result
   */
  async refundBet(options: RefundBetOptions): Promise<RefundBetResult> {
    // Get bet box
    const betBox = await this.getBetBox(options.boxId);
    if (!betBox) {
      throw new BetError(`Bet box ${options.boxId} not found`);
    }

    // Check for timeout register
    const r9 = betBox.additionalRegisters.R9;
    if (!r9) {
      throw new BetError('Bet box does not have timeout register');
    }

    // Verify timeout has passed
    const currentHeight = await this.nodeClient.getCurrentHeight();
    const timeoutHeight = Number(r9.serializedValue); // Deserialize Int

    if (currentHeight < timeoutHeight) {
      throw new BetError(
        `Timeout not reached: current=${currentHeight}, timeout=${timeoutHeight}`
      );
    }

    // Build refund transaction
    const tx = this.txBuilder.buildRefundTransaction({
      betBoxId: options.boxId,
      betBoxValue: betBox.value,
      playerAddress: options.refundAddress,
      betAmount: betBox.value,
    });

    // Submit transaction
    const txResult = await this.nodeClient.submitTransaction(
      this.txBuilder.toWalletFormat(tx)
    );

    return {
      transactionId: txResult.txId,
      betId: betBox.additionalRegisters.R8.serializedValue,
      refundAmount: betBox.value,
    };
  }

  /**
   * Get bet box by ID
   */
  async getBetBox(boxId: string): Promise<PendingBetBox | null> {
    try {
      const box = await this.nodeClient.getBoxById(boxId);
      return box as PendingBetBox;
    } catch (_error) {
      return null;
    }
  }

  /**
   * Generate bet ID
   */
  private async generateBetId(commitment: string): Promise<string> {
    const timestamp = Date.now().toString();
    const { sha256 } = await import('../crypto');
    const hash = await sha256(Buffer.from(commitment + timestamp, 'utf8'));
    return hash.toString('hex');
  }

  /**
   * Verify commitment matches secret and choice
   */
  private async verifyCommit(
    commitment: string,
    secret: string,
    choice: number
  ): Promise<boolean> {
    const { commitment: computed } = await generateCommit(secret, choice);
    return commitment.toLowerCase() === computed.toLowerCase();
  }

  /**
   * Get block hash at height.
   *
   * SECURITY (SDK-SEC-1): Never falls back to a deterministic placeholder.
   * If the block hash cannot be obtained, the reveal MUST fail.
   * A silent fallback would allow an attacker who disrupts node
   * connectivity to force a known RNG outcome via SHA256(known_hash || secret).
   */
  private async getBlockHash(height: number): Promise<string> {
    const blockInfo = await this.nodeClient.getBlockHeaderByHeight(height);
    const hash = blockInfo.headerId || blockInfo.id;

    if (!hash) {
      throw new BetError(
        `Cannot determine block hash for height ${height} — ` +
        `node returned unexpected format. Aborting reveal to prevent RNG manipulation.`
      );
    }

    // Defense-in-depth: reject obviously fake hashes
    if (hash === 'placeholder_block_hash' || hash === 'unknown_block_hash') {
      throw new BetError(
        `Suspicious block hash at height ${height}: "${hash}". ` +
        `Aborting reveal to prevent RNG manipulation.`
      );
    }

    return hash;
  }

  /**
   * Calculate payout based on result
   */
  private calculatePayout(betAmount: bigint, result: BetResult): bigint {
    if (result === 'win') {
      // Win: 2x bet amount (minus house edge)
      const winMultiplier = 2 * (1 - this.houseEdge);
      return (betAmount * BigInt(Math.round(winMultiplier * 10000))) / 10000n;
    } else {
      // Lose: no payout
      return 0n;
    }
  }

  /**
   * Compute RNG hash for reference
   */
  private async computeRngHash(blockHash: string, secret: string): Promise<string> {
    const { sha256 } = await import('../crypto');
    const hash = await sha256(
      Buffer.concat([Buffer.from(blockHash, 'utf8'), Buffer.from(secret, 'hex')])
    );
    return hash.toString('hex');
  }
}
