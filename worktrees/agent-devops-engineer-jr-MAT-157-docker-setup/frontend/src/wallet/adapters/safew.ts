/**
 * SAFEW Wallet Adapter
 *
 * EIP-12 compatible wallet. Accessed via `window.ergoConnector.safew`.
 * Key differences from Nautilus:
 *  - getContext() may return a slightly different API surface
 *  - get_utxos() may not support the filter parameter (fall back to fetching all)
 *  - May not support sign_data or sign_tx_input
 *
 * @see https://safew.io/
 */
import type { EIP12ContextAPI, ErgoBox, SignedTransaction, UnsignedTransaction } from '../../types/eip12';
import { createWalletError } from '../../types/walletErrors';
import type { WalletAdapter, WalletInfo, WalletId } from './types';

const CONNECT_TIMEOUT = 10_000;
const DEFAULT_TIMEOUT = 5_000;

function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(createWalletError('timeout_error', `${label} timed out after ${ms}ms`)), ms),
    ),
  ]);
}

function wrapError(err: unknown, label: string): never {
  const msg = err instanceof Error ? err.message : String(err);
  if (msg.includes('reject') || msg.includes('denied') || msg.includes('cancel')) {
    throw createWalletError('user_rejected', `${label}: User rejected the request`);
  }
  throw createWalletError('wallet_error', `${label}: ${msg}`);
}

const SAFEW_INFO: WalletInfo = {
  id: 'safew' as WalletId,
  name: 'SAFEW',
  icon: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#1a1a2e" stroke="#00d4aa" stroke-width="4"/><rect x="30" y="35" width="40" height="30" rx="4" fill="none" stroke="#00d4aa" stroke-width="3"/><circle cx="50" cy="50" r="8" fill="#00d4aa"/><line x1="50" y1="30" x2="50" y2="38" stroke="#00d4aa" stroke-width="3"/></svg>'),
  downloadUrl: 'https://safew.io/',
  mobileSupport: true,
  deepLinkScheme: 'safew',
};

export class SafewAdapter implements WalletAdapter {
  readonly info: WalletInfo = SAFEW_INFO;
  private context: EIP12ContextAPI | null = null;

  private getConnector() {
    if (!window.ergoConnector?.safew) {
      throw createWalletError(
        'wallet_not_found',
        'SAFEW wallet extension not found',
        ['Install the SAFEW wallet from https://safew.io/'],
      );
    }
    return window.ergoConnector.safew;
  }

  isAvailable(): boolean {
    return !!window.ergoConnector?.safew;
  }

  isConnected(): Promise<boolean> {
    try {
      return withTimeout(this.getConnector().isConnected(), DEFAULT_TIMEOUT, 'SAFEW.isConnected');
    } catch (err) {
      wrapError(err, 'SAFEW.isConnected');
    }
  }

  async connect(): Promise<boolean> {
    try {
      const connector = this.getConnector();
      const connected = await withTimeout(connector.connect(), CONNECT_TIMEOUT, 'SAFEW.connect');
      if (connected) {
        this.context = await withTimeout(connector.getContext(), DEFAULT_TIMEOUT, 'SAFEW.getContext');
      }
      return connected;
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'SAFEW.connect');
    }
  }

  async disconnect(): Promise<boolean> {
    try {
      const result = await withTimeout(this.getConnector().disconnect(), DEFAULT_TIMEOUT, 'SAFEW.disconnect');
      this.context = null;
      return result;
    } catch (err) {
      this.context = null;
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'SAFEW.disconnect');
    }
  }

  async getContext(): Promise<EIP12ContextAPI> {
    if (this.context) return this.context;
    try {
      this.context = await withTimeout(this.getConnector().getContext(), DEFAULT_TIMEOUT, 'SAFEW.getContext');
      return this.context;
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'SAFEW.getContext');
    }
  }

  async getAddress(): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.get_change_address(), DEFAULT_TIMEOUT, 'SAFEW.getAddress');
    } catch (err) {
      wrapError(err, 'SAFEW.getAddress');
    }
  }

  async getBalance(tokenId?: string): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.get_balance(tokenId), DEFAULT_TIMEOUT, 'SAFEW.getBalance');
    } catch (err) {
      wrapError(err, 'SAFEW.getBalance');
    }
  }

  async getUtxos(filter?: { nanoErgs?: string; tokens?: Array<{ tokenId: string; amount: string }> }): Promise<ErgoBox[]> {
    const ctx = await this.getContext();
    try {
      // SAFEW may not support filter parameter — try with filter first, fall back
      if (filter) {
        try {
          return await withTimeout(ctx.get_utxos(filter), DEFAULT_TIMEOUT, 'SAFEW.getUtxos');
        } catch {
          // Filter not supported, fall back to fetching all UTXOs
        }
      }
      return await withTimeout(ctx.get_utxos(), DEFAULT_TIMEOUT, 'SAFEW.getUtxos');
    } catch (err) {
      wrapError(err, 'SAFEW.getUtxos');
    }
  }

  async signTx(tx: UnsignedTransaction): Promise<SignedTransaction> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.sign_tx(tx), DEFAULT_TIMEOUT, 'SAFEW.signTx');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('reject') || msg.includes('denied') || msg.includes('cancel')) {
        throw createWalletError('user_rejected', 'User rejected transaction signing');
      }
      throw createWalletError('signing_error', `SAFEW signTx: ${msg}`);
    }
  }

  async submitTx(tx: SignedTransaction): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.submit_tx(tx), DEFAULT_TIMEOUT, 'SAFEW.submitTx');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      throw createWalletError('submission_error', `SAFEW submitTx: ${msg}`);
    }
  }
}
