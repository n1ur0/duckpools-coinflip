/**
 * DuckPools SDK Type Definitions
 * TypeScript types for DuckPools Coinflip protocol interaction
 */

/**
 * Network type
 */
export type Network = 'mainnet' | 'testnet' | 'local';

/**
 * Bet choice
 */
export type BetChoice = 0 | 1; // 0 = heads, 1 = tails

/**
 * Register keys supported by Ergo
 */
export type RegisterKey = 'R4' | 'R5' | 'R6' | 'R7' | 'R8' | 'R9';

/**
 * SValue types for Sigma-state serialization
 */
export type SValue =
  | { type: 'Int'; value: number }
  | { type: 'Long'; value: bigint }
  | { type: 'Coll[Byte]'; value: string } // hex string
  | { type: 'Coll[SByte]'; value: string } // hex string
  | { type: 'SigmaProp'; value: string } // hex string
  | { type: 'Boolean'; value: boolean } // true = 0x07, false = 0x06
  | { type: 'Option'; value: SValue | null } // None = 0x0b, Some = 0x0b + inner_type
  | { type: 'Pair'; left: SValue; right: SValue }; // Tuple type 0x0d

/**
 * ErgoBox register
 */
export interface ErgoBoxRegister {
  value: string;
  serializedValue: string;
}

/**
 * ErgoBox asset
 */
export interface ErgoBoxAsset {
  tokenId: string;
  amount: bigint;
  name?: string;
  decimals?: number;
}

/**
 * ErgoBox on-chain representation
 */
export interface ErgoBox {
  boxId: string;
  value: bigint;
  ergoTree: string;
  creationHeight: number;
  assets: ErgoBoxAsset[];
  additionalRegisters: Record<RegisterKey, ErgoBoxRegister>;
  transactionId: string;
  index: number;
}

/**
 * PendingBetBox registers
 */
export interface PendingBetRegisters {
  R4: ErgoBoxRegister; // Player's ErgoTree
  R5: ErgoBoxRegister; // Commitment hash (32 bytes)
  R6: ErgoBoxRegister; // Bet choice (0=heads, 1=tails)
  R7: ErgoBoxRegister; // Player's random secret (8 bytes)
  R8: ErgoBoxRegister; // Bet ID (32 bytes)
  R9?: ErgoBoxRegister; // Timeout height (optional, for timeout/refund)
}

/**
 * PendingBetBox
 */
export interface PendingBetBox extends Omit<ErgoBox, 'additionalRegisters'> {
  additionalRegisters: PendingBetRegisters;
}

/**
 * Transaction output
 */
export interface TransactionOutput {
  address?: string;
  value: bigint;
  ergoTree?: string;
  assets?: ErgoBoxAsset[];
  additionalRegisters?: Record<RegisterKey, SValue>;
  creationHeight?: number;
}

/**
 * Transaction input
 */
export interface TransactionInput {
  boxId: string;
  /** Resolved box value in nanoERG (fetched from node) */
  value: bigint;
  extension?: Record<string, unknown>;
}

/**
 * Transaction
 */
export interface ErgoTransaction {
  inputs: TransactionInput[];
  dataInputs?: TransactionInput[];
  outputs: TransactionOutput[];
  fee?: bigint;
}

/**
 * Signed transaction
 */
export interface SignedTransaction {
  id: string;
  inputs: unknown[];
  dataInputs: unknown[];
  outputs: unknown[];
}

/**
 * Node info
 */
export interface NodeInfo {
  fullHeight: number;
  headersHeight: number;
  bestHeaderId: string;
  stateType: string;
  isMining: boolean;
  peersCount: number;
  unconfirmedCount: number;
  UTXOSize: number;
}

/**
 * Wallet balance
 */
export interface WalletBalance {
  height: number;
  balance: bigint;
  assets: Record<string, bigint>;
}

/**
 * Unspent box
 */
export interface UnspentBox {
  boxId: string;
  value: bigint;
  ergoTree: string;
  assets: ErgoBoxAsset[];
  creationHeight: number;
  index: number;
  transactionId: string;
}

