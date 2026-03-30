import { createContext, useContext, ReactNode, useEffect, useMemo } from 'react';
import type { WalletError, ErgoBox, UnsignedTransaction, SignedTransaction } from '../types';
import type { WalletInfo } from '../wallet/adapters';
import { useWalletManager } from '../wallet/useWalletManager';
import { useErgoWallet } from '../wallet/useErgoWallet';

interface WalletContextValue {
  // Connection state
  isConnected: boolean;
  isConnecting: boolean;
  isLocked: boolean;
  walletAddress?: string;
  balance?: number;
  network?: 'testnet' | 'mainnet';
  tokens?: import('../types').Asset[];
  error?: WalletError;

  // Wallet management
  activeWalletKey: string | null;
  activeWalletInfo: WalletInfo | undefined;
  availableWallets: string[];
  knownWallets: WalletInfo[];
  isDetecting: boolean;

  // Actions
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  clearError: () => void;
  refreshBalance: () => Promise<void>;
  selectWallet: (key: string) => void;
  deselectWallet: () => void;
  refreshAvailable: () => Promise<string[]>;

  // EIP-12 operations
  getUtxos: () => Promise<ErgoBox[]>;
  getCurrentHeight: () => Promise<number>;
  getChangeAddress: () => Promise<string | null>;
  signTransaction: (tx: UnsignedTransaction) => Promise<SignedTransaction | null>;
  submitTransaction: (tx: SignedTransaction) => Promise<string | null>;
}

const WalletContext = createContext<WalletContextValue | null>(null);

export function WalletProvider({ children }: { children: ReactNode }) {
  const manager = useWalletManager();
  const wallet = useErgoWallet({ walletKey: manager.selectedWallet });

  // Poll balance every 10s when connected
  useEffect(() => {
    if (!wallet.isConnected) return;
    const id = setInterval(() => wallet.refreshBalance(), 10_000);
    return () => clearInterval(id);
  }, [wallet.isConnected, wallet.refreshBalance]);

  const value = useMemo<WalletContextValue>(() => ({
    // Connection state
    isConnected: wallet.isConnected,
    isConnecting: wallet.isConnecting,
    isLocked: wallet.isLocked,
    walletAddress: wallet.walletAddress,
    balance: wallet.balance,
    network: wallet.network,
    tokens: wallet.tokens,
    error: wallet.error,

    // Wallet management
    activeWalletKey: wallet.activeWalletKey,
    activeWalletInfo: manager.selectedWalletInfo,
    availableWallets: manager.availableWallets,
    knownWallets: manager.knownWallets,
    isDetecting: manager.isDetecting,

    // Actions
    connect: wallet.connect,
    disconnect: wallet.disconnect,
    clearError: wallet.clearError,
    refreshBalance: wallet.refreshBalance,
    selectWallet: manager.selectWallet,
    deselectWallet: manager.deselectWallet,
    refreshAvailable: manager.refreshAvailable,

    // EIP-12 operations
    getUtxos: wallet.getUtxos,
    getCurrentHeight: wallet.getCurrentHeight,
    getChangeAddress: wallet.getChangeAddress,
    signTransaction: wallet.signTransaction,
    submitTransaction: wallet.submitTransaction,
  }), [
    wallet, manager,
  ]);

  return (
    <WalletContext.Provider value={value}>
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet(): WalletContextValue {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error('useWallet must be used within WalletProvider');
  return ctx;
}

export function useWalletSafe(): WalletContextValue | null {
  return useContext(WalletContext);
}
