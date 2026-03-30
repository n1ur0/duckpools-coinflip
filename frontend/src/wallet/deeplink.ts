/**
 * Mobile deep-linking utilities for Ergo wallets.
 *
 * Generates deep-link URLs for mobile wallets and provides
 * mobile user-agent detection. QR code rendering is left to
 * the UI layer (we just provide the URLs).
 */
import type { WalletId, WalletInfo } from './adapters/types';
import { walletRegistry } from './registry';

/** Deep-link schemes for supported wallets */
const DEEP_LINK_SCHEMES: Record<WalletId, string> = {
  nautilus: 'https://nautiluswallet.io/',
  safew: 'safew://',
  minotaur: 'minotaur://',
  ergopay: 'https://paid.ergoplatform.com/',
};

/**
 * Check if the current user agent is a mobile device.
 */
export function isMobileUserAgent(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  return /Android|iPhone|iPad|iPod|Mobile/i.test(ua);
}

/**
 * Check if the app is running inside a specific wallet's in-app browser.
 */
export function isInWalletBrowser(walletId?: WalletId): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  switch (walletId) {
    case 'nautilus':
      return /Nautilus/i.test(ua);
    case 'safew':
      return /SAFEW/i.test(ua);
    case 'minotaur':
      return /Minotaur/i.test(ua);
    case 'ergopay':
      return false; // ErgoPay doesn't have an in-app browser
    default:
      return /Nautilus|SAFEW|Minotaur/i.test(ua);
  }
}

/**
 * Get the deep-link URL for a specific wallet.
 * This URL can be used for QR codes or direct redirect.
 */
export function getDeepLinkUrl(walletId: WalletId, dappUrl?: string): string {
  const scheme = DEEP_LINK_SCHEMES[walletId];
  // Nautilus doesn't have a mobile deep-link scheme, return download URL
  if (walletId === 'nautilus') {
    return scheme;
  }
  // For other wallets, append the dApp URL if provided
  if (dappUrl) {
    return `${scheme}${encodeURIComponent(dappUrl)}`;
  }
  return scheme;
}

/**
 * Get the download URL for a wallet (useful when wallet is not installed).
 */
export function getWalletDownloadUrl(walletId: WalletId): string {
  const adapter = walletRegistry.getAdapter(walletId);
  return adapter?.info.downloadUrl ?? '';
}

/**
 * Redirect to a wallet's deep-link (for mobile).
 * Opens the deep-link in the current tab, with a fallback timeout.
 */
export function redirectToWallet(walletId: WalletId, dappUrl?: string): void {
  const url = getDeepLinkUrl(walletId, dappUrl);
  // Attempt to open the deep-link
  window.location.href = url;

  // If the deep-link fails (wallet not installed), user will need to navigate back.
  // We could set a fallback timer, but that's fragile across browsers.
}

/**
 * Get all wallet deep-link info for the mobile connect UI.
 */
export function getMobileWalletOptions(dappUrl?: string): Array<{
  walletId: WalletId;
  info: WalletInfo;
  deepLink: string;
  installed: boolean;
}> {
  return walletRegistry.getAllWallets()
    .filter((info) => info.mobileSupport)
    .map((info) => ({
      walletId: info.id,
      info,
      deepLink: getDeepLinkUrl(info.id, dappUrl),
      installed: walletRegistry.isWalletAvailable(info.id),
    }));
}
