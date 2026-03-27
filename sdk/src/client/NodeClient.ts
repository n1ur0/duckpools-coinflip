/**
 * DuckPools SDK - Node Client
 * HTTP client for interacting with Ergo node REST API
 */

import type { NodeClientConfig, NodeInfo, UnspentBox, WalletBalance } from '../types';
import { NodeError } from '../types';

export class NodeClient {
  private url: string;
  private apiKey: string | undefined;
  private timeout: number;

  constructor(config: NodeClientConfig) {
    this.url = config.url.replace(/\/$/, ''); // Remove trailing slash
    this.apiKey = config.apiKey;
    this.timeout = config.timeout || 30000;
  }

  /**
   * Make authenticated request to node API
   */
  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.apiKey) {
      (headers as Record<string, string>)['api_key'] = this.apiKey;
    }

    const response = await fetch(`${this.url}${path}`, {
      ...options,
      headers,
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      let errorText = await response.text().catch(() => 'Unknown error');
      try {
        const errorJson = JSON.parse(errorText);
        errorText = errorJson.detail || errorJson.error || errorText;
      } catch {
        // Not JSON, use as-is
      }
      throw new NodeError(
        `Node request failed: ${errorText}`,
        response.status,
        { path, options }
      );
    }

    return response.json() as Promise<T>;
  }

  /**
   * Get node info
   */
  async getInfo(): Promise<NodeInfo> {
    return this.request<NodeInfo>('/info');
  }

  /**
   * Get current blockchain height
   */
  async getCurrentHeight(): Promise<number> {
    const info = await this.getInfo();
    return info.fullHeight;
  }

  /**
   * Unlock wallet
   */
  async unlockWallet(password: string): Promise<void> {
    await this.request('/wallet/unlock', {
      method: 'POST',
      body: JSON.stringify({ pass: password }),
    });
  }

  /**
   * Get wallet status
   */
  async getWalletStatus(): Promise<{ initialized: boolean; unlocked: boolean }> {
    return this.request('/wallet/status');
  }

  /**
   * Get wallet addresses
   */
  async getWalletAddresses(): Promise<string[]> {
    return this.request('/wallet/addresses');
  }

  /**
   * Get wallet balances
   */
  async getWalletBalance(): Promise<WalletBalance> {
    const balance = await this.request<{ height: number; balance: number; assets: Record<string, number> }>(
      '/wallet/balances'
    );

    return {
      height: balance.height,
      balance: BigInt(balance.balance),
      assets: Object.fromEntries(
        Object.entries(balance.assets).map(([k, v]) => [k, BigInt(v)])
      ),
    };
  }

  /**
   * Get unspent boxes for wallet
   */
  async getUnspentBoxes(withUnconfirmed = false): Promise<UnspentBox[]> {
    const boxes = await this.request<any[]>('/wallet/boxes/unspent', {
      method: 'POST',
      body: JSON.stringify({ minConfirmations: withUnconfirmed ? 0 : 1 }),
    });

    return boxes.map(box => ({
      boxId: box.boxId,
      value: BigInt(box.value),
      ergoTree: box.ergoTree,
      assets: (box.assets || []).map((a: any) => ({
        tokenId: a.tokenId,
        amount: BigInt(a.amount),
        name: a.name,
        decimals: a.decimals,
      })),
      creationHeight: box.creationHeight,
      index: box.index,
      transactionId: box.transactionId,
    }));
  }

  /**
   * Get box by ID
   */
  async getBoxById(boxId: string): Promise<any> {
    return this.request(`/blockchain/box/byId/${boxId}`);
  }

  /**
   * Get unspent boxes by token ID
   */
  async getUnspentBoxesByTokenId(tokenId: string): Promise<any[]> {
    return this.request(`/blockchain/box/unspent/byTokenId/${tokenId}`);
  }

  /**
   * Get boxes by token ID (alias for getUnspentBoxesByTokenId)
   */
  async getBoxesByTokenId(tokenId: string): Promise<any[]> {
    return this.getUnspentBoxesByTokenId(tokenId);
  }

  /**
   * Get transaction by ID
   */
  async getTransactionById(txId: string): Promise<any> {
    return this.request(`/blockchain/transaction/byId/${txId}`);
  }

  /**
   * Get unconfirmed transaction by ID
   */
  async getUnconfirmedTransaction(txId: string): Promise<any> {
    return this.request(`/transactions/unconfirmed/byTransactionId/${txId}`);
  }

  /**
   * Get block header by height
   */
  async getBlockHeaderByHeight(height: number): Promise<any> {
    return this.request(`/blocks/at/${height}`);
  }

  /**
   * Submit transaction via wallet
   */
  async submitTransaction(tx: any): Promise<{ txId: string }> {
    const result = await this.request<string>('/wallet/transaction/send', {
      method: 'POST',
      body: JSON.stringify(tx),
    });
    return { txId: result };
  }

  /**
   * Submit payment transaction
   */
  async submitPayment(requests: any[], rawInputs: any[] = []): Promise<{ txId: string }> {
    const result = await this.request<string>('/wallet/payment/send', {
      method: 'POST',
      body: JSON.stringify({
        requests,
        rawInputs,
      }),
    });
    return { txId: result };
  }

  /**
   * Convert address to bytes (ErgoTree)
   */
  async addressToBytes(address: string): Promise<{ bytes: string }> {
    return this.request(`/script/addressToBytes/${address}`);
  }

  /**
   * Get UTxO size
   */
  async getUtxoSize(): Promise<number> {
    const info = await this.getInfo();
    return info.UTXOSize;
  }

  /**
   * Get peer count
   */
  async getPeerCount(): Promise<number> {
    const info = await this.getInfo();
    return info.peersCount;
  }

  /**
   * Check if node is mining
   */
  async isMining(): Promise<boolean> {
    const info = await this.getInfo();
    return info.isMining;
  }
}
