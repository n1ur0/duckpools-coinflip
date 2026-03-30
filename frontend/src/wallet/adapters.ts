/**
 * Multi-wallet adapter definitions
 *
 * Each wallet implements the EIP-12 standard, so they share the same
 * connection interface. This module provides metadata (name, icon, install
 * URLs, deep-linking) and detection helpers for each supported wallet.
 *
 * @see https://github.com/ergoplatform/eips/blob/master/eip-0012.md
 */

import type { EIP12Connection } from '../types';

// ─── Wallet metadata ─────────────────────────────────────────────

export interface WalletInfo {
  /** Unique key used in window.ergoConnector[key] */
  key: string;
  /** Human-readable wallet name */
  name: string;
  /** Short name for UI badges */
  shortName: string;
  /** SVG path or emoji icon (inline-safe) */
  icon: string;
  /** Primary color for UI theming */
  color: string;
  /** Extension install URL (Chrome Web Store) */
  installUrl: string;
  /** Mobile deep-link URL scheme for QR codes */
  mobileScheme?: string;
  /** Whether this wallet is a mobile-first wallet */
  isMobile?: boolean;
}

// ─── Known wallets ───────────────────────────────────────────────

export const KNOWN_WALLETS: WalletInfo[] = [
  {
    key: 'nautilus',
    name: 'Nautilus',
    shortName: 'Naut',
    icon: '🐚',
    color: '#5B6AE0',
    installUrl: 'https://chromewebstore.google.com/detail/nautilus-wallet/gjmhjciegjkagokmoflcoohpkoggljdo',
    mobileScheme: 'https://nautiluswallet.io',
  },
  {
    key: 'safew',
    name: 'SAFEW',
    shortName: 'SAFEW',
    icon: '🛡️',
    color: '#10B981',
    installUrl: 'https://chromewebstore.google.com/detail/safew/ldpochfccmkkmhdbclfhpagapcfdljkj',
    mobileScheme: 'https://safew.io',
  },
  {
    key: 'minotaur',
    name: 'Minotaur',
    shortName: 'Mino',
    icon: '🪙',
    color: '#F59E0B',
    installUrl: 'https://chromewebstore.google.com/detail/minotaur-wallet/cpgeilhbgkmpnlhkhdjmkeoanibgmhpk',
    mobileScheme: 'https://minotaurwallet.io',
  },
  {
    key: 'ergopay',
    name: 'ErgoPay',
    shortName: 'ErgoPay',
    icon: '📱',
    color: '#8B5CF6',
    installUrl: 'https://docs.ergoplatform.com/developer-tools/ergopay/',
    mobileScheme: 'https://paid.ergoplatform.com',
    isMobile: true,
  },
];

/** Quick lookup by key */
const WALLET_MAP = new Map(KNOWN_WALLETS.map(w => [w.key, w]));

export function getWalletInfo(key: string): WalletInfo | undefined {
  return WALLET_MAP.get(key);
}

// ─── Detection ───────────────────────────────────────────────────

/**
 * Poll for window.ergoConnector injection.
 * Browser extensions inject asynchronously after page load.
 */
export function waitForConnector(timeoutMs = 3000): Promise<boolean> {
  return new Promise(resolve => {
    if (window.ergoConnector) return resolve(true);
    const t0 = Date.now();
    const id = setInterval(() => {
      if (window.ergoConnector) { clearInterval(id); resolve(true); }
      else if (Date.now() - t0 >= timeoutMs) { clearInterval(id); resolve(false); }
    }, 100);
  });
}

/**
 * Poll for a specific wallet key in window.ergoConnector.
 * Unlike waitForConnector which checks for the top-level object,
 * this checks for a specific wallet entry (e.g. 'nautilus').
 */
export function waitForWalletKey(key: string, timeoutMs = 5000): Promise<boolean> {
  return new Promise(resolve => {
    if (window.ergoConnector?.[key]) return resolve(true);
    const t0 = Date.now();
    const id = setInterval(() => {
      if (window.ergoConnector?.[key]) { clearInterval(id); resolve(true); }
      else if (Date.now() - t0 >= timeoutMs) { clearInterval(id); resolve(false); }
    }, 100);
  });
}

/**
 * Get the EIP-12 connection for a specific wallet.
 * Returns null if the wallet extension is not installed.
 */
export function getWalletConnection(key: string): EIP12Connection | null {
  return (window.ergoConnector?.[key] as EIP12Connection | undefined) ?? null;
}

/**
 * Detect which wallet extensions are installed.
 * Returns a list of wallet keys that are available.
 * Uses a longer timeout (5s) since extensions can be slow to inject.
 */
export async function detectAvailableWallets(timeoutMs = 5000): Promise<string[]> {
  await waitForConnector(timeoutMs);
  if (!window.ergoConnector) return [];

  const available: string[] = [];
  for (const wallet of KNOWN_WALLETS) {
    if (window.ergoConnector[wallet.key]) {
      available.push(wallet.key);
    }
  }
  return available;
}

/**
 * Build a mobile deep-link URL for connecting to a dApp.
 * Format: {scheme}?dapp={origin}&action=connect
 */
export function buildMobileDeepLink(wallet: WalletInfo, dappOrigin: string): string {
  if (!wallet.mobileScheme) return '';
  const separator = wallet.mobileScheme.includes('?') ? '&' : '?';
  return `${wallet.mobileScheme}${separator}dapp=${encodeURIComponent(dappOrigin)}&action=connect`;
}

/**
 * Check if the current device is likely mobile.
 */
export function isMobileDevice(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
}

/**
 * Generate a QR-code-safe data URL for a mobile deep-link.
 * Returns the deep-link URL (the UI component will render it as QR).
 */
export function getMobileConnectUrl(walletKey: string, dappOrigin: string): string | null {
  const info = getWalletInfo(walletKey);
  if (!info?.mobileScheme) return null;
  return buildMobileDeepLink(info, dappOrigin);
}
