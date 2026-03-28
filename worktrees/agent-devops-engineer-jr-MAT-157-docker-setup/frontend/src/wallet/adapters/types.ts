/**
 * Wallet adapter interface — the abstraction layer.
 * All wallet implementations (Nautilus, SAFEW, Minotaur) implement this.
 */
import type { EIP12ContextAPI, ErgoBox, SignedTransaction, UnsignedTransaction } from '../../types/eip12';

export type WalletId = 'nautilus' | 'safew' | 'minotaur';

export interface WalletInfo {
  id: WalletId;
  name: string;
  icon: string; // SVG data URI or emoji
  downloadUrl: string;
  mobileSupport: boolean;
  deepLinkScheme?: string;
}

export interface WalletAdapter {
  readonly info: WalletInfo;
  /** Check if this wallet extension is installed */
  isAvailable(): boolean;
  /** Check if dApp is currently connected to this wallet */
  isConnected(): Promise<boolean>;
  /** Request wallet connection (shows popup) */
  connect(): Promise<boolean>;
  /** Disconnect from wallet */
  disconnect(): Promise<boolean>;
  /** Get the EIP-12 context API for signing operations */
  getContext(): Promise<EIP12ContextAPI>;
  /** Get the connected wallet address */
  getAddress(): Promise<string>;
  /** Get ERG balance in nanoERG */
  getBalance(tokenId?: string): Promise<string>;
  /** Get UTXOs */
  getUtxos(filter?: { nanoErgs?: string; tokens?: Array<{ tokenId: string; amount: string }> }): Promise<ErgoBox[]>;
  /** Sign a transaction */
  signTx(tx: UnsignedTransaction): Promise<SignedTransaction>;
  /** Submit a signed transaction */
  submitTx(tx: SignedTransaction): Promise<string>;
}

export interface WalletAdapterFactory {
  create(): WalletAdapter;
}
