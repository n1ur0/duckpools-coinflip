/**
 * DuckPools SDK - Transaction Builder
 * Builds Ergo transactions for the coinflip protocol.
 *
 * Handles input/output balancing, fee deduction, and change box creation.
 * Callers must provide resolved input box values (fetched from node or wallet).
 *
 * Output formats:
 *   - toEIP12Object()  — for browser wallet signing (Nautilus EIP-12)
 *   - toWalletFormat()  — for node wallet API (/wallet/transaction/send)
 *   - toPaymentFormat() — for node payment API (/wallet/payment/send)
 */

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
  private creationHeight: number | undefined;

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
   * Set creation height (block height when the transaction is created)
   */
  setCreationHeight(height: number): this {
    this.creationHeight = height;
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
   * Register layout MUST match coinflip_v2.es (compiled 2026-03-28):
   *   R4: Coll[Byte] — house's compressed public key (33 bytes)
   *   R5: Coll[Byte] — player's compressed public key (33 bytes)
   *   R6: Coll[Byte] — blake2b256(playerSecret ++ Coll(choiceByte))
   *   R7: Int        — player's choice: 0=heads, 1=tails
   *   R8: Int        — block height for timeout/refund
   *   R9: Coll[Byte] — player's random secret (raw bytes)
   *
   * NOTE: Ergo boxes only have R0-R9. R0-R3 are reserved. No R10.
   * NOTE: betId is tracked off-chain only, NOT in contract registers.
   * NOTE: Contract uses blake2b256(playerSecret ++ Coll(choiceByte))
   *       where playerSecret is raw bytes (R9) and choiceByte is 0 or 1.
   *
   * @param inputs - UTXO inputs to spend (from wallet.getUtxos())
   *   Each input needs boxId and value. The wallet handles signing proofs.
   */
  buildPlaceBetTransaction(params: {
    playerAddress: string;
    pendingBetAddress: string;
    amount: bigint;
    housePubKey: string;       // House's compressed public key (hex, 33 bytes)
    playerPubKey: string;      // Player's compressed public key (hex, 33 bytes)
    commitment: string;        // blake2b256(playerSecret ++ Coll(choiceByte)) (hex, 64 chars)
    choice: number;            // Player's choice: 0=heads, 1=tails
    secret: string;            // Player's random secret as hex string (raw bytes as hex)
    timeoutHeight: number;     // Block height for timeout/refund
    inputs: Array<{ boxId: string; value: bigint }>; // UTXO inputs from wallet
    gameNftId?: string;        // Optional NFT token ID for off-chain indexing
  }): ErgoTransaction {
    const output: TransactionOutput = {
      address: params.pendingBetAddress,
      value: params.amount,
      creationHeight: this.creationHeight,
      additionalRegisters: {
        R4: { type: 'Coll[Byte]' as const, value: params.housePubKey },
        R5: { type: 'Coll[Byte]' as const, value: params.playerPubKey },
        R6: { type: 'Coll[Byte]' as const, value: params.commitment },
        R7: { type: 'Int' as const, value: params.choice },
        R8: { type: 'Int' as const, value: params.timeoutHeight },
        R9: { type: 'Coll[Byte]' as const, value: params.secret },
      } as Record<string, SValue>,
    };

    // Optionally add NFT to the output for off-chain indexing
    if (params.gameNftId) {
      output.assets = [{ tokenId: params.gameNftId, amount: 1n }];
    }

    return this.build(
      params.inputs,
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
      creationHeight: this.creationHeight,
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
      creationHeight: this.creationHeight,
    };

    return this.build(
      [{ boxId: params.betBoxId, value: params.betBoxValue }],
      [output]
    );
  }

  // ─── Format Converters ───────────────────────────────────────────

  /**
   * Convert transaction to EIP-12 format for browser wallet signing.
   *
   * EIP-12 (Ergo Improvement Proposal 12) defines the format that
   * Nautilus and other browser wallets expect for signTransaction().
   *
   * This is the primary format for frontend wallet integration.
   */
  toEIP12Object(tx: ErgoTransaction): EIP12UnsignedTransaction {
    return {
      inputs: tx.inputs.map(input => ({
        boxId: input.boxId,
        extension: input.extension ?? {},
      })),
      dataInputs: tx.dataInputs?.map(input => ({
        boxId: input.boxId,
        extension: input.extension ?? {},
      })) ?? [],
      outputs: tx.outputs.map(output => {
        const eip12Output: EIP12Output = {
          value: output.value.toString(),
          ergoTree: output.ergoTree ?? '',
          creationHeight: output.creationHeight ?? 0,
          assets: output.assets?.map(a => ({
            tokenId: a.tokenId,
            amount: a.amount.toString(),
          })) ?? [],
          additionalRegisters: {},
        };

        // Serialize registers using Sigma-state encoding
        if (output.additionalRegisters) {
          for (const [key, svalue] of Object.entries(output.additionalRegisters)) {
            eip12Output.additionalRegisters[key] = serializeSValue(svalue);
          }
        }

        return eip12Output;
      }),
      fee: tx.fee?.toString() ?? '0',
    };
  }

  /**
   * Convert transaction to node wallet format
   * For /wallet/transaction/send endpoint
   */
  toWalletFormat(tx: ErgoTransaction): any {
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
   * For /wallet/payment/send endpoint
   */
  toPaymentFormat(tx: ErgoTransaction): any {
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

// ─── EIP-12 Type Definitions ──────────────────────────────────────

/**
 * EIP-12 unsigned transaction format.
 * This is what Nautilus (and other EIP-12 wallets) expect for signTransaction().
 *
 * Reference: https://github.com/ergoplatform/eips/blob/eip-12/eip-12.md
 */
export interface EIP12UnsignedTransaction {
  inputs: Array<{
    boxId: string;
    extension: Record<string, unknown>;
  }>;
  dataInputs: Array<{
    boxId: string;
    extension: Record<string, unknown>;
  }>;
  outputs: EIP12Output[];
  fee: string;
}

/**
 * EIP-12 output box format.
 */
export interface EIP12Output {
  value: string;
  ergoTree: string;
  creationHeight: number;
  assets: Array<{
    tokenId: string;
    amount: string;
  }>;
  additionalRegisters: Record<string, string>;
}
