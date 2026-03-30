/**
 * ErgoPay Wallet Adapter
 *
 * ErgoPay is a URL-based transaction signing protocol for Ergo.
 * Unlike browser extension wallets, ErgoPay works via a payment URL
 * that the user opens in their mobile wallet app (e.g., Yoroi, Gloze).
 *
 * Flow:
 *   1. dApp builds an unsigned transaction
 *   2. dApp creates an ErgoPay payment request (registers with ErgoPay service)
 *   3. dApp generates a payment URL for the user to scan/open
 *   4. User opens URL in their mobile wallet
 *   5. Mobile wallet signs and submits the transaction
 *   6. dApp polls for the transaction status
 *
 * For connection/identification purposes, ErgoPay requires the user to
 * provide their address manually or via QR scanning. The adapter uses
 * localStorage to persist the connected address.
 *
 * @see https://github.com/ergoplatform/ergo-pay
 * @see https://docs.ergoplatform.com/developer-tools/ergopay/
 */

import type { EIP12ContextAPI, ErgoBox, SignedInput, SignedTransaction, UnsignedTransaction } from '../../types/eip12';
import { createWalletError } from '../../types/walletErrors';
import type { WalletAdapter, WalletInfo, WalletId } from './types';

const STORAGE_KEY = 'duckpools:ergopay-address';

const ERGOPAY_INFO: WalletInfo = {
  id: 'ergopay' as WalletId,
  name: 'ErgoPay',
  icon: 'data:image/svg+xml,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
    '<rect width="100" height="100" rx="20" fill="#1B1B3A"/>' +
    '<path d="M50 20 C35 20 23 32 23 47 C23 62 35 74 50 74 C65 74 77 62 77 47 C77 32 65 20 50 20Z" fill="none" stroke="#8B5CF6" stroke-width="3"/>' +
    '<text x="50" y="55" text-anchor="middle" font-family="Arial" font-weight="bold" font-size="22" fill="#8B5CF6">EP</text>' +
    '</svg>'
  ),
  downloadUrl: 'https://docs.ergoplatform.com/developer-tools/ergopay/',
  mobileSupport: true,
  deepLinkScheme: 'https://paid.ergoplatform.com',
};

/**
 * ErgoPay does not provide a real EIP-12 context since signing happens
 * on the mobile device, not via the browser extension API. This stub
 * provides a minimal compatible interface so the existing wallet code
 * can treat it like any other adapter.
 *
 * The actual signing/submitting flow is handled by the ErgoPay URL
 * protocol — see buildErgoPayUrl() and pollErgoPayStatus().
 */
class ErgoPayContextStub implements EIP12ContextAPI {
  private address: string;

  constructor(address: string) {
    this.address = address;
  }

  async get_balance(_tokenId?: string): Promise<string> {
    // ErgoPay doesn't provide direct balance access.
    // The dApp backend should fetch balances from the Ergo node.
    // Return '0' as a fallback — the UI should use backend APIs for real balance.
    return '0';
  }

  async get_utxos(_filter?: unknown): Promise<ErgoBox[]> {
    // ErgoPay doesn't provide UTXO listing. Backend APIs handle this.
    return [];
  }

  async get_used_addresses(): Promise<string[]> {
    return [this.address];
  }

  async get_unused_addresses(): Promise<string[]> {
    return [];
  }

  async get_change_address(): Promise<string> {
    return this.address;
  }

  async get_current_height(): Promise<number> {
    // Fetch from the Ergo node directly
    try {
      const resp = await fetch('https://api.ergoplatform.com/api/v1/blocks?limit=1');
      const data = await resp.json();
      return data.items?.[0]?.height ?? 0;
    } catch {
      return 0;
    }
  }

  async sign_tx(_tx: UnsignedTransaction): Promise<SignedTransaction> {
    throw createWalletError(
      'wallet_error',
      'ErgoPay cannot sign transactions via browser API',
      ['Use buildErgoPayUrl() to generate a payment URL for mobile signing'],
    );
  }

