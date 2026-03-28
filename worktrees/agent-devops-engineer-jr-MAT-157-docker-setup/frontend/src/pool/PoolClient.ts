/**
 * HttpPoolClient - HTTP client for the LP liquidity pool backend
 *
 * Fetches data from the DuckPools backend /api/lp/* endpoints,
 * transforms snake_case responses to camelCase, and provides
 * utility formatting functions.
 *
 * MAT-15: Tokenized bankroll and liquidity pool
 */

import type {
  PoolStateResponse,
  APYResponse,
  LPBalanceResponse,
  EstimateResponse,
  TxResponse,
} from './types';
import {
  transformPoolState,
  transformAPY,
  transformBalance,
  transformEstimate,
  transformTx,
} from './types';

// ─── PoolClient Interface ────────────────────────────────────────────

export interface IPoolClient {
  getPoolState(): Promise<PoolStateResponse>;
  getLPPrice(): Promise<{ pricePerShareErg: string; totalSupply: string; totalValueErg: string }>;
  getBalance(address: string): Promise<LPBalanceResponse>;
  getAPY(avgBetSize?: number, betsPerBlock?: number): Promise<APYResponse>;
  estimateDeposit(amountNanoErg: number): Promise<EstimateResponse>;
  estimateWithdraw(shares: number): Promise<EstimateResponse>;
  buildDepositTx(amountNanoErg: number, address: string): Promise<TxResponse>;
  requestWithdraw(lpAmount: number, address: string): Promise<TxResponse>;
}

// ─── HttpPoolClient ──────────────────────────────────────────────────

export class HttpPoolClient implements IPoolClient {
  private readonly baseUrl: string;

  constructor(apiUrl: string = '/api') {
    // Ensure no trailing slash
    this.baseUrl = apiUrl.replace(/\/+$/, '');
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}/lp${path}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(
        body?.detail || body?.message || `Pool API error: ${response.status} ${response.statusText}`
      );
    }

    return response.json();
  }

  // ─── Query Endpoints ───────────────────────────────────────────────

  async getPoolState(): Promise<PoolStateResponse> {
    const raw = await this.request<Record<string, unknown>>('/pool');
    return transformPoolState(raw as any);
  }

  async getLPPrice(): Promise<{ pricePerShareErg: string; totalSupply: string; totalValueErg: string }> {
    const raw = await this.request<Record<string, string>>('/price');
    return {
      pricePerShareErg: raw['price_per_share_erg'] || raw['pricePerShareErg'] || '0',
      totalSupply: raw['total_supply'] || raw['totalSupply'] || '0',
      totalValueErg: raw['total_value_erg'] || raw['totalValueErg'] || '0',
    };
  }

  async getBalance(address: string): Promise<LPBalanceResponse> {
    const raw = await this.request<Record<string, unknown>>(`/balance/${encodeURIComponent(address)}`);
    return transformBalance(raw as any);
  }

  async getAPY(avgBetSize?: number, betsPerBlock?: number): Promise<APYResponse> {
    const params = new URLSearchParams();
    if (avgBetSize !== undefined) params.set('avg_bet_size', String(avgBetSize));
    if (betsPerBlock !== undefined) params.set('bets_per_block', String(betsPerBlock));

    const query = params.toString() ? `?${params.toString()}` : '';
    const raw = await this.request<Record<string, unknown>>(`/apy${query}`);
    return transformAPY(raw as any);
  }

  // ─── Estimate Endpoints ────────────────────────────────────────────

  async estimateDeposit(amountNanoErg: number): Promise<EstimateResponse> {
    const raw = await this.request<Record<string, string>>(
      `/estimate/deposit?amount=${amountNanoErg}`
    );
    return transformEstimate(raw as any);
  }

  async estimateWithdraw(shares: number): Promise<EstimateResponse> {
    const raw = await this.request<Record<string, string>>(
      `/estimate/withdraw?shares=${shares}`
    );
    return transformEstimate(raw as any);
  }

  // ─── Transaction Endpoints ─────────────────────────────────────────

  async buildDepositTx(amountNanoErg: number, address: string): Promise<TxResponse> {
    const raw = await this.request<Record<string, unknown>>('/deposit', {
      method: 'POST',
      body: JSON.stringify({
        amount: amountNanoErg,
        address,
      }),
    });
    return transformTx(raw as any);
  }

  async requestWithdraw(lpAmount: number, address: string): Promise<TxResponse> {
    const raw = await this.request<Record<string, unknown>>('/request-withdraw', {
      method: 'POST',
      body: JSON.stringify({
        lp_amount: lpAmount,
        address,
      }),
    });
    return transformTx(raw as any);
  }

  // ─── Advanced (not used in PoolUI but available) ───────────────────

  async executeWithdraw(boxId: string): Promise<TxResponse> {
    const raw = await this.request<Record<string, unknown>>('/execute-withdraw', {
      method: 'POST',
      body: JSON.stringify({ box_id: boxId }),
    });
    return transformTx(raw as any);
  }

  async cancelWithdraw(boxId: string): Promise<TxResponse> {
    const raw = await this.request<Record<string, unknown>>('/cancel-withdraw', {
      method: 'POST',
      body: JSON.stringify({ box_id: boxId }),
    });
    return transformTx(raw as any);
  }
}

