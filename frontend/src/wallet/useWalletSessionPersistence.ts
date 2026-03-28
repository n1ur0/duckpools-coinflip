/**
 * useWalletSessionPersistence Hook - Enhanced wallet session persistence
 *
 * Provides robust session persistence for EIP-12 wallet connections.
 * This hook saves connection state, addresses, and tokens to localStorage
 * and restores them on page reload, providing a seamless user experience.
 *
 * Features:
 * - Automatic session save on successful connection
 * - Session restore on component mount
 * - Session expiration handling
 * - Graceful degradation when localStorage is unavailable
 */

import { useEffect, useRef, useCallback } from 'react';
import type {
  WalletState,
  EIP12ContextAPI,
  Asset,
} from '../types';

interface PersistedWalletSession {
  isConnected: boolean;
  walletAddress?: string;
  balance?: number;
  network?: 'testnet' | 'mainnet';
  tokens?: Asset[];
  walletKey: string;
  timestamp: number;
  // Session expires after 24 hours
  expiresAt: number;
}

const SESSION_KEY = 'duckpools-wallet-session';
const SESSION_DURATION_MS = 24 * 60 * 60 * 1000; // 24 hours

const log = import.meta.env.DEV ? console : { log: () => {}, warn: () => {}, error: () => {} };

/**
 * Safely access localStorage with error handling
 */
function safeLocalStorageGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch (e) {
    log.warn('localStorage unavailable:', e);
    return null;
  }
}

function safeLocalStorageSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch (e) {
    log.warn('localStorage unavailable:', e);
  }
}

function safeLocalStorageRemove(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch (e) {
    log.warn('localStorage unavailable:', e);
  }
}

/**
 * Check if a session has expired
 */
function isSessionExpired(session: PersistedWalletSession): boolean {
  return Date.now() > session.expiresAt;
}

/**
 * Clean up expired sessions
 */
function cleanupExpiredSessions(): void {
  try {
    const sessionsJson = safeLocalStorageGet(`${SESSION_KEY}-list`);
    if (!sessionsJson) return;

    const sessions: PersistedWalletSession[] = JSON.parse(sessionsJson);
    const validSessions = sessions.filter(s => !isSessionExpired(s));
    
    safeLocalStorageSet(`${SESSION_KEY}-list`, JSON.stringify(validSessions));
  } catch (e) {
    log.warn('Failed to cleanup expired sessions:', e);
  }
}

/**
 * Get the current session for a wallet key
 */
function getSessionForWallet(walletKey: string): PersistedWalletSession | null {
  try {
    const sessionsJson = safeLocalStorageGet(`${SESSION_KEY}-list`);
    if (!sessionsJson) return null;

    const sessions: PersistedWalletSession[] = JSON.parse(sessionsJson);
    const session = sessions.find(s => s.walletKey === walletKey);
    
    if (!session) return null;
    if (isSessionExpired(session)) {
      cleanupExpiredSessions();
      return null;
    }
    
    return session;
  } catch (e) {
    log.warn('Failed to get session:', e);
    return null;
  }
}

/**
 * Save session data for a wallet
 */
function saveSessionForWallet(
  walletKey: string,
  sessionData: Omit<PersistedWalletSession, 'walletKey' | 'timestamp' | 'expiresAt'>
): void {
  try {
    const sessionsJson = safeLocalStorageGet(`${SESSION_KEY}-list`);
    let sessions: PersistedWalletSession[] = [];
    
    if (sessionsJson) {
      sessions = JSON.parse(sessionsJson);
    }
    
    // Remove any existing session for this wallet
    sessions = sessions.filter(s => s.walletKey !== walletKey);
    
    // Add new session
    const newSession: PersistedWalletSession = {
      ...sessionData,
      walletKey,
      timestamp: Date.now(),
      expiresAt: Date.now() + SESSION_DURATION_MS,
    };
    
    sessions.push(newSession);
    safeLocalStorageSet(`${SESSION_KEY}-list`, JSON.stringify(sessions));
  } catch (e) {
    log.warn('Failed to save session:', e);
  }
}

/**
 * Remove session for a wallet
 */
function removeSessionForWallet(walletKey: string): void {
  try {
    const sessionsJson = safeLocalStorageGet(`${SESSION_KEY}-list`);
    if (!sessionsJson) return;

    const sessions: PersistedWalletSession[] = JSON.parse(sessionsJson);
    const filtered = sessions.filter(s => s.walletKey !== walletKey);
    
    safeLocalStorageSet(`${SESSION_KEY}-list`, JSON.stringify(filtered));
  } catch (e) {
    log.warn('Failed to remove session:', e);
  }
}

export interface UseWalletSessionPersistenceReturn {
  /**
   * Persist the current wallet session state
   */
  saveSession: (walletKey: string, state: WalletState, tokens?: Asset[]) => void;
  
  /**
   * Restore a previously persisted session
   */
  restoreSession: (walletKey: string) => PersistedWalletSession | null;
  
  /**
   * Remove the persisted session for a wallet
   */
  clearSession: (walletKey: string) => void;
  
  /**
   * Check if a persisted session exists for a wallet
   */
  hasSession: (walletKey: string) => boolean;
}

export function useWalletSessionPersistence(): UseWalletSessionPersistenceReturn {
  const restoringRef = useRef(false);

  // Clean up expired sessions on mount
  useEffect(() => {
    cleanupExpiredSessions();
  }, []);

  const saveSession = useCallback((walletKey: string, state: WalletState, tokens?: Asset[]) => {
    if (!state.isConnected) {
      // Don't save if not connected
      return;
    }

    log.log('[SessionPersistence] Saving session for wallet:', walletKey);
    
    const sessionData = {
      isConnected: state.isConnected,
      walletAddress: state.walletAddress,
      balance: state.balance,
      network: state.network,
      tokens,
    };

    saveSessionForWallet(walletKey, sessionData);
  }, []);

  const restoreSession = useCallback((walletKey: string): PersistedWalletSession | null => {
    if (restoringRef.current) {
      log.warn('[SessionPersistence] Already restoring session, skipping...');
      return null;
    }

    restoringRef.current = true;
    
    try {
      log.log('[SessionPersistence] Attempting to restore session for wallet:', walletKey);
      
      const session = getSessionForWallet(walletKey);
      if (!session) {
        log.log('[SessionPersistence] No session found for wallet:', walletKey);
        return null;
      }

      if (isSessionExpired(session)) {
        log.log('[SessionPersistence] Session expired for wallet:', walletKey);
        removeSessionForWallet(walletKey);
        return null;
      }

      log.log('[SessionPersistence] Session restored successfully for wallet:', walletKey);
      return session;
    } catch (e) {
      log.error('[SessionPersistence] Failed to restore session:', e);
      return null;
    } finally {
      restoringRef.current = false;
    }
  }, []);

  const clearSession = useCallback((walletKey: string) => {
    log.log('[SessionPersistence] Clearing session for wallet:', walletKey);
    removeSessionForWallet(walletKey);
  }, []);

  const hasSession = useCallback((walletKey: string): boolean => {
    const session = getSessionForWallet(walletKey);
    return session !== null && !isSessionExpired(session);
  }, []);

  return {
    saveSession,
    restoreSession,
    clearSession,
    hasSession,
  };
}