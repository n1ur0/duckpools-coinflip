import { vi } from 'vitest';
import type { ReactNode } from 'react';
import { WalletProvider, useWalletSafe } from '../../contexts/WalletContext';

// ─── Factory for creating mock wallet context values ────────────────

export interface MockWalletOverrides {
  isConnected?: boolean;
  isConnecting?: boolean;
  isLocked?: boolean;
  walletAddress?: string;
  balance?: number;
  network?: 'testnet' | 'mainnet';
  tokens?: Array<{ tokenId: string; amount: number; name: string; decimals: number }>;
  error?: { message: string; suggestions: string[] };
  activeWalletKey?: string | null;
  activeWalletInfo?: any;
  availableWallets?: string[];
  knownWallets?: Array<{ key: string; name: string; icon: string; color: string; mobileScheme?: string }>;
  isDetecting?: boolean;
  connect?: () => Promise<void>;
  disconnect?: () => Promise<void>;
  clearError?: () => void;
  refreshBalance?: () => Promise<void>;
  selectWallet?: (key: string) => void;
  refreshAvailable?: () => Promise<string[]>;
  signTransaction?: (tx: any) => Promise<any>;
  submitTransaction?: (tx: any) => Promise<string | null>;
  getUtxos?: () => Promise<any[]>;
  getCurrentHeight?: () => Promise<number>;
  getChangeAddress?: () => Promise<string | null>;
}

function createMockWalletContext(overrides: MockWalletOverrides = {}) {
  return {
    isConnected: overrides.isConnected ?? false,
    isConnecting: overrides.isConnecting ?? false,
    isLocked: overrides.isLocked ?? false,
    walletAddress: overrides.walletAddress,
    balance: overrides.balance,
    network: overrides.network ?? 'testnet',
    tokens: overrides.tokens,
    error: overrides.error,
    activeWalletKey: overrides.activeWalletKey ?? null,
    activeWalletInfo: overrides.activeWalletInfo,
    availableWallets: overrides.availableWallets ?? [],
    knownWallets: overrides.knownWallets ?? [],
    isDetecting: overrides.isDetecting ?? false,
    connect: overrides.connect ?? vi.fn().mockResolvedValue(undefined),
    disconnect: overrides.disconnect ?? vi.fn().mockResolvedValue(undefined),
    clearError: overrides.clearError ?? vi.fn(),
    refreshBalance: overrides.refreshBalance ?? vi.fn().mockResolvedValue(undefined),
    selectWallet: overrides.selectWallet ?? vi.fn(),
    deselectWallet: vi.fn(),
    refreshAvailable: overrides.refreshAvailable ?? vi.fn().mockResolvedValue([]),
    signTransaction: overrides.signTransaction ?? vi.fn(),
    submitTransaction: overrides.submitTransaction ?? vi.fn(),
    getUtxos: overrides.getUtxos ?? vi.fn().mockResolvedValue([]),
    getCurrentHeight: overrides.getCurrentHeight ?? vi.fn().mockResolvedValue(500000),
    getChangeAddress: overrides.getChangeAddress ?? vi.fn().mockResolvedValue(null),
  };
}

// ─── Mock the wallet modules ──────────────────────────────────────────

const mockWalletContextRef = { current: createMockWalletContext() };

vi.mock('../../wallet/useWalletManager', () => ({
  useWalletManager: () => ({
    selectedWallet: mockWalletContextRef.current.activeWalletKey,
    selectedWalletInfo: mockWalletContextRef.current.activeWalletInfo,
    availableWallets: mockWalletContextRef.current.availableWallets,
    knownWallets: mockWalletContextRef.current.knownWallets,
    isDetecting: mockWalletContextRef.current.isDetecting,
    selectWallet: mockWalletContextRef.current.selectWallet,
    deselectWallet: mockWalletContextRef.current.deselectWallet,
    refreshAvailable: mockWalletContextRef.current.refreshAvailable,
  }),
}));

vi.mock('../../wallet/useErgoWallet', () => ({
  useErgoWallet: () => mockWalletContextRef.current,
}));

// ─── Re-export WalletProvider (uses mocked hooks internally) ────────

export { WalletProvider };

// ─── Helper to set mock state before rendering ───────────────────────

export function setMockWalletState(overrides: MockWalletOverrides) {
  mockWalletContextRef.current = createMockWalletContext(overrides);
}

// ─── Connected wallet defaults for convenience ──────────────────────

export const CONNECTED_WALLET: MockWalletOverrides = {
  isConnected: true,
  walletAddress: '3Wz8WpDLuSGoA7o3d1yGKbLCqkLkJFRXwKfSY3MGpGBPxwA4NMa',
  balance: 5_000_000_000,
  network: 'testnet',
  activeWalletKey: 'nautilus',
  activeWalletInfo: {
    key: 'nautilus',
    name: 'Nautilus',
    icon: '🦑',
    color: '#6c5ce7',
  },
  availableWallets: ['nautilus'],
  knownWallets: [
    { key: 'nautilus', name: 'Nautilus', icon: '🦑', color: '#6c5ce7' },
    { key: 'ergopay', name: 'ErgoPay', icon: '📱', color: '#00b894', mobileScheme: 'ergopay:' },
  ],
};
