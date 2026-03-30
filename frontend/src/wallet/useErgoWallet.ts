/**
 * useErgoWallet Hook - EIP-12 Wallet Connection (Multi-wallet)
 *
 * Implements the official EIP-12 dApp Connector standard.
 * All supported wallets (Nautilus, SAFEW, Minotaur) use the same API:
 *   connect(), disconnect(), isConnected(), getContext()
 *   get_balance(), get_utxos(), get_change_address(),
 *   sign_tx(), submit_tx(), get_current_height()
 *
 * This hook is wallet-agnostic and accepts a walletKey to determine
 * which window.ergoConnector entry to use.
 *
 * @see https://github.com/ergoplatform/eips/blob/master/eip-0012.md
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  WalletState,
  WalletError,
  ErgoBox,
  EIP12ContextAPI,
  UnsignedTransaction,
  SignedTransaction,
} from '../types';
import type { Asset } from '../types';
import { createWalletError } from '../types';
import { getExpectedNetworkType, getNetworkFromAddress } from '../utils/network';
import { getWalletConnection, waitForConnector, waitForWalletKey, getWalletInfo } from './adapters';
import { useWalletSessionPersistence } from './useWalletSessionPersistence';

// Use a simple flag for logging - in production this would be false
const isDev = import.meta.env.DEV;
const log = isDev ? console : { log: () => {}, warn: () => {}, error: () => {} };

// ─── Helpers ────────────────────────────────────────────────────

function parseNanoErg(raw: string): number {
  const n = Number(raw);
  return Number.isFinite(n) ? n : Number.MAX_SAFE_INTEGER;
}

function extractTokens(utxos: ErgoBox[]): Asset[] {
  const map = new Map<string, Asset>();
  for (const box of utxos) {
    for (const asset of box.assets ?? []) {
      const existing = map.get(asset.tokenId);
      if (existing) {
        existing.amount = (BigInt(existing.amount) + BigInt(asset.amount)).toString();
      } else {
        map.set(asset.tokenId, { ...asset });
      }
    }
  }
  return Array.from(map.values());
}

// ─── Hook ───────────────────────────────────────────────────────

export interface UseErgoWalletReturn {
  isConnected: boolean;
  isConnecting: boolean;
  isLocked: boolean;
  walletAddress?: string;
  balance?: number;
  network?: 'testnet' | 'mainnet';
  tokens?: Asset[];
  error?: WalletError;
  ergo: EIP12ContextAPI | null;
  /** The wallet key currently in use (e.g. 'nautilus', 'safew', 'minotaur') */
  activeWalletKey: string | null;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  clearError: () => void;
  refreshBalance: () => Promise<void>;
  getUtxos: () => Promise<ErgoBox[]>;
  getCurrentHeight: () => Promise<number>;
  getChangeAddress: () => Promise<string | null>;
  signTransaction: (tx: UnsignedTransaction) => Promise<SignedTransaction | null>;
  submitTransaction: (tx: SignedTransaction) => Promise<string | null>;
}

interface UseErgoWalletOptions {
  /** The wallet key to use (from useWalletManager.selectedWallet) */
  walletKey: string | null;
}

