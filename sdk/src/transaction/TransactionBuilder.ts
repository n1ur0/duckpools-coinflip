/**
 * DuckPools SDK - Transaction Builder
 * Builds Ergo transactions for the coinflip protocol.
 *
 * Handles input/output balancing, fee deduction, and change box creation.
 * Callers must provide resolved input box values (fetched from node).
 */

import { Buffer } from 'buffer';
import type {
  ErgoTransaction,
  TransactionInput,
  TransactionOutput,
  SValue,
  TransactionBuilderOptions,
} from '../types';
import { serializeSValue } from '../serialization';

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
   *
   * Computes input/output balance, deducts fee, and creates a change
   * box if there is leftover ERG after outputs + fee.
   *
   * @throws Error if output value + fee exceeds input value
   */
  build(
    inputs: TransactionInput[],
    outputs: TransactionOutput[]
  ): ErgoTransaction {
    if (inputs.length === 0) {
      throw new Error('Transaction must have at least one input');
    }

    // Sum input values from resolved boxes
    const totalInputValue = inputs.reduce((sum, input) => sum + input.value, 0n);

    // Sum output values
    const totalOutputValue = outputs.reduce((sum, output) => sum + output.value, 0n);

    // Total cost = outputs + fee
    const totalCost = totalOutputValue + this.fee;

    // Validate: outputs + fee must not exceed inputs
    if (totalCost > totalInputValue) {
      throw new Error(
        `Insufficient input value: inputs=${totalInputValue} nanoERG, ` +
        `outputs=${totalOutputValue} nanoERG, fee=${this.fee} nanoERG, ` +
        `shortfall=${totalCost - totalInputValue} nanoERG`
      );
    }

    // Compute change amount
    const changeValue = totalInputValue - totalCost;
    const allOutputs = [...outputs];

    if (changeValue > 0n) {
      if (!this.changeAddress) {
        throw new Error(
          'Change address required: transaction has ' +
          `${changeValue} nanoERG unspent. Call setChangeAddress() first.`
        );
      }

      if (changeValue >= this.minBoxValue) {
        allOutputs.push({
          address: this.changeAddress,
          value: changeValue,
        });
      } else {
        // Dust change — absorb into fee to avoid creating a box below minBoxValue
        this.fee += changeValue;
      }
    }

    return {
      inputs,
      outputs: allOutputs,
      fee: this.fee,
    };
  }

  /**
   * Build bet placement transaction
   * Creates a PendingBetBox with commitment and other registers
   *
   * Register layout MUST match smart contracts (coinflip_v1.es, dice_v1.es, plinko_v1.es):
   *   R4:  housePubKey    (Coll[Byte]) — house's compressed public key (33 bytes)
   *   R5:  playerPubKey   (Coll[Byte]) — player's compressed public key
   *   R6:  commitmentHash (Coll[Byte]) — blake2b256(secret || choice)
   *   R7:  playerChoice   (Int)        — 0=heads/1=tails for coinflip
   *   R8:  playerSecret   (Int)        — player's random secret
   *   R9:  betId          (Coll[Byte]) — unique bet identifier
   *   R10: timeoutHeight  (Int)        — block height for timeout/refund
   *
   * CRITICAL (SEC-CRITICAL-6): This layout was fixed to match on-chain contracts.
   * Previous SDK layout was completely different — see GitHub issue #211.
   */
  buildPlaceBetTransaction(params: {
    playerAddress: string;
    pendingBetAddress: string;
    amount: bigint;
    housePubKey: string;       // House's compressed public key (hex, 33 bytes)
    playerPubKey: string;      // Player's compressed public key (hex)
    commitment: string;        // blake2b256 hash (hex)
    choice: number;            // Player's choice (game-specific)
    secret: number;            // Player's random secret as Int
    betId: string;             // Unique bet identifier (hex)
    timeoutHeight: number;     // Block height for timeout
    inputBoxId: string;
    inputBoxValue: bigint;
  }): ErgoTransaction {
    const output: TransactionOutput = {
      address: params.pendingBetAddress,
      value: params.amount,
      additionalRegisters: {
        R4: { type: 'Coll[Byte]' as const, value: params.housePubKey },
        R5: { type: 'Coll[Byte]' as const, value: params.playerPubKey },
        R6: { type: 'Coll[Byte]' as const, value: params.commitment },
        R7: { type: 'Int' as const, value: params.choice },
        R8: { type: 'Int' as const, value: params.secret },
        R9: { type: 'Coll[Byte]' as const, value: params.betId },
        R10: { type: 'Int' as const, value: params.timeoutHeight },
      } as Record<string, SValue>,
    }

    return this.build(
      [{ boxId: params.inputBoxId, value: params.inputBoxValue }],
      [output]
    );
  }

  /**
   * Build reveal transaction
   * Spends PendingBetBox and sends winnings/losses
   */
  buildRevealTransaction(params: {
    betBoxId: string;
    betBoxValue: bigint;
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
      [{ boxId: params.betBoxId, value: params.betBoxValue }],
      [output]
    );
  }

  /**
   * Build refund transaction
   * Spends expired PendingBetBox and returns funds to player
   */
  buildRefundTransaction(params: {
    betBoxId: string;
    betBoxValue: bigint;
    playerAddress: string;
    betAmount: bigint;
  }): ErgoTransaction {
    const output: TransactionOutput = {
      address: params.playerAddress,
      value: params.betAmount,
    };

    return this.build(
      [{ boxId: params.betBoxId, value: params.betBoxValue }],
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
                { value: serializeSValue(v), type: v.type },
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
                { value: serializeSValue(v), type: v.type },
              ])
            )
          : undefined,
        creationHeight: output.creationHeight,
      })),
      rawInputs: tx.inputs.map(input => input.boxId),
      fee: tx.fee?.toString(),
    };
  }
}