  async sign_tx_input(_tx: UnsignedTransaction, _index: number): Promise<SignedInput> {
    throw createWalletError(
      'wallet_error',
      'ErgoPay cannot sign inputs via browser API',
      ['Use buildErgoPayUrl() to generate a payment URL for mobile signing'],
    );
  }

  async sign_data(_address: string, _message: string): Promise<string> {
    throw createWalletError(
      'wallet_error',
      'ErgoPay cannot sign data via browser API',
    );
  }

  async submit_tx(_tx: SignedTransaction): Promise<string> {
    throw createWalletError(
      'wallet_error',
      'ErgoPay cannot submit transactions via browser API',
      ['The mobile wallet handles submission automatically'],
    );
  }
}

export class ErgoPayAdapter implements WalletAdapter {
  readonly info: WalletInfo = ERGOPAY_INFO;
  private context: EIP12ContextAPI | null = null;

  /**
   * ErgoPay is always "available" — it's a URL-based protocol,
   * not a browser extension. Users connect by providing their address.
   */
  isAvailable(): boolean {
    return true;
  }

  async isConnected(): Promise<boolean> {
    return this.context !== null;
  }

  /**
   * Connect to ErgoPay by providing a wallet address.
   * The user must enter their address or scan a QR code.
   *
   * @param address - The Ergo address to connect with
   */
  async connect(address?: string): Promise<boolean> {
    if (!address) {
      // Try to restore from localStorage
      address = this.getPersistedAddress();
    }

    if (!address || typeof address !== 'string') {
      throw createWalletError(
        'wallet_error',
        'ErgoPay requires a wallet address to connect',
        ['Enter your Ergo address to connect via ErgoPay'],
      );
    }

    // Basic address validation
    if (!address.startsWith('9') && !address.startsWith('3') && !address.startsWith('4')) {
      throw createWalletError(
        'wallet_error',
        'Invalid Ergo address format',
        ['Enter a valid Ergo address starting with 9, 3, or 4'],
      );
    }

    this.context = new ErgoPayContextStub(address);
    this.persistAddress(address);
    return true;
  }

  async disconnect(): Promise<boolean> {
    this.context = null;
    this.clearPersistedAddress();
    return true;
  }

  async getContext(): Promise<EIP12ContextAPI> {
    if (!this.context) {
      throw createWalletError(
        'wallet_error',
        'ErgoPay not connected',
        ['Connect your Ergo address first'],
      );
    }
    return this.context;
  }

  async getAddress(): Promise<string> {
    const ctx = await this.getContext();
    return ctx.get_change_address();
  }

  async getBalance(tokenId?: string): Promise<string> {
    const ctx = await this.getContext();
    return ctx.get_balance(tokenId);
  }

  async getUtxos(): Promise<ErgoBox[]> {
    const ctx = await this.getContext();
    return ctx.get_utxos();
  }

  async signTx(_tx: UnsignedTransaction): Promise<SignedTransaction> {
    throw createWalletError(
      'wallet_error',
      'ErgoPay cannot sign transactions via browser API',
      ['Use buildErgoPayUrl() to generate a payment URL for the user\'s mobile wallet'],
    );
  }

  async submitTx(_tx: SignedTransaction): Promise<string> {
    throw createWalletError(
      'wallet_error',
      'ErgoPay cannot submit transactions via browser API',
      ['The mobile wallet handles submission automatically after signing'],
    );
  }

  // ─── ErgoPay-specific helpers ──────────────────────────────

  private getPersistedAddress(): string | undefined {
    try {
      return localStorage.getItem(STORAGE_KEY) ?? undefined;
    } catch {
      return undefined;
    }
  }

  private persistAddress(address: string): void {
    try {
      localStorage.setItem(STORAGE_KEY, address);
    } catch {
      // localStorage unavailable
    }
  }

  private clearPersistedAddress(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }
}

// ─── ErgoPay URL Builder ─────────────────────────────────────

/**
 * Build an ErgoPay payment URL from a serialized unsigned transaction.
 *
 * @param serializedTx - CBOR-Hex serialized unsigned transaction
 * @param message - Optional message shown to the user in the wallet
 * @param reducer - Optional ErgoPay reducer address for UTXO selection
 * @returns The ErgoPay URL to present to the user (QR code or deep link)
 */
