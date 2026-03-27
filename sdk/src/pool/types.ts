/**
 * DuckPools SDK - LP Pool Type Definitions
 * TypeScript types for liquidity pool operations
 *
 * MAT-15: Tokenized bankroll and liquidity pool
 */

// ─── Pool Configuration ─────────────────────────────────────────────

export interface PoolConfig {
  /** Minimum deposit in nanoERG */
  minDeposit: bigint;
  /** Withdrawal cooldown in blocks */
  cooldownBlocks: number;
  /** House edge in basis points (300 = 3%) */
  houseEdgeBps: number;
  /** Minimum pool value in nanoERG (anti-drain) */
  minPoolValue: bigint;
  /** LP token decimals */
  lpTokenDecimals: number;
}

// ─── Pool State (from API) ─────────────────────────────────────────

export interface PoolStateResponse {
  bankroll: string;
  bankrollErg: string;
  totalSupply: string;
  totalValue: string;
  totalValueErg: string;
  pricePerShare: string;
  pricePerShareErg: string;
  houseEdgeBps: number;
  cooldownBlocks: number;
  cooldownHours: number;
  pendingBets: number;
}

// ─── APY ────────────────────────────────────────────────────────────

export interface APYResponse {
  apyPercent: number;
  houseEdgeBps: number;
  avgBetSizeErg: string;
  betsPerBlock: number;
  estimatedDailyProfitErg: string;
  estimatedMonthlyProfitErg: string;
  estimatedYearlyProfitErg: string;
}

// ─── Estimates ──────────────────────────────────────────────────────

export interface EstimateResponse {
  shares: string;
  ergAmount: string;
  pricePerShare: string;
  newTotalValue: string;
}

// ─── LP Balance ─────────────────────────────────────────────────────

export interface LPBalanceResponse {
  address: string;
  lpBalance: string;
  ergValue: string;
  sharePercent: number;
}

// ─── Transactions ───────────────────────────────────────────────────

export interface TxResponse {
  txId: string | null;
  txJson: Record<string, unknown>;
  message: string;
}

// ─── Deposit/Withdraw ──────────────────────────────────────────────

export interface DepositRequest {
  amount: number;  // nanoERG
  address: string;
}

export interface WithdrawRequestCreate {
  lpAmount: number;
  address: string;
}

export interface WithdrawExecuteRequest {
  boxId: string;
}

export interface WithdrawCancelRequest {
  boxId: string;
}

// ─── Withdrawal Status ─────────────────────────────────────────────

export type WithdrawalStatus = 'pending' | 'mature' | 'executed' | 'cancelled';

export interface WithdrawalInfo {
  boxId: string;
  holderAddress: string;
  lpAmount: bigint;
  requestedErg: bigint;
  requestHeight: number;
  cooldownDelta: number;
  executableHeight: number;
  isMature: boolean;
  status: WithdrawalStatus;
}

// ─── Pool Client (Frontend) ─────────────────────────────────────────

export interface PoolClient {
  /** Get pool state */
  getPoolState(): Promise<PoolStateResponse>;
  /** Get LP token price */
  getPrice(): Promise<{ pricePerShare: string; pricePerShareErg: string }>;
  /** Get LP balance for address */
  getBalance(address: string): Promise<LPBalanceResponse>;
  /** Calculate APY */
  getAPY(avgBetSize?: string, betsPerBlock?: number): Promise<APYResponse>;
  /** Estimate deposit */
  estimateDeposit(amountNanoErg: number): Promise<EstimateResponse>;
  /** Estimate withdrawal */
  estimateWithdraw(shares: number): Promise<EstimateResponse>;
  /** Build deposit transaction */
  buildDepositTx(amountNanoErg: number, address: string): Promise<TxResponse>;
  /** Create withdrawal request */
  requestWithdraw(lpAmount: number, address: string): Promise<TxResponse>;
  /** Execute matured withdrawal */
  executeWithdraw(boxId: string): Promise<TxResponse>;
  /** Cancel withdrawal */
  cancelWithdraw(boxId: string): Promise<TxResponse>;
}
