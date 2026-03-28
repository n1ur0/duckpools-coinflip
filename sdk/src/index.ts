/**
 * DuckPools SDK - Main Entry Point
 * TypeScript SDK for DuckPools Coinflip protocol interaction
 */

// Types
export * from './types';

// Client
export { NodeClient } from './client/NodeClient';
export { DuckPoolsClient } from './client/DuckPoolsClient';

// Transaction
export { TransactionBuilder } from './transaction/TransactionBuilder';

// Bet
export { BetManager } from './bet/BetManager';

// Crypto
export {
  blake2b256,
  sha256,
  generateSecret,
  generateCommit,
  verifyCommit,
  computeRng,
  formatSecret,
  formatHash,
} from './crypto';

// Serialization
export {
  serializeInt,
  serializeLong,
  serializeCollByte,
  serializeSigmaProp,
  serializeSValue,
  serializeSValues,
  deserializeInt,
  deserializeLong,
  deserializeCollByte,
  deserializeSValue,
  formatErg,
  parseErg,
  formatTokenAmount,
} from './serialization';

// Version
export const SDK_VERSION = '0.1.0';
export const SDK_NAME = 'DuckPools SDK';
export const PROTOCOL_VERSION = '1.0.0';
