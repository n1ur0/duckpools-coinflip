/**
 * DEPRECATED: This file has been moved to ../wallet/useErgoWallet.ts
 *
 * The wallet system was refactored to support multiple wallets (Nautilus,
 * SAFEW, Minotaur). The new implementation accepts a walletKey parameter.
 *
 * Import from '../wallet/useErgoWallet' or use the WalletContext instead.
 *
 * @see src/wallet/adapters.ts - wallet definitions and detection
 * @see src/wallet/useWalletManager.ts - wallet selection management
 * @see src/wallet/useErgoWallet.ts - wallet connection hook (multi-wallet)
 * @see src/contexts/WalletContext.tsx - React context (use useWallet())
 */

// Re-export for backward compatibility
export { useErgoWallet } from '../wallet/useErgoWallet';
