/**
 * DuckPools SDK - Pool Client
 * Frontend HTTP client for liquidity pool API
 *
 * MAT-15: Tokenized bankroll and liquidity pool
 */

import type {
  PoolStateResponse,
  APYResponse,
  EstimateResponse,
  LPBalanceResponse,
  TxResponse,
  PoolClient,
} from './types.js';

/**
 * HTTP-based pool client for frontend usage
 */
export class HttpPoolClient implements PoolClient {
  private baseUrl: string;

  constructor(baseUrl: string = '/api') {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}/lp${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error((error as any).detail || `Pool API error: ${response.status}`);
    }

    return response.json() as Promise<T>;
  }

  async getPoolState(): Promise<PoolStateResponse> {
    return this.request<PoolStateResponse>('/pool');
  }

  async getPrice(): Promise<{ pricePerShare: string; pricePerShareErg: string }> {
    return this.request('/price');
  }

  async getBalance(address: string): Promise<LPBalanceResponse> {
    return this.request<LPBalanceResponse>(`/balance/${encodeURIComponent(address)}`);
  }

  async getAPY(avgBetSize?: string, betsPerBlock?: number): Promise<APYResponse> {
    const params = new URLSearchParams();
    if (avgBetSize !== undefined) params.set('avg_bet_size', avgBetSize);
    if (betsPerBlock !== undefined) params.set('bets_per_block', String(betsPerBlock));
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request<APYResponse>(`/apy${query}`);
  }

  async estimateDeposit(amountNanoErg: number): Promise<EstimateResponse> {
    return this.request<EstimateResponse>(
      `/estimate/deposit?amount=${amountNanoErg}`
    );
  }

  async estimateWithdraw(shares: number): Promise<EstimateResponse> {
    return this.request<EstimateResponse>(
      `/estimate/withdraw?shares=${shares}`
    );
  }

  async buildDepositTx(amountNanoErg: number, address: string): Promise<TxResponse> {
    return this.request<TxResponse>('/deposit', {
      method: 'POST',
      body: JSON.stringify({ amount: amountNanoErg, address }),
    });
  }

  async requestWithdraw(lpAmount: number, address: string): Promise<TxResponse> {
    return this.request<TxResponse>('/request-withdraw', {
      method: 'POST',
      body: JSON.stringify({ lpAmount, address }),
    });
  }

  async executeWithdraw(boxId: string): Promise<TxResponse> {
    return this.request<TxResponse>('/execute-withdraw', {
      method: 'POST',
      body: JSON.stringify({ boxId }),
    });
  }

  async cancelWithdraw(boxId: string): Promise<TxResponse> {
    return this.request<TxResponse>('/cancel-withdraw', {
      method: 'POST',
      body: JSON.stringify({ boxId }),
    });
  }
}

/**
 * Formatting helpers for the pool UI
 */
export const PoolFormatters = {
  /** nanoERG → ERG string */
  nanoErgToErg(nanoErg: string | number | bigint): string {
    const value = typeof nanoErg === 'bigint' ? nanoErg : BigInt(nanoErg);
    const erg = Number(value) / 1e9;
    return erg.toFixed(9).replace(/\.?0+$/, '');
  },

  /** nanoERG → compact ERG string (e.g., "1.234") */
  nanoErgToCompact(nanoErg: string | number | bigint, decimals = 3): string {
    const value = typeof nanoErg === 'bigint' ? nanoErg : BigInt(nanoErg);
    const erg = Number(value) / 1e9;
    return erg.toFixed(decimals);
  },

  /** LP token amount → readable string */
  formatLPAmount(amount: string | number | bigint, decimals = 9): string {
    const value = typeof amount === 'bigint' ? amount : BigInt(amount);
    const divisor = BigInt(10 ** decimals);
    const whole = value / divisor;
    const fraction = value % divisor;

    const fractionStr = fraction.toString().padStart(decimals, '0').replace(/0+$/, '');
    if (fractionStr === '') {
      return whole.toString();
    }
    return `${whole}.${fractionStr}`;
  },

  /** Percentage to readable string */
  formatPercent(value: number, decimals = 2): string {
    return `${value.toFixed(decimals)}%`;
  },

  /** Cooldown blocks → human-readable time */
  formatCooldown(blocks: number): string {
    const minutes = blocks * 2;  // ~2 min block time
    if (minutes < 60) return `${minutes} min`;
    const hours = minutes / 60;
    if (hours < 24) return `${hours.toFixed(1)}h`;
    const days = hours / 24;
    return `${days.toFixed(1)} days`;
  },

  /** BigInt to string for display */
  bigIntToStr(value: string | bigint): string {
    return typeof value === 'string' ? value : value.toString();
  },
};
