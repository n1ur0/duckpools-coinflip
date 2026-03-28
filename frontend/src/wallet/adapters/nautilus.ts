/**
 * Nautilus Wallet Adapter
 *
 * Standard EIP-12 implementation. Accessed via `window.ergoConnector.nautilus`.
 * Nautilus has the most complete EIP-12 support of all Ergo wallets.
 *
 * @see https://github.com/nautls/nautilus-wallet
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

const NAUTILUS_INFO: WalletInfo = {
  id: 'nautilus' as WalletId,
  name: 'Nautilus',
  icon: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#1a1a2e" stroke="#f0b429" stroke-width="4"/><path d="M50 15 C30 15 15 35 15 55 C15 75 35 85 50 85 C65 85 85 75 85 55 C85 35 70 15 50 15Z" fill="#16213e" stroke="#f0b429" stroke-width="2"/><ellipse cx="50" cy="52" rx="12" ry="20" fill="#f0b429" opacity="0.8"/></svg>'),
  downloadUrl: 'https://nautiluswallet.io/',
  mobileSupport: false,
};

export class NautilusAdapter implements WalletAdapter {
  readonly info: WalletInfo = NAUTILUS_INFO;
  private context: EIP12ContextAPI | null = null;

  private getConnector() {
    if (!window.ergoConnector?.nautilus) {
      throw createWalletError(
        'wallet_not_found',
        'Nautilus wallet extension not found',
        ['Install the Nautilus wallet extension from https://nautiluswallet.io/'],
      );
    }
    return window.ergoConnector.nautilus;
  }

  isAvailable(): boolean {
    return !!window.ergoConnector?.nautilus;
  }

  isConnected(): Promise<boolean> {
    try {
      return withTimeout(this.getConnector().isConnected(), DEFAULT_TIMEOUT, 'Nautilus.isConnected');
    } catch (err) {
      wrapError(err, 'Nautilus.isConnected');
    }
  }

  async connect(): Promise<boolean> {
    try {
      const connector = this.getConnector();
      const connected = await withTimeout(connector.connect(), CONNECT_TIMEOUT, 'Nautilus.connect');
      if (connected) {
        this.context = await withTimeout(connector.getContext(), DEFAULT_TIMEOUT, 'Nautilus.getContext');
      }
      return connected;
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'Nautilus.connect');
    }
  }

  async disconnect(): Promise<boolean> {
    try {
      const result = await withTimeout(this.getConnector().disconnect(), DEFAULT_TIMEOUT, 'Nautilus.disconnect');
      this.context = null;
      return result;
    } catch (err) {
      this.context = null;
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'Nautilus.disconnect');
    }
  }

  async getContext(): Promise<EIP12ContextAPI> {
    if (this.context) return this.context;
    try {
      this.context = await withTimeout(this.getConnector().getContext(), DEFAULT_TIMEOUT, 'Nautilus.getContext');
      return this.context;
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err) throw err;
      wrapError(err, 'Nautilus.getContext');
    }
  }

  async getAddress(): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.get_change_address(), DEFAULT_TIMEOUT, 'Nautilus.getAddress');
    } catch (err) {
      wrapError(err, 'Nautilus.getAddress');
    }
  }

  async getBalance(tokenId?: string): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.get_balance(tokenId), DEFAULT_TIMEOUT, 'Nautilus.getBalance');
    } catch (err) {
      wrapError(err, 'Nautilus.getBalance');
    }
  }

  async getUtxos(filter?: { nanoErgs?: string; tokens?: Array<{ tokenId: string; amount: string }> }): Promise<ErgoBox[]> {
    const ctx = await this.getContext();
    try {
      // Nautilus supports filter objects in newer versions
      if (filter) {
        return await withTimeout(ctx.get_utxos(filter), DEFAULT_TIMEOUT, 'Nautilus.getUtxos');
      }
      return await withTimeout(ctx.get_utxos(), DEFAULT_TIMEOUT, 'Nautilus.getUtxos');
    } catch (err) {
      // Fallback: if filter fails, try without filter
      if (filter) {
        try {
          return await withTimeout(ctx.get_utxos(), DEFAULT_TIMEOUT, 'Nautilus.getUtxos');
        } catch {
          // ignore
        }
      }
      wrapError(err, 'Nautilus.getUtxos');
    }
  }

  async signTx(tx: UnsignedTransaction): Promise<SignedTransaction> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.sign_tx(tx), DEFAULT_TIMEOUT, 'Nautilus.signTx');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('reject') || msg.includes('denied') || msg.includes('cancel')) {
        throw createWalletError('user_rejected', 'User rejected transaction signing');
      }
      throw createWalletError('signing_error', `Nautilus signTx: ${msg}`);
    }
  }

  async submitTx(tx: SignedTransaction): Promise<string> {
    const ctx = await this.getContext();
    try {
      return await withTimeout(ctx.submit_tx(tx), DEFAULT_TIMEOUT, 'Nautilus.submitTx');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      throw createWalletError('submission_error', `Nautilus submitTx: ${msg}`);
    }
  }
}