// ─── Formatting Utilities ────────────────────────────────────────────

export const PoolFormatters = {
  /**
   * Convert nanoERG (bigint) to compact ERG string.
   * e.g., 1_500_000_000n → "1.5"
   */
  nanoErgToCompact(nano: bigint): string {
    const erg = Number(nano) / 1e9;
    if (erg === 0) return '0';
    // Up to 4 decimal places, strip trailing zeros
    return erg.toFixed(4).replace(/\.?0+$/, '');
  },

  /**
   * Convert a nanoERG string to compact ERG.
   * Accepts both bigint-string and decimal ERG strings.
   */
  nanoErgStringToCompact(nano: string): string {
    const num = parseFloat(nano);
    if (num >= 1e9) {
      // It's already in nanoERG
      return (num / 1e9).toFixed(4).replace(/\.?0+$/, '');
    }
    // It's already in ERG from the backend
    return num.toFixed(4).replace(/\.?0+$/, '');
  },

  /**
   * Format a number as percentage with 1-2 decimals.
   * e.g., 3.942 → "394.2%"
   */
  formatPercent(value: number): string {
    if (value === 0) return '0%';
    if (value >= 100) return `${value.toFixed(1)}%`;
    if (value >= 10) return `${value.toFixed(1)}%`;
    if (value >= 1) return `${value.toFixed(2)}%`;
    return `${value.toFixed(4)}%`;
  },

  /**
   * Format LP token amounts (nanoERG-scale bigint to readable).
   * e.g., 1_000_000_000n → "1.00 LP"
   */
  formatLPAmount(shares: string | bigint): string {
    const num = typeof shares === 'string' ? BigInt(shares) : shares;
    const lp = Number(num) / 1e9;
    if (lp === 0) return '0 LP';
    if (lp < 0.01) return '<0.01 LP';
    return `${lp.toFixed(2)} LP`;
  },

  /**
   * Format cooldown blocks to human-readable.
   * e.g., 60 → "~2.0 hours"
   */
  formatCooldown(blocks: number): string {
    const hours = (blocks * 2) / 60; // ~2 min blocks
    if (hours < 1) {
      return `~${Math.round(hours * 60)} min`;
    }
    return `~${hours.toFixed(1)} hours`;
  },

  /**
   * Truncate a hex string for display.
   * e.g., "abcdef0123456789" → "abcdef...6789"
   */
  truncateHex(hex: string, prefixLen = 6, suffixLen = 4): string {
    if (hex.length <= prefixLen + suffixLen + 3) return hex;
    return `${hex.slice(0, prefixLen)}...${hex.slice(-suffixLen)}`;
  },
} as const;