/**
 * Bet result
 */
export type BetResult = 'win' | 'lose';

/**
 * Bet status
 */
export type BetStatus = 'pending' | 'revealed' | 'refunded' | 'timeout';

/**
 * Bet info
 */
export interface BetInfo {
  betId: string;
  boxId: string;
  playerAddress: string;
  betAmount: bigint;
  betChoice: BetChoice;
  commitment: string;
  secret?: string;
  status: BetStatus;
  result?: BetResult;
  payout?: bigint;
  createdAt: number;
  revealedAt?: number;
  timeoutHeight?: number;
}

/**
 * Pool state
 */
export interface PoolState {
  liquidity: bigint;
  houseEdge: number; // percentage (e.g., 0.03 for 3%)
  totalValueLocked: bigint;
  pendingBets: number;
  completedBets: number;
}

/**
 * Place bet options
 */
export interface PlaceBetOptions {
  amount: bigint;
  choice: BetChoice;
  secret?: string; // If not provided, one will be generated
  timeoutDelta?: number; // Blocks until timeout (e.g., 100)
  /** UTXO inputs to spend — caller must provide resolved box values */
  inputs?: Array<{ boxId: string; value: bigint }>;
}

/**
 * Place bet result
 */
export interface PlaceBetResult {
  betId: string;
  boxId: string;
  transactionId: string;
  commitment: string;
  secret: string;
  timeoutHeight: number;
}

/**
 * Reveal bet options
 */
export interface RevealBetOptions {
  boxId: string;
  secret: string;
  choice: BetChoice;
}

/**
 * Reveal bet result
 */
export interface RevealBetResult {
  transactionId: string;
  betId: string;
  result: BetResult;
  payout: bigint;
  blockHash: string;
  rngHash: string;
  /** Block height used for RNG seed */
  rngHeight: number;
}

/**
 * Refund bet options
 */
export interface RefundBetOptions {
  boxId: string;
  refundAddress: string;
}

/**
 * Refund bet result
 */
export interface RefundBetResult {
  transactionId: string;
  betId: string;
  refundAmount: bigint;
}

/**
 * Node client configuration
 */
export interface NodeClientConfig {
  url: string;
  apiKey?: string;
  timeout?: number;
}

/**
 * DuckPools client configuration
 */
export interface DuckPoolsClientConfig extends NodeClientConfig {
  network: Network;
  houseAddress?: string;
  coinflipNftId?: string;
  pendingBetAddress?: string;
  pendingBetErgoTree?: string;
}

/**
 * Commit-Reveal pair
 */
export interface CommitRevealPair {
  secret: string;
  commitment: string;
  choice: BetChoice;
}

/**
 * RNG parameters
 */
export interface RNGParams {
  blockHash: string;
  secret: string;
}

/**
 * Transaction building options
 */
export interface TransactionBuilderOptions {
  fee?: bigint;
  changeAddress?: string;
  minBoxValue?: bigint;
}

/**
 * Error types
 */
export class DuckPoolsError extends Error {
  constructor(
    message: string,
    public code: string,
    public details?: unknown
  ) {
    super(message);
    this.name = 'DuckPoolsError';
  }
}

export class NodeError extends DuckPoolsError {
  constructor(message: string, public statusCode: number, details?: unknown) {
    super(message, 'NODE_ERROR', details);
    this.name = 'NodeError';
  }
}

export class SerializationError extends DuckPoolsError {
  constructor(message: string, details?: unknown) {
    super(message, 'SERIALIZATION_ERROR', details);
    this.name = 'SerializationError';
  }
}

export class BetError extends DuckPoolsError {
  constructor(message: string, details?: unknown) {
    super(message, 'BET_ERROR', details);
    this.name = 'BetError';
  }
}

export class TimeoutError extends DuckPoolsError {
  constructor(message: string, details?: unknown) {
    super(message, 'TIMEOUT_ERROR', details);
    this.name = 'TimeoutError';
  }
}
