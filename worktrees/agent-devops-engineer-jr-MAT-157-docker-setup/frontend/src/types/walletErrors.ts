/**
 * Wallet error types
 */

export interface WalletState {
  isConnected: boolean;
  isConnecting: boolean;
  isLocked: boolean;
  walletAddress?: string;
  balance?: number;
  network?: 'testnet' | 'mainnet';
  tokens?: import('./eip12').Asset[];
  error?: WalletError;
}

export interface WalletError {
  code: WalletErrorCode;
  message: string;
  suggestions: string[];
}

export type WalletErrorCode =
  | 'wallet_not_found'
  | 'wallet_not_responsive'
  | 'preflight_timeout'
  | 'timeout_error'
  | 'user_rejected'
  | 'network_mismatch'
  | 'wallet_error'
  | 'signing_error'
  | 'submission_error'
  | 'invalid_transaction';

export function createWalletError(
  code: WalletErrorCode,
  message: string,
  suggestions: string[] = [],
): WalletError {
  return { code, message, suggestions };
}
