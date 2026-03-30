/**
 * Wallet Registry — singleton that manages wallet adapters.
 *
 * Responsibilities:
 *  - Detects which wallets are installed
 *  - Manages the current active adapter
 *  - Provides wallet switching without page reload
 *  - Factory pattern for creating adapters
 */
import { NautilusAdapter } from './adapters/nautilus';
import { SafewAdapter } from './adapters/safew';
import { MinotaurAdapter } from './adapters/minotaur';
import { ErgoPayAdapter } from './adapters/ergopay';
import type { WalletAdapter, WalletId, WalletInfo } from './adapters/types';

export type WalletRegistryEvents = {
  /** Fired when the active wallet changes (adapter or connection state) */
  change: (adapter: WalletAdapter | null) => void;
  /** Fired when detected wallets list changes */
  detect: (wallets: WalletInfo[]) => void;
};

type EventCallback = WalletRegistryEvents[keyof WalletRegistryEvents];

const STORAGE_KEY = 'duckpools:last-wallet';

class WalletRegistry {
  private static instance: WalletRegistry;
  private adapters = new Map<WalletId, WalletAdapter>();
  private activeAdapter: WalletAdapter | null = null;
  private listeners = new Map<keyof WalletRegistryEvents, Set<EventCallback>>();

  private constructor() {
    // Register built-in adapters
    this.adapters.set('nautilus', new NautilusAdapter());
    this.adapters.set('safew', new SafewAdapter());
    this.adapters.set('minotaur', new MinotaurAdapter());
    this.adapters.set('ergopay', new ErgoPayAdapter());
  }

  static getInstance(): WalletRegistry {
    if (!WalletRegistry.instance) {
      WalletRegistry.instance = new WalletRegistry();
    }
    return WalletRegistry.instance;
  }

  // ─── Detection ────────────────────────────────────────────────

  /** Get info for all registered wallet adapters */
  getAllWallets(): WalletInfo[] {
    return Array.from(this.adapters.values()).map((a) => a.info);
  }

  /** Get info only for wallets that are currently installed */
  getAvailableWallets(): WalletInfo[] {
    return this.getAllWallets().filter((info) => this.adapters.get(info.id)!.isAvailable());
  }

  /** Check if a specific wallet is installed */
  isWalletAvailable(id: WalletId): boolean {
    return this.adapters.get(id)?.isAvailable() ?? false;
  }

  /** Get adapter by wallet ID */
  getAdapter(id: WalletId): WalletAdapter | undefined {
    return this.adapters.get(id);
  }

  // ─── Active Wallet ────────────────────────────────────────────

  /** Get the currently active wallet adapter */
  getActiveAdapter(): WalletAdapter | null {
    return this.activeAdapter;
  }

  /** Get the currently active wallet ID */
  getActiveWalletId(): WalletId | null {
    return this.activeAdapter?.info.id ?? null;
  }

  /** Get the last-used wallet ID from localStorage */
  getLastWalletId(): WalletId | null {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored && this.adapters.has(stored as WalletId)) {
        return stored as WalletId;
      }
    } catch {
      // localStorage unavailable
    }
    return null;
  }

  /** Persist last-used wallet ID */
  private persistLastWallet(id: WalletId): void {
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // localStorage unavailable
    }
  }

  /** Set the active wallet adapter */
  setActiveAdapter(id: WalletId): void {
    const adapter = this.adapters.get(id);
    if (!adapter) {
      throw new Error(`Unknown wallet ID: ${id}`);
    }
    if (this.activeAdapter?.info.id !== id) {
      this.activeAdapter = adapter;
      this.persistLastWallet(id);
      this.emit('change', adapter);
    }
  }

  /** Clear the active wallet (e.g. after disconnect) */
  clearActiveAdapter(): void {
    if (this.activeAdapter) {
      this.activeAdapter = null;
      this.emit('change', null);
    }
  }

  // ─── Events ───────────────────────────────────────────────────

  on<K extends keyof WalletRegistryEvents>(event: K, callback: WalletRegistryEvents[K]): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback as EventCallback);
    return () => this.listeners.get(event)?.delete(callback as EventCallback);
  }

  private emit<K extends keyof WalletRegistryEvents>(event: K, ...args: Parameters<WalletRegistryEvents[K]>): void {
    this.listeners.get(event)?.forEach((cb) => {
      try {
        (cb as (...a: unknown[]) => void)(...args);
      } catch {
        // Swallow listener errors
      }
    });
  }
}

export const walletRegistry = WalletRegistry.getInstance();
