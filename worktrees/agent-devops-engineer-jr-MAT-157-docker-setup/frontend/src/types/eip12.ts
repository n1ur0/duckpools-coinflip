/**
 * EIP-12 Nautilus Wallet Types
 *
 * Uses the official EIP-12 dApp Connector standard.
 * Nautilus exposes snake_case method names:
 *   connect(), disconnect(), isConnected(), getContext()
 *   get_balance(), get_utxos(), get_change_address(),
 *   sign_tx(), submit_tx(), get_current_height()
 *
 * @see https://github.com/ergoplatform/eips/blob/master/eip-0012.md
 * @see https://github.com/nautls/nautilus-wallet
 */

// ─── ErgoBox (UTXO) ──────────────────────────────────────────────

export interface Asset {
  tokenId: string;
  amount: string;
  name?: string;
  decimals?: number;
  type?: string;
}

export interface Registers {
  R4?: string;
  R5?: string;
  R6?: string;
  R7?: string;
  R8?: string;
  R9?: string;
}

export interface ErgoBox {
  boxId: string;
  transactionId: string;
  value: string;           // nanoERG
  index: number;
  creationHeight: number;
  ergoTree: string;
  address?: string;
  assets: Asset[];
  additionalRegisters: Registers;
}

// ─── Transaction types ───────────────────────────────────────────

export interface UnsignedInput {
  boxId: string;
  extension?: Record<string, string>;
}

export interface SignedInput {
  boxId: string;
  spendingProof: {
    proofBytes: string;
    extension: Record<string, string>;
  };
}

export interface UnsignedTransaction {
  inputs: UnsignedInput[];
  dataInputs: Array<{ boxId: string }>;
  outputs: Array<{
    value: string;
    ergoTree: string;
    creationHeight: number;
    assets: Asset[];
    additionalRegisters: Registers;
  }>;
}

export interface SignedTransaction {
  id: string;
  inputs: SignedInput[];
  dataInputs: Array<{ boxId: string }>;
  outputs: ErgoBox[];
}

// ─── Wallet Connection API (window.ergoConnector.nautilus) ───────

export interface EIP12Connection {
  /** Request wallet connection — triggers permission popup */
  connect(): Promise<boolean>;
  /** Check if dApp is currently connected */
  isConnected(): Promise<boolean>;
  /** Disconnect from wallet */
  disconnect(): Promise<boolean>;
  /** Get the context API object after connecting */
  getContext(): Promise<EIP12ContextAPI>;
}

// ─── Context API (the ergo object) ───────────────────────────────

export interface UtxoSelector {
  nanoErgs?: string;
  tokens?: Array<{ tokenId: string; amount: string }>;
}

export interface EIP12ContextAPI {
  /** Get ERG balance (nanoERG string) or specific token balance */
  get_balance(tokenId?: string): Promise<string>;
  /** Get UTXOs. Accepts optional filter in newer Nautilus versions. */
  get_utxos(filter?: UtxoSelector | number): Promise<ErgoBox[]>;
  /** Get used addresses */
  get_used_addresses(paging?: { limit?: number; offset?: number }): Promise<string[]>;
  /** Get unused addresses */
  get_unused_addresses(): Promise<string[]>;
  /** Get change address */
  get_change_address(): Promise<string>;
  /** Get current blockchain height */
  get_current_height(): Promise<number>;
  /** Sign an unsigned transaction — user approves in popup */
  sign_tx(tx: UnsignedTransaction): Promise<SignedTransaction>;
  /** Sign a single input */
  sign_tx_input(tx: UnsignedTransaction, index: number): Promise<SignedInput>;
  /** Sign arbitrary data with a wallet key */
  sign_data(address: string, message: string): Promise<string>;
  /** Submit a signed transaction */
  submit_tx(tx: SignedTransaction): Promise<string>;
}

// ─── Convenience aliases ─────────────────────────────────────────

export type TokenAmount = Asset & { name: string; decimals: number };

// ─── ErgoLib WASM stub interface ────────────────────────────────

/** Minimal subset of ergo-lib-wasm-browser used by utils/ergoLib.ts */
export interface IErgoLib {
  Address: {
    from_base58(address: string): {
      to_ergo_tree(): {
        to_hex(): string;
      };
    };
  };
}
