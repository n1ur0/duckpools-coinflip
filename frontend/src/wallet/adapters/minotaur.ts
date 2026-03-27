/**
 * Minotaur Wallet Adapter
 *
 * EIP-12 compatible wallet. Accessed via `window.ergoConnector.minotaur`.
 * Key differences from Nautilus:
 *  - May have timeout differences
 *  - UTXO selection may need different handling
 *
 * @see https://minotaurwallet.io/
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

const MINOTAUR_INFO: WalletInfo = {
  id: 'minotaur' as WalletId,
  name: 'Minotaur',
  icon: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#1a1a2e" stroke="#ff6b6b" stroke-width="4"/><polygon points="50,20 65,55 35,55" fill="none" stroke="#ff6b6b" stroke-width="3"/><line x1="50" y1="20" x2="50" y2="10" stroke="#ff6b6b" stroke-width="3"/><circle cx="50" cy="50" r="5" fill="#ff6b6b"/></svg>'),
  downloadUrl: 'https://minotaurwallet.io/',
  mobileSupport: true,
  deepLinkScheme: 'minotaur',
};

export class MinotaurAdapter implements WalletAdapter {
  readonly info: WalletInfo = MINOTAUR_INFO;
  private context: EIP12ContextAPI | null = null;

  private getConnector() {
    if (!window.ergoConnector?.minotaur) {
      throw createWalletError(
        'wallet_not_found',
        'Minotaur wallet extension not found',
        ['Install the Minotaur wallet from https://minotaurwallet.io/'],
      );
    }
    return window.ergoConnector.minotaur;
  }

  isAvailable(): boolean {
    return !!window.ergoConnector?.minotaur;
  }

  isConnected(): Promise<boolean> {
    try {
      return withTimeout(this.getConnector().isConnected(), DEFAULT_TIMEOUT, 'Minotaur.isConnected');
    } catch (err) {
      wrapError(err, 'Minotaur.isConnected');
    }
  }

  async connect(): Promise<boolean> {
    try {
      const connector = this.getConnector();
      const connected = await withTimeout(connector.connect(), CONNECT_TIMEOUT, 'Minotaur.connect');
      if (connected) {
        this.context = await withTimeout(connector.getContext(), DEFAULT_TIMEOUT, 'Minotaur.getContext');
      }
      return connected;
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'Minotaur.connect');
    }
  }

  async disconnect(): Promise<boolean> {
    try {
      const result = await withTimeout(this.getConnector().disconnect(), DEFAULT_TIMEOUT, 'Minotaur.disconnect');
      this.context = null;
      return result;
    } catch (err) {
      this.context = null;
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'Minotaur.disconnect');
    }
  }

  async getContext(): Promise<EIP12ContextAPI> {
    if (this.context) return this.context;
    try {
      this.context = await withTimeout(this.getConnector().getContext(), DEFAULT_TIMEOUT, 'Minotaur.getContext');
      return this.context;
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'Minotaur.getContext');
    }
  }

  async getAddress(): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.get_change_address(), DEFAULT_TIMEOUT, 'Minotaur.getAddress');
    } catch (err) {
      wrapError(err, 'Minotaur.getAddress');
    }
  }

  async getBalance(tokenId?: string): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.get_balance(tokenId), DEFAULT_TIMEOUT, 'Minotaur.getBalance');
    } catch (err) {
      wrapError(err, 'Minotaur.getBalance');
    }
  }

  async getUtxos(filter?: { nanoErgs?: string; tokens?: Array<{ tokenId: string; amount: string }> }): Promise<ErgoBox[]> {
    const ctx = await this.getContext();
    try {
      if (filter) {
        try {
          return await withTimeout(ctx.get_utxos(filter), DEFAULT_TIMEOUT, 'Minotaur.getUtxos');
        } catch {
          // Filter not supported, fall back
        }
      }
      return await withTimeout(ctx.get_utxos(), DEFAULT_TIMEOUT, 'Minotaur.getUtxos');
    } catch (err) {
      wrapError(err, 'Minotaur.getUtxos');
    }
  }

  async signTx(tx: UnsignedTransaction): Promise<SignedTransaction> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.sign_tx(tx), DEFAULT_TIMEOUT, 'Minotaur.signTx');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('reject') || msg.includes('denied') || msg.includes('cancel')) {
        throw createWalletError('user_rejected', 'User rejected transaction signing');
      }
      throw createWalletError('signing_error', `Minotaur signTx: ${msg}`);
    }
  }

  async submitTx(tx: SignedTransaction): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.submit_tx(tx), DEFAULT_TIMEOUT, 'Minotaur.submitTx');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      throw createWalletError('submission_error', `Minotaur submitTx: ${msg}`);
    }
  }
}
