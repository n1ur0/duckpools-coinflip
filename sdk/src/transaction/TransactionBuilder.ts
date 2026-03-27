/**
 * DuckPools SDK - Transaction Builder
 * Builds Ergo transactions using FleetSDK
 *
 * NOTE: This is a placeholder implementation that shows the interface.
 * In production, this would use @fleet-sdk/core for actual transaction building.
 */

import { Buffer } from 'buffer';
import type {
  ErgoTransaction,
  TransactionInput,
  TransactionOutput,
  SValue,
  TransactionBuilderOptions,
} from '../types';

export class TransactionBuilder {
  private fee: bigint;
  private changeAddress: string | undefined;
  private minBoxValue: bigint;

  constructor(options: TransactionBuilderOptions = {}) {
    this.fee = options.fee ?? 1000000n; // Default 0.001 ERG
    this.changeAddress = options.changeAddress;
    this.minBoxValue = options.minBoxValue ?? 100000n; // Default 0.0001 ERG
  }

  /**
   * Create a new transaction builder
   */
  static create(options?: TransactionBuilderOptions): TransactionBuilder {
    return new TransactionBuilder(options);
  }

  /**
   * Set fee for transaction
   */
  setFee(fee: bigint): this {
    this.fee = fee;
    return this;
  }

  /**
   * Set change address
   */
  setChangeAddress(address: string): this {
    this.changeAddress = address;
    return this;
  }

  /**
   * Build transaction from inputs and outputs
   */
  build(
    inputs: TransactionInput[],
    outputs: TransactionOutput[]
  ): ErgoTransaction {
    // Calculate total input value
    const totalInputValue = inputs.reduce((sum, input) => {
      // This would need actual box values from input boxes
      // For now, just return a placeholder
      return sum;
    }, 0n);

    // Calculate total output value
    const totalOutputValue = outputs.reduce((sum, output) => {
      return sum + output.value;
    }, 0n);

    // Validate transaction
    if (totalOutputValue > totalInputValue) {
      throw new Error('Output value exceeds input value');
    }

    return {
      inputs,
      outputs,
      fee: this.fee,
    };
  }

  /**
   * Build bet placement transaction
   * Creates a PendingBetBox with commitment and other registers
   */
  buildPlaceBetTransaction(params: {
    playerAddress: string;
    pendingBetAddress: string;
    amount: bigint;
    commitment: string;
    choice: number;
    secret: string;
    betId: string;
    timeoutHeight?: number;
    inputBoxId: string;
  }): ErgoTransaction {
    const output: TransactionOutput = {
      address: params.pendingBetAddress,
      value: params.amount,
      additionalRegisters: {
        R4: { type: 'Coll[Byte]' as const, value: '' }, // Player's ErgoTree - will be filled
        R5: { type: 'Coll[Byte]' as const, value: params.commitment },
        R6: { type: 'Int' as const, value: params.choice },
        R7: { type: 'Coll[Byte]' as const, value: Buffer.from(params.secret, 'hex').toString('hex') },
        R8: { type: 'Coll[Byte]' as const, value: params.betId },
        ...(params.timeoutHeight !== undefined ? {
          R9: { type: 'Int' as const, value: params.timeoutHeight },
        } : {}),
      } as Record<string, SValue>,
    }

    return this.build(
      [{ boxId: params.inputBoxId }],
      [output]
    );
  }

  /**
   * Build reveal transaction
   * Spends PendingBetBox and sends winnings/losses
   */
  buildRevealTransaction(params: {
    betBoxId: string;
    houseAddress: string;
    playerAddress: string;
    betAmount: bigint;
    result: 'win' | 'lose';
    houseEdge: number; // e.g., 0.03 for 3%
    blockHash: string;
    secret: string;
  }): ErgoTransaction {
    let payout: bigint;
    let recipient: string;

    if (params.result === 'win') {
      // Player wins: bet amount * (1 - house edge) * 2
      // But player already put in bet amount, so net payout is: bet * 2 * (1 - house edge) - bet
      const winMultiplier = 2 * (1 - params.houseEdge);
      payout = (params.betAmount * BigInt(Math.round(winMultiplier * 10000))) / 10000n;
      recipient = params.playerAddress;
    } else {
      // Player loses: bet goes to house
      payout = params.betAmount;
      recipient = params.houseAddress;
    }

    const output: TransactionOutput = {
      address: recipient,
      value: payout,
    };

    return this.build(
      [{ boxId: params.betBoxId }],
      [output]
    );
  }

  /**
   * Build refund transaction
   * Spends expired PendingBetBox and returns funds to player
   */
  buildRefundTransaction(params: {
    betBoxId: string;
    playerAddress: string;
    betAmount: bigint;
  }): ErgoTransaction {
    const output: TransactionOutput = {
      address: params.playerAddress,
      value: params.betAmount,
    };

    return this.build(
      [{ boxId: params.betBoxId }],
      [output]
    );
  }

  /**
   * Convert transaction to node wallet format
   */
  toWalletFormat(tx: ErgoTransaction): any {
    // Convert to format expected by /wallet/transaction/send
    return {
      requests: tx.outputs.map(output => ({
        address: output.address,
        value: output.value.toString(),
        ergoTree: output.ergoTree,
        assets: output.assets?.map(a => ({
          tokenId: a.tokenId,
          amount: a.amount.toString(),
        })),
        registers: output.additionalRegisters
          ? Object.fromEntries(
              Object.entries(output.additionalRegisters).map(([k, v]) => [
                k,
                { value: v.value.toString(), type: v.type },
              ])
            )
          : undefined,
        creationHeight: output.creationHeight,
      })),
      inputsRaw: tx.inputs.map(input => input.boxId),
      fee: tx.fee?.toString(),
    };
  }

  /**
   * Convert transaction to payment format
   */
  toPaymentFormat(tx: ErgoTransaction): any {
    // Convert to format expected by /wallet/payment/send
    return {
      requests: tx.outputs.map(output => ({
        address: output.address,
        value: output.value.toString(),
        ergoTree: output.ergoTree,
        assets: output.assets?.map(a => ({
          tokenId: a.tokenId,
          amount: a.amount.toString(),
        })),
        registers: output.additionalRegisters
          ? Object.fromEntries(
              Object.entries(output.additionalRegisters).map(([k, v]) => [
                k,
                { value: v.value.toString(), type: v.type },
              ])
            )
          : undefined,
      })),
      rawInputs: tx.inputs.map(input => input.boxId),
      fee: tx.fee?.toString(),
    };
  }
}
