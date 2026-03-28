/**
 * Global type declarations for the Ergo wallet extension API.
 *
 * Wallet extensions inject `window.ergoConnector` with a map of
 * wallet names (e.g. 'nautilus', 'safew', 'minotaur') to their
 * EIP-12 connection objects.
 *
 * @see https://github.com/ergoplatform/eips/blob/master/eip-0012.md
 */

import type { EIP12ContextAPI, SignedTransaction, UnsignedTransaction } from './eip12';

/** EIP-12 connection object exposed by each wallet extension */
export interface ErgoConnectorWallet {
  connect(): Promise<boolean>;
  isConnected(): Promise<boolean>;
  disconnect(): Promise<boolean>;
  getContext(): Promise<EIP12ContextAPI>;
}

/** Shape of `window.ergoConnector` injected by Ergo wallet extensions */
export interface ErgoConnectorMap {
  nautilus?: ErgoConnectorWallet;
  safew?: ErgoConnectorWallet;
  minotaur?: ErgoConnectorWallet;
  [key: string]: ErgoConnectorWallet | undefined;
}

declare global {
  interface Window {
    ergoConnector?: ErgoConnectorMap;
  }
}

export {};