export function useErgoWallet(options: UseErgoWalletOptions): UseErgoWalletReturn {
  const { walletKey } = options;

  const [state, setState] = useState<WalletState>({
    isConnected: false,
    isConnecting: false,
    isLocked: false,
  });

  const [ergo, setErgo] = useState<EIP12ContextAPI | null>(null);
  const connectGuard = useRef(false);
  const connectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastError = useRef<string | undefined>(undefined);
  const CONNECT_TIMEOUT = 30_000;

  const walletInfo = walletKey ? getWalletInfo(walletKey) : undefined;
  const walletDisplayName = walletInfo?.name ?? walletKey ?? 'wallet';
  
  // Session persistence integration
  const { saveSession, restoreSession, clearSession, hasSession } = useWalletSessionPersistence();

  // ─── Disconnect when wallet key changes ──────────────────────

  useEffect(() => {
    // If the user switches wallets, disconnect the old one first
    setErgo(null);
    setState({
      isConnected: false,
      isConnecting: false,
      isLocked: false,
    });
    lastError.current = undefined;
    if (connectTimer.current) {
      clearTimeout(connectTimer.current);
      connectTimer.current = null;
    }
    connectGuard.current = false;
  }, [walletKey]);

  // ─── Auto-reconnect when wallet is locked ─────────────────────

  useEffect(() => {
    if (!walletKey || !state.isLocked || state.isConnected) return;

    const id = setInterval(async () => {
      const conn = getWalletConnection(walletKey);
      if (!conn) return;
      try {
        const connected = await conn.isConnected();
        if (connected) {
          const ctx = await conn.getContext();
          if (!ctx) return;
          setErgo(ctx);
        const address = await ctx.get_change_address();
        const bal = parseNanoErg(await ctx.get_balance());
        const utxos = await ctx.get_utxos();
        const tokens = extractTokens(utxos);
          setState(prev => ({
            ...prev,
            isConnected: true,
            isLocked: false,
            walletAddress: address,
            balance: isNaN(bal) ? undefined : bal,
            tokens,
            network: getNetworkFromAddress(address),
          }));
        }
      } catch {
        // still locked
      }
    }, 2000);

    return () => clearInterval(id);
  }, [walletKey, state.isLocked, state.isConnected]);

  // ─── Restore session on mount / walletKey change ──────────────

  useEffect(() => {
    if (!walletKey) return;

    let cancelled = false;

    const restore = async () => {
      // ── ErgoPay session restore ──
      // ErgoPay doesn't use window.ergoConnector, so we handle it separately.
      // We restore from persisted session and refresh balance from the explorer API.
      if (walletKey === 'ergopay') {
        const persistedSession = hasSession(walletKey) ? restoreSession(walletKey) : null;
        if (persistedSession && persistedSession.walletAddress) {
          log.log('[Wallet] Restoring ErgoPay session:', { address: persistedSession.walletAddress });

          // Import ErgoPayAdapter and restore
          const { ErgoPayAdapter } = await import('./adapters/ergopay');
          const adapter = new ErgoPayAdapter();
          const connected = await adapter.connect(persistedSession.walletAddress);
          if (connected && !cancelled) {
            const ctx = await adapter.getContext();
            if (ctx) {
              setErgo(ctx);

              // Refresh balance from explorer API
              let bal = persistedSession.balance || 0;
              let tokens: Asset[] = persistedSession.tokens || [];
              try {
                const balResp = await fetch(`https://api.ergoplatform.com/api/v1/addresses/${persistedSession.walletAddress}/balance`);
                if (balResp.ok) {
                  const balData = await balResp.json();
                  bal = balData.confirmed ? Number(balData.confirmed.nanoErgs) : 0;
              tokens = (balData.confirmed?.tokens || []).map((t: any) => ({
                    tokenId: t.tokenId,
                    amount: t.amount,
                    name: t.name,
                    decimals: t.decimals,
                  }));
                }
              } catch { /* ignore */ }

              setState(prev => ({
                ...prev,
                isConnected: true,
                isLocked: false,
                walletAddress: persistedSession.walletAddress,
                balance: isNaN(bal) ? undefined : bal,
                network: persistedSession.network,
                tokens,
              }));
              saveSession(walletKey, {
                isConnected: true,
                isConnecting: false,
                isLocked: false,
                walletAddress: persistedSession.walletAddress,
                balance: isNaN(bal) ? undefined : bal,
                network: persistedSession.network,
                error: undefined,
              }, tokens);
            }
          } else {
            clearSession(walletKey);
          }
        }
        return;
      }

      // ── Standard EIP-12 extension wallets ──
      const available = await waitForConnector(3000);
      if (cancelled) return;
      const conn = getWalletConnection(walletKey);
      if (!available || !conn) return;

      try {
        // First try to restore from persisted session for immediate UI feedback
        const persistedSession = hasSession(walletKey) ? restoreSession(walletKey) : null;
        if (persistedSession) {
          log.log('[Wallet] Restored session from persistence:', { walletKey, address: persistedSession.walletAddress });
          setState(prev => ({
            ...prev,
            isConnected: true,
            isLocked: false,
            walletAddress: persistedSession.walletAddress,
            balance: persistedSession.balance,
            network: persistedSession.network,
            tokens: persistedSession.tokens,
          }));
        }

        // Then verify with actual wallet connection
        const connected = await conn.isConnected();
        if (cancelled || !connected) {
          // If wallet is not actually connected, clear the persisted session
          if (persistedSession) {
            clearSession(walletKey);
            setState(prev => ({
              ...prev,
              isConnected: false,
              isLocked: false,
              walletAddress: undefined,
              balance: undefined,
              network: undefined,
              tokens: undefined,
            }));
          }
          return;
        }

        const ctx = await conn.getContext();
        if (cancelled || !ctx) return;

        setErgo(ctx);
        const address = await ctx.get_change_address();
        const bal = parseNanoErg(await ctx.get_balance());
        const utxos = await ctx.get_utxos();
        const tokens = extractTokens(utxos);

        if (cancelled) return;
        setState(prev => ({
          ...prev,
          isConnected: true,
          isLocked: false,
          walletAddress: address,
          balance: isNaN(bal) ? undefined : bal,
          network: getNetworkFromAddress(address),
          tokens,
        }));

        // Save the fresh session data
        saveSession(walletKey, {
          isConnected: true,
          isConnecting: false,
          isLocked: false,
          walletAddress: address,
          balance: isNaN(bal) ? undefined : bal,
          network: getNetworkFromAddress(address),
          error: undefined,
        }, tokens);
      } catch (err: any) {
        // code -3 = not connected, expected
        if (err?.code !== -3) log.error('Failed to restore wallet:', err);
        // If there was an error during restoration, clear any persisted session
        clearSession(walletKey);
      }
    };

    restore();

    return () => {
      cancelled = true;
      if (connectTimer.current) { clearTimeout(connectTimer.current); connectTimer.current = null; }
    };
  }, [walletKey, hasSession, restoreSession, clearSession, saveSession]);

  // ─── connect ──────────────────────────────────────────────────

  const connect = useCallback(async () => {
    log.log(`[Wallet] Connect clicked (wallet: ${walletDisplayName})`);

    if (!walletKey) {
      setState(prev => ({
        ...prev,
        error: createWalletError('wallet_not_found', 'No wallet selected', ['Select a wallet first']),
      }));
      return;
    }

    if (connectGuard.current) {
      log.log('[Wallet] Already connecting, ignoring');
      return;
    }

    if (connectTimer.current) { clearTimeout(connectTimer.current); connectTimer.current = null; }

    // Wait for the extension to inject the specific wallet key into window.ergoConnector.
    // We poll for the specific wallet key (e.g. 'nautilus') rather than just the top-level
    // ergoConnector object, because the extension may inject the top-level object first
    // and populate wallet keys asynchronously.

    // ── ErgoPay special handling ──
    // ErgoPay is a URL-based protocol, not a browser extension.
    // It doesn't use window.ergoConnector. Instead, the user provides
    // their address, and we create a stub context for balance/UTXO queries.
    if (walletKey === 'ergopay') {
      // Set connecting state for UI feedback
      connectGuard.current = true;
      setState(prev => {
        const { error: _e, ...rest } = prev;
        return { ...rest, isConnecting: true };
      });

      const pendingAddress = (() => {
        try {
          return localStorage.getItem('duckpools:ergopay-pending-address');
        } catch {
          return null;
        }
      })();

      if (!pendingAddress) {
        setState(prev => ({
          ...prev,
          isConnecting: false,
          error: createWalletError('wallet_not_found', 'No Ergo address provided', ['Enter your Ergo address to connect via ErgoPay']),
        }));
        return;
      }

      // Clear the pending address
      try { localStorage.removeItem('duckpools:ergopay-pending-address'); } catch { /* ignore */ }

      // Import ErgoPayAdapter dynamically to avoid circular deps
      const { ErgoPayAdapter } = await import('./adapters/ergopay');
      const adapter = new ErgoPayAdapter();

      try {
        const connected = await adapter.connect(pendingAddress);
        if (!connected) {
          setState(prev => ({
            ...prev,
            isConnecting: false,
            error: createWalletError('wallet_error', 'Failed to connect via ErgoPay', ['Check your Ergo address and try again']),
          }));
          return;
        }

        const ctx = await adapter.getContext();
        if (!ctx) {
          setState(prev => ({
            ...prev,
            isConnecting: false,
            error: createWalletError('wallet_error', 'Failed to get ErgoPay context'),
          }));
          return;
        }

        setErgo(ctx);
        const address = await ctx.get_change_address();
        await ctx.get_current_height();

        // For ErgoPay, we need to fetch balance from the Ergo explorer API
        // since the stub context returns '0'
        let bal = 0;
        let tokens: Asset[] = [];
        try {
          const balResp = await fetch(`https://api.ergoplatform.com/api/v1/addresses/${address}/balance`);
          if (balResp.ok) {
            const balData = await balResp.json();
            bal = balData.confirmed ? Number(balData.confirmed.nanoErgs) : 0;
              tokens = (balData.confirmed?.tokens || []).map((t: any) => ({
              tokenId: t.tokenId,
              amount: t.amount,
              name: t.name,
              decimals: t.decimals,
            }));
          }
        } catch {
          // Balance fetch failed, use 0
        }

        const walletNetwork = getNetworkFromAddress(address);

        const finalState = {
          isConnected: true,
          isConnecting: false,
          isLocked: false,
          walletAddress: address,
          balance: isNaN(bal) ? undefined : bal,
          network: walletNetwork,
          tokens,
          error: undefined,
        };

        setState(prev => ({ ...prev, ...finalState }));
        saveSession(walletKey, finalState, tokens);
        log.log('[Wallet] ErgoPay connection complete:', { address, balance: bal, network: walletNetwork });
      } catch (error: any) {
        log.error('[Wallet] ErgoPay connection error:', error);
        setState(prev => ({
          ...prev,
          isConnecting: false,
          error: createWalletError('wallet_error', error?.message || 'Failed to connect via ErgoPay', ['Check your address and try again']),
        }));
      } finally {
        connectGuard.current = false;
      }
      return;
    }

    // ── Standard EIP-12 extension wallets ──
    const available = await waitForWalletKey(walletKey, 8000);
    const conn = getWalletConnection(walletKey);

    if (!available || !conn) {
      setState(prev => ({
        ...prev,
        error: createWalletError('wallet_not_found',
          `${walletDisplayName} wallet not installed or not enabled`,
          [
            `Install ${walletDisplayName} from the Chrome Web Store`,
            'Enable the extension in chrome://extensions',
            'Refresh this page after enabling',
            'Make sure the wallet extension is unlocked',
          ]),
      }));
      return;
    }

    log.log(`[Wallet] ${walletDisplayName} found, calling connect()...`);

    // Set guard and connecting state
    connectGuard.current = true;
    lastError.current = undefined;
    setState(prev => {
      const { error: _e, ...rest } = prev;
      return { ...rest, isConnecting: true };
    });

    try {
      // ── The one and only connect() call ──
      // EIP-12: conn.connect() triggers the wallet popup.
      // - If dApp is NOT authorized: shows popup, resolves true/false based on user choice.
      // - If dApp IS already authorized: resolves true immediately (no popup).
      //
      // We intentionally do NOT call isConnected() or any pre-flight checks before this.
      // Pre-flight isConnected() calls can:
      //   1. Timeout on slow/stalled extensions, aborting the connect flow entirely
      //   2. Race with the user's intent to connect (Nautilus throws code -3 when not connected)
      //   3. Add unnecessary latency before the popup appears
      //
      // Directly calling connect() is the standard EIP-12 flow and avoids all these issues.
      // If the extension is unresponsive, the 30s CONNECT_TIMEOUT handles it.
      //
      // @see https://github.com/ergoplatform/eips/blob/master/eip-0012.md

      const connectPromise = conn.connect();
      const timeoutPromise = new Promise<never>((_, reject) => {
        connectTimer.current = setTimeout(
          () => reject(new Error(`Connection timed out — ${walletDisplayName} did not respond within 30s`)),
          CONNECT_TIMEOUT,
        );
      });

      let connected: boolean;
      try {
        connected = await Promise.race([connectPromise, timeoutPromise]);
      } catch (timeoutErr) {
        connectTimer.current = null;
        lastError.current = 'timeout';
        setState(prev => ({
          ...prev,
          isConnecting: false,
          error: createWalletError('timeout_error',
            `Connection timed out — ${walletDisplayName} did not respond within 30 seconds`,
            [
              `Click the ${walletDisplayName} extension icon in your browser toolbar`,
              `Make sure ${walletDisplayName} is unlocked`,
              'Try refreshing the page and connecting again',
            ]),
        }));
        return;
      }

      if (connectTimer.current) { clearTimeout(connectTimer.current); connectTimer.current = null; }

      if (!connected) {
        setState(prev => ({
          ...prev,
          isConnecting: false,
          error: createWalletError('user_rejected',
            'Connection was declined or popup was closed',
            [`Click "Connect" in the ${walletDisplayName} popup`, `Make sure ${walletDisplayName} is unlocked`]),
        }));
        return;
      }

      log.log('[Wallet] Connection approved! Getting context...');

      // Get the EIP-12 context API
      const ctx = await conn.getContext();
      if (!ctx) {
        setState(prev => ({
          ...prev,
          isConnecting: false,
          error: createWalletError('wallet_error',
            'Failed to get wallet context after connection',
            ['Try disconnecting and reconnecting']),
        }));
        return;
      }

      setErgo(ctx);

      const address = await ctx.get_change_address();
      const bal = parseNanoErg(await ctx.get_balance());
      const utxos = await ctx.get_utxos();
      const tokens = extractTokens(utxos);

      const walletNetwork = getNetworkFromAddress(address);
      const expected = getExpectedNetworkType();

      if (walletNetwork && walletNetwork !== expected) {
        setState(prev => ({
          ...prev,
          isConnecting: false,
          error: createWalletError('network_mismatch',
            `Wallet is on ${walletNetwork}, dApp expects ${expected}`,
            [`Switch ${walletDisplayName} to ${expected}`]),
        }));
        await conn.disconnect();
        setErgo(null);
        return;
      }

      const finalState = {
        isConnected: true,
        isConnecting: false,
        isLocked: false,
        walletAddress: address,
        balance: isNaN(bal) ? undefined : bal,
        network: walletNetwork,
        tokens,
        error: undefined,
      };

      setState(prev => ({
        ...prev,
        ...finalState,
      }));

      // Save session on successful connection
      saveSession(walletKey, finalState, tokens);

      log.log('[Wallet] Connection complete:', { address, balance: bal, network: walletNetwork });
    } catch (error: any) {
      log.error('[Wallet] Connection error:', error);
      lastError.current = error?.message || 'unknown';
      setState(prev => ({
        ...prev,
        isConnecting: false,
        error: createWalletError('wallet_error',
          error?.message || 'Failed to connect wallet',
          [`Unlock ${walletDisplayName} and try again`]),
      }));
    } finally {
      connectGuard.current = false;
    }
  }, [walletKey, walletDisplayName, saveSession]);

  // ─── disconnect ───────────────────────────────────────────────

  const disconnect = useCallback(async () => {
    if (walletKey) {
      // ErgoPay doesn't use ergoConnector
      if (walletKey !== 'ergopay') {
        const conn = getWalletConnection(walletKey);
        if (conn) {
          try { await conn.disconnect(); } catch (e) { console.error('Disconnect error:', e); }
        }
      }
      // Clear the persisted session
      clearSession(walletKey);
    }
    setErgo(null);
    setState({ isConnected: false, isConnecting: false, isLocked: false });
  }, [walletKey, clearSession]);

  // ─── signTransaction ──────────────────────────────────────────

  const signTransaction = useCallback(async (unsignedTx: UnsignedTransaction): Promise<SignedTransaction | null> => {
    if (!ergo || !state.isConnected) {
      throw createWalletError('wallet_error', 'Wallet not connected', ['Connect your wallet first']);
    }
    try {
      const signed = await ergo.sign_tx(unsignedTx);
      log.log('Transaction signed:', signed.id);
      return signed;
    } catch (error: any) {
      if (error?.info === 'unreachable') {
        throw createWalletError('signing_error',
          'Wallet cannot find private key to sign inputs',
          ['Ensure UTXOs belong to the connected wallet', 'Try reconnecting']);
      }
      throw createWalletError('signing_error',
        error?.message || 'Failed to sign transaction',
        ['Check wallet connection and approve the signing request']);
    }
  }, [ergo, state.isConnected]);

  // ─── submitTransaction ────────────────────────────────────────

  const submitTransaction = useCallback(async (signedTx: SignedTransaction): Promise<string | null> => {
    if (!ergo) {
      throw createWalletError('wallet_error', 'Wallet not connected', ['Connect your wallet first']);
    }
    const txId = await ergo.submit_tx(signedTx);
    return txId;
  }, [ergo]);

  // ─── getUtxos ─────────────────────────────────────────────────

  const getUtxos = useCallback(async (): Promise<ErgoBox[]> => {
    if (!ergo) return [];
    return await ergo.get_utxos();
  }, [ergo]);

  // ─── getCurrentHeight ─────────────────────────────────────────

  const getCurrentHeight = useCallback(async (): Promise<number> => {
    if (!ergo) return 0;
    return await ergo.get_current_height();
  }, [ergo]);

  // ─── getChangeAddress ─────────────────────────────────────────

  const getChangeAddress = useCallback(async (): Promise<string | null> => {
    if (!ergo) return null;
    return await ergo.get_change_address();
  }, [ergo]);

  // ─── refreshBalance ───────────────────────────────────────────

  const refreshBalance = useCallback(async () => {
    if (!ergo || !state.isConnected) return;
    try {
      if (walletKey === 'ergopay' && state.walletAddress) {
        // ErgoPay uses explorer API for balance since stub context returns '0'
        const balResp = await fetch(`https://api.ergoplatform.com/api/v1/addresses/${state.walletAddress}/balance`);
        if (balResp.ok) {
          const balData = await balResp.json();
          const bal = balData.confirmed ? Number(balData.confirmed.nanoErgs) : 0;
          const tokens = (balData.confirmed?.tokens || []).map((t: any) => ({
            tokenId: t.tokenId,
            amount: t.amount,
            name: t.name,
            decimals: t.decimals,
          }));
          if (!isNaN(bal)) {
            setState(prev => ({ ...prev, balance: bal, tokens }));
          }
        }
      } else {
        const bal = parseNanoErg(await ergo.get_balance());
        const utxos = await ergo.get_utxos();
        const tokens = extractTokens(utxos);
        if (!isNaN(bal)) {
          setState(prev => ({ ...prev, balance: bal, tokens }));
        }
      }
    } catch (error: any) {
      console.error('Failed to refresh balance:', error);
      if (error?.code === -3) {
        setState(prev => ({ ...prev, isLocked: true }));
      }
    }
  }, [ergo, state.isConnected, walletKey, state.walletAddress]);

  // ─── clearError ───────────────────────────────────────────────

  const clearError = useCallback(() => {
    setState(prev => {
      const { error: _e, ...rest } = prev;
      return rest;
    });
  }, []);

  return {
    ...state,
    ergo,
    activeWalletKey: walletKey,
    connect,
    disconnect,
    signTransaction,
    submitTransaction,
    getUtxos,
    getCurrentHeight,
    getChangeAddress,
    refreshBalance,
    clearError,
  };
}
