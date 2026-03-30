/**
 * useWalletManager Hook - Multi-wallet detection, selection, and switching
 *
 * Manages the lifecycle of which wallet adapter is active.
 * Wallets are all EIP-12 compatible, so the underlying connection API
 * is identical -- this hook just manages which one is selected.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { KNOWN_WALLETS, detectAvailableWallets, getWalletInfo, type WalletInfo } from './adapters';

const log = import.meta.env.DEV ? console : { log: () => {}, warn: () => {}, error: () => {} };

export interface UseWalletManagerReturn {
  /** List of wallets whose extensions are installed */
  availableWallets: string[];
  /** Currently selected wallet key (null = no selection yet) */
  selectedWallet: string | null;
  /** Info for the selected wallet */
  selectedWalletInfo: WalletInfo | undefined;
  /** All known wallet definitions */
  knownWallets: WalletInfo[];
  /** Whether we're still detecting wallets */
  isDetecting: boolean;
  /** Select a wallet (triggers connection flow in useErgoWallet) */
  selectWallet: (key: string) => void;
  /** Deselect the current wallet */
  deselectWallet: () => void;
  /** Manually refresh detected wallets; returns the list of detected wallet keys */
  refreshAvailable: () => Promise<string[]>;
  /** Persisted wallet preference key for localStorage */
  STORAGE_KEY: string;
}

const STORAGE_KEY = 'duckpools-preferred-wallet';

export function useWalletManager(): UseWalletManagerReturn {
  const [availableWallets, setAvailableWallets] = useState<string[]>([]);
  const [selectedWallet, setSelectedWallet] = useState<string | null>(null);
  const [isDetecting, setIsDetecting] = useState(true);
  const mountedRef = useRef(true);

  // ─── Detect installed wallets ─────────────────────────────────

  const refreshAvailable = useCallback(async () => {
    const detected = await detectAvailableWallets();
    if (!mountedRef.current) return [];
    setAvailableWallets(detected);
    setIsDetecting(false);
    log.log('[WalletManager] Detected wallets:', detected);
    return detected;
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    const init = async () => {
      // Detect wallets
      await refreshAvailable();

      if (!mountedRef.current) return;

      // Restore persisted wallet preference
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved && KNOWN_WALLETS.some(w => w.key === saved)) {
          setSelectedWallet(saved);
        }
      } catch {
        // localStorage unavailable
      }
    };

    init();

    return () => { mountedRef.current = false; };
  }, [refreshAvailable]);

  // ─── Select wallet ────────────────────────────────────────────

  const selectWallet = useCallback((key: string) => {
    if (!KNOWN_WALLETS.some(w => w.key === key)) {
      log.warn('[WalletManager] Unknown wallet:', key);
      return;
    }
    setSelectedWallet(key);
    try {
      localStorage.setItem(STORAGE_KEY, key);
    } catch {
      // localStorage unavailable
    }
    log.log('[WalletManager] Selected wallet:', key);
  }, []);

  // ─── Deselect wallet ──────────────────────────────────────────

  const deselectWallet = useCallback(() => {
    setSelectedWallet(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  return {
    availableWallets,
    selectedWallet,
    selectedWalletInfo: selectedWallet ? getWalletInfo(selectedWallet) : undefined,
    knownWallets: KNOWN_WALLETS,
    isDetecting,
    selectWallet,
    deselectWallet,
    refreshAvailable,
    STORAGE_KEY,
  };
}
