/**
 * Integration tests for useErgoWallet with session persistence
 */

import { renderHook, act } from '@testing-library/react';
import { useErgoWallet } from '../useErgoWallet';

// Mock dependencies
jest.mock('../adapters', () => ({
  getWalletConnection: jest.fn(),
  waitForConnector: jest.fn(() => Promise.resolve(true)),
  getWalletInfo: jest.fn(() => ({
    key: 'nautilus',
    name: 'Nautilus',
    shortName: 'Naut',
    icon: '🐚',
    color: '#5B6AE0',
    installUrl: 'https://example.com',
    mobileScheme: 'https://nautiluswallet.io',
  })),
}));

jest.mock('../utils/network', () => ({
  getExpectedNetworkType: jest.fn(() => 'testnet'),
  getNetworkFromAddress: jest.fn(() => 'testnet'),
}));

// Mock window.ergoConnector
const mockNautilusConnector = {
  isConnected: jest.fn(() => Promise.resolve(true)),
  getContext: jest.fn(() => Promise.resolve({
    get_change_address: jest.fn(() => Promise.resolve('test-address')),
    get_balance: jest.fn(() => Promise.resolve('1000000')),
    get_utxos: jest.fn(() => Promise.resolve([
      {
        boxId: 'test-box-id',
        transactionId: 'test-tx-id',
        value: '1000000',
        index: 0,
        creationHeight: 100,
        ergoTree: 'test-tree',
        assets: [],
        additionalRegisters: {},
      },
    ])),
  })),
};

Object.defineProperty(window, 'ergoConnector', {
  value: {
    nautilus: mockNautilusConnector,
  },
  writable: true,
});

// Mock localStorage
const mockLocalStorage = {
  store: {} as Record<string, string>,
  getItem: jest.fn((key: string) => mockLocalStorage.store[key] || null),
  setItem: jest.fn((key: string, value: string) => {
    mockLocalStorage.store[key] = value;
  }),
  removeItem: jest.fn((key: string) => {
    delete mockLocalStorage.store[key];
  }),
  clear: jest.fn(() => {
    mockLocalStorage.store = {};
  }),
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

beforeEach(() => {
  jest.clearAllMocks();
  mockLocalStorage.clear();
  mockLocalStorage.store = {};
});

describe('useErgoWallet with session persistence', () => {
  it('should restore persisted session on mount', async () => {
    // Set up persisted session
    mockLocalStorage.store['duckpools-wallet-session-list'] = JSON.stringify([
      {
        isConnected: true,
        walletAddress: 'persisted-address',
        balance: 2000000,
        network: 'testnet',
        tokens: [],
        walletKey: 'nautilus',
        timestamp: Date.now(),
        expiresAt: Date.now() + 24 * 60 * 60 * 1000,
      },
    ]);

    const { result } = renderHook(() => useErgoWallet({ walletKey: 'nautilus' }));

    // Wait for async operations to complete
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    // Verify the hook tried to restore the session
    expect(mockLocalStorage.getItem).toHaveBeenCalledWith(
      'duckpools-wallet-session-list'
    );
  });

  it('should save session on successful connection', async () => {
    const { result } = renderHook(() => useErgoWallet({ walletKey: 'nautilus' }));

    // Connect wallet
    await act(async () => {
      await result.current.connect();
    });

    // Verify session was saved
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      expect.stringContaining('duckpools-wallet-session'),
      expect.any(String)
    );
  });

  it('should clear session on disconnect', async () => {
    const { result } = renderHook(() => useErgoWallet({ walletKey: 'nautilus' }));

    // First connect
    await act(async () => {
      await result.current.connect();
    });

    // Then disconnect
    await act(async () => {
      await result.current.disconnect();
    });

    // Verify session was cleared
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith(
      'duckpools-wallet-session-list'
    );
  });

  it('should handle session restoration failure gracefully', async () => {
    // Make localStorage throw error
    mockLocalStorage.getItem.mockImplementationOnce(() => {
      throw new Error('localStorage error');
    });

    const { result } = renderHook(() => useErgoWallet({ walletKey: 'nautilus' }));

    // Should not throw error
    expect(() => {
      // Wait for async operations
      act(() => {
        // Just trigger the hook
      });
    }).not.toThrow();
  });

  it('should not restore expired session', async () => {
    // Set up expired session
    mockLocalStorage.store['duckpools-wallet-session-list'] = JSON.stringify([
      {
        isConnected: true,
        walletAddress: 'expired-address',
        balance: 3000000,
        network: 'testnet',
        tokens: [],
        walletKey: 'nautilus',
        timestamp: Date.now(),
        expiresAt: Date.now() - 1000, // Expired 1 second ago
      },
    ]);

    const { result } = renderHook(() => useErgoWallet({ walletKey: 'nautilus' }));

    // Wait for async operations
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    // Should try to establish a fresh connection since session is expired
    expect(mockNautilusConnector.isConnected).toHaveBeenCalled();
  });
});