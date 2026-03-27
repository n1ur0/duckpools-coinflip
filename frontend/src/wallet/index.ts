/**
 * Multi-wallet module exports
 *
 * Wallet adapter system for supporting multiple EIP-12 compatible
 * Ergo wallets (Nautilus, SAFEW, Minotaur) and mobile deep-linking.
 */

export * from './adapters';
export { useWalletManager } from './useWalletManager';
export { useErgoWallet } from './useErgoWallet';