export function buildErgoPayUrl(
  serializedTx: string,
  options?: {
    message?: string;
    reducer?: string;
    replyTo?: string;
  },
): string {
  const params = new URLSearchParams();

  // The serialized transaction is the main payload
  // For large transactions, use POST to the ErgoPay service instead
  if (serializedTx.length <= 15000) {
    params.set('unsignedTx', serializedTx);
  }

  if (options?.message) {
    params.set('message', options.message);
  }
  if (options?.reducer) {
    params.set('reducer', options.reducer);
  }
  if (options?.replyTo) {
    params.set('replyTo', options.replyTo);
  }

  const queryString = params.toString();
  return queryString
    ? `https://paid.ergoplatform.com/?${queryString}`
    : 'https://paid.ergoplatform.com/';
}

/**
 * Build an ErgoPay URL using the payment ID flow.
 *
 * For complex transactions, you can register the transaction with
 * an ErgoPay service and use the resulting payment ID. This is
 * preferred for large transactions that don't fit in a URL.
 *
 * @param paymentId - The payment ID from the ErgoPay service
 * @returns The ErgoPay URL
 */
export function buildErgoPayPaymentUrl(paymentId: string): string {
  return `https://paid.ergoplatform.com/api/${paymentId}`;
}

/**
 * Poll the ErgoPay service for transaction status.
 *
 * After the user opens the ErgoPay URL in their mobile wallet,
 * this function can be used to poll for the signed transaction.
 *
 * @param paymentId - The payment ID to poll
 * @param onSigned - Callback when the transaction is signed
 * @param onError - Callback on error
 * @param intervalMs - Polling interval in milliseconds (default: 3000)
 * @param maxAttempts - Maximum number of polling attempts (default: 100)
 */
export function pollErgoPayStatus(
  paymentId: string,
  onSigned: (txId: string) => void,
  onError: (error: string) => void,
  intervalMs = 3000,
  maxAttempts = 100,
): { cancel: () => void } {
  let cancelled = false;
  let attempts = 0;

  const poll = async () => {
    if (cancelled || attempts >= maxAttempts) {
      if (attempts >= maxAttempts && !cancelled) {
        onError('ErgoPay polling timed out — transaction may not have been signed');
      }
      return;
    }

    attempts++;

    try {
      const resp = await fetch(`https://paid.ergoplatform.com/api/${paymentId}`);
      if (!resp.ok) {
        // Payment ID not found yet, keep polling
        setTimeout(poll, intervalMs);
        return;
      }

      const data = await resp.json();

      if (data.status === 'signed' || data.txId) {
        onSigned(data.txId);
        return;
      }

      if (data.status === 'error' || data.error) {
        onError(data.error || 'ErgoPay signing failed');
        return;
      }

      // Still pending, keep polling
      setTimeout(poll, intervalMs);
    } catch {
      setTimeout(poll, intervalMs);
    }
  };

  // Start polling after a short delay to give the user time to open the URL
  setTimeout(poll, 2000);

  return {
    cancel: () => {
      cancelled = true;
    },
  };
}

/**
 * Register a transaction with the ErgoPay service (for large transactions).
 *
 * This sends the transaction to the ErgoPay API via POST and returns
 * a payment ID that can be used to build a shorter URL.
 *
 * @param serializedTx - CBOR-Hex serialized unsigned transaction
 * @param options - Optional parameters (message, reducer, replyTo)
 * @returns The payment ID for polling
 */
export async function registerErgoPayTransaction(
  serializedTx: string,
  options?: {
    message?: string;
    reducer?: string;
    replyTo?: string;
  },
): Promise<string> {
  const body: Record<string, string> = {
    unsignedTx: serializedTx,
  };

  if (options?.message) body.message = options.message;
  if (options?.reducer) body.reducer = options.reducer;
  if (options?.replyTo) body.replyTo = options.replyTo;

  const resp = await fetch('https://paid.ergoplatform.com/api/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    throw createWalletError(
      'wallet_error',
      `ErgoPay registration failed: ${resp.statusText}`,
    );
  }

  const data = await resp.json();
  return data.paymentId;
}
