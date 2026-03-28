/**
 * Tests for useWalletSessionPersistence hook
 */

import { renderHook, act } from '@testing-library/react';
import { useWalletSessionPersistence } from '../useWalletSessionPersistence';

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

// Mock console methods
const mockConsole = {
  log: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
};

beforeEach(() => {
  mockLocalStorage.clear();
  jest.clearAllMocks();
  mockLocalStorage.store = {};
});

describe('useWalletSessionPersistence', () => {
  it('should save and restore a wallet session', () => {
    const { result } = renderHook(() => useWalletSessionPersistence());
    
    const walletKey = 'nautilus';
    const sessionData = {
      isConnected: true,
      walletAddress: 'test-address',
      balance: 1000000,
      network: 'testnet' as const,
      tokens: [],
    };

    // Save session
    act(() => {
      result.current.saveSession(walletKey, sessionData);
    });

    // Verify localStorage was called
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      expect.stringContaining('duckpools-wallet-session'),
      expect.any(String)
    );

    // Clear hook to test restoration
    const { result: newResult } = renderHook(() => useWalletSessionPersistence());
    
    // Restore session
    let restoredSession;
    act(() => {
      restoredSession = newResult.current.restoreSession(walletKey);
    });

    // Verify restored session
    expect(restoredSession).toMatchObject(sessionData);
    expect(restoredSession?.walletKey).toBe(walletKey);
    expect(restoredSession?.timestamp).toBeDefined();
    expect(restoredSession?.expiresAt).toBeDefined();
  });

  it('should return null for non-existent session', () => {
    const { result } = renderHook(() => useWalletSessionPersistence());
    
    const nonExistentKey = 'non-existent-wallet';
    let restoredSession;
    
    act(() => {
      restoredSession = result.current.restoreSession(nonExistentKey);
    });

    expect(restoredSession).toBeNull();
  });

  it('should clear a session', () => {
    const { result } = renderHook(() => useWalletSessionPersistence());
    
    const walletKey = 'nautilus';
    const sessionData = {
      isConnected: true,
      walletAddress: 'test-address',
      balance: 1000000,
      network: 'testnet' as const,
      tokens: [],
    };

    // Save session
    act(() => {
      result.current.saveSession(walletKey, sessionData);
    });

    // Verify it exists
    let hasSessionBeforeClear;
    act(() => {
      hasSessionBeforeClear = result.current.hasSession(walletKey);
    });
    expect(hasSessionBeforeClear).toBe(true);

    // Clear session
    act(() => {
      result.current.clearSession(walletKey);
    });

    // Verify it's cleared
    let hasSessionAfterClear;
    act(() => {
      hasSessionAfterClear = result.current.hasSession(walletKey);
    });
    expect(hasSessionAfterClear).toBe(false);
  });

  it('should handle expired sessions', () => {
    const { result } = renderHook(() => useWalletSessionPersistence());
    
    const walletKey = 'nautilus';
    const sessionData = {
      isConnected: true,
      walletAddress: 'test-address',
      balance: 1000000,
      network: 'testnet' as const,
      tokens: [],
    };

    // Save session
    act(() => {
      result.current.saveSession(walletKey, sessionData);
    });

    // Manually set expiration to the past
    const sessionKey = 'duckpools-wallet-session-list';
    const sessionsJson = mockLocalStorage.store[sessionKey];
    const sessions = JSON.parse(sessionsJson);
    sessions[0].expiresAt = Date.now() - 1000; // Expired 1 second ago
    mockLocalStorage.store[sessionKey] = JSON.stringify(sessions);

    // Try to restore - should return null for expired session
    let restoredSession;
    act(() => {
      restoredSession = result.current.restoreSession(walletKey);
    });

    expect(restoredSession).toBeNull();
  });

  it('should handle localStorage errors gracefully', () => {
    // Make localStorage throw errors
    mockLocalStorage.getItem.mockImplementationOnce(() => {
      throw new Error('localStorage error');
    });

    const { result } = renderHook(() => useWalletSessionPersistence());
    
    const walletKey = 'nautilus';
    let restoredSession;
    
    act(() => {
      restoredSession = result.current.restoreSession(walletKey);
    });

    // Should handle error gracefully and return null
    expect(restoredSession).toBeNull();
  });
});