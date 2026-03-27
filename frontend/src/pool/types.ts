/**
 * Pool Types - TypeScript type definitions for the LP liquidity pool
 *
 * These types define the frontend-facing data structures.
 * The HttpPoolClient transforms backend snake_case responses
 * into these camelCase types.
 *
 * MAT-15: Tokenized bankroll and liquidity pool
 */

// ─── Pool State ──────────────────────────────────────────────────────

/** Current pool state from GET /api/lp/pool */
export interface PoolStateResponse {
  /** Bankroll in nanoERG (raw string) */
  bankroll: string;
  /** Bankroll in ERG (formatted string) */
  bankrollErg: string;
  /** LP token total supply (raw string) */
  totalSupply: string;
  /** Total value = bankroll + pending bets (raw string) */
  totalValue: string;
  /** Total value in ERG (formatted string) */
  totalValueErg: string;
  /** Price per LP share with precision factor (raw string) */
  pricePerShare: string;
  /** Price per LP share in ERG (formatted string) */
  pricePerShareErg: string;
  /** House edge in basis points (e.g., 300 = 3%) */
  houseEdgeBps: number;
  /** Withdrawal cooldown in blocks */
  cooldownBlocks: number;
  /** Withdrawal cooldown in hours */
  cooldownHours: number;
  /** Number of pending bets locking pool value */
  pendingBets: number;
}

// ─── APY ─────────────────────────────────────────────────────────────

/** APY calculation result from GET /api/lp/apy */
export interface APYResponse {
  /** Annualized percentage yield */
  apyPercent: number;
  /** House edge in basis points */
  houseEdgeBps: number;
  /** Average bet size used for calculation (ERG string) */
  avgBetSizeErg: string;
  /** Bets per block used for calculation */
  betsPerBlock: number;
  /** Estimated daily profit in nanoERG (string) */
  estimatedDailyProfitErg: string;
  /** Estimated monthly profit in nanoERG (string) */
  estimatedMonthlyProfitErg: string;
  /** Estimated yearly profit in nanoERG (string) */
  estimatedYearlyProfitErg: string;
}

// ─── LP Balance ──────────────────────────────────────────────────────

/** LP token balance for an address from GET /api/lp/balance/{address} */
export interface LPBalanceResponse {
  /** Wallet address queried */
  address: string;
  /** LP token balance (raw string) */
  lpBalance: string;
  /** Equivalent ERG value (formatted string) */
  ergValue: string;
  /** Percentage of pool owned (0-100) */
  sharePercent: number;
}

// ─── Estimate ────────────────────────────────────────────────────────

/** Deposit/withdraw estimate from GET /api/lp/estimate/* */
export interface EstimateResponse {
  /** LP shares (mint or burn) as string */
  shares: string;
  /** ERG amount (deposit or withdraw) as string */
  ergAmount: string;
  /** Current price per share (raw string) */
  pricePerShare: string;
  /** New pool total value (raw string) */
  newTotalValue: string;
}

// ─── Transaction ─────────────────────────────────────────────────────

/** Transaction response from POST /api/lp/* */
export interface TxResponse {
  /** Transaction ID if submitted to node */
  txId: string | null;
  /** Built transaction JSON for signing */
  txJson: Record<string, unknown>;
  /** Human-readable message */
  message: string;
}

// ─── Backend raw responses (snake_case) ──────────────────────────────

/** Raw pool state from backend */
interface RawPoolStateResponse {
  bankroll: string;
  bankroll_erg: string;
  total_supply: string;
  total_value: string;
  total_value_erg: string;
  price_per_share: string;
  price_per_share_erg: string;
  house_edge_bps: number;
  cooldown_blocks: number;
  cooldown_hours: number;
  pending_bets: number;
}

/** Raw APY from backend */
interface RawAPYResponse {
  apy_percent: number;
  house_edge_bps: number;
  avg_bet_size_erg: string;
  bets_per_block: number;
  estimated_daily_profit_erg: string;
  estimated_monthly_profit_erg: string;
  estimated_yearly_profit_erg: string;
}

/** Raw balance from backend */
interface RawLPBalanceResponse {
  address: string;
  lp_balance: string;
  erg_value: string;
  share_percent: number;
}

/** Raw estimate from backend */
interface RawEstimateResponse {
  shares: string;
  erg_amount: string;
  price_per_share: string;
  new_total_value: string;
}

/** Raw tx from backend */
interface RawTxResponse {
  tx_id: string | null;
  tx_json: Record<string, unknown>;
  message: string;
}

// ─── Transformer helpers ─────────────────────────────────────────────

/** Convert backend snake_case pool state to frontend camelCase */
export function transformPoolState(raw: RawPoolStateResponse): PoolStateResponse {
  return {
    bankroll: raw.bankroll,
    bankrollErg: raw.bankroll_erg,
    totalSupply: raw.total_supply,
    totalValue: raw.total_value,
    totalValueErg: raw.total_value_erg,
    pricePerShare: raw.price_per_share,
    pricePerShareErg: raw.price_per_share_erg,
    houseEdgeBps: raw.house_edge_bps,
    cooldownBlocks: raw.cooldown_blocks,
    cooldownHours: raw.cooldown_hours,
    pendingBets: raw.pending_bets,
  };
}

/** Convert backend snake_case APY to frontend camelCase */
export function transformAPY(raw: RawAPYResponse): APYResponse {
  return {
    apyPercent: raw.apy_percent,
    houseEdgeBps: raw.house_edge_bps,
    avgBetSizeErg: raw.avg_bet_size_erg,
    betsPerBlock: raw.bets_per_block,
    estimatedDailyProfitErg: raw.estimated_daily_profit_erg,
    estimatedMonthlyProfitErg: raw.estimated_monthly_profit_erg,
    estimatedYearlyProfitErg: raw.estimated_yearly_profit_erg,
  };
}

/** Convert backend snake_case balance to frontend camelCase */
export function transformBalance(raw: RawLPBalanceResponse): LPBalanceResponse {
  return {
    address: raw.address,
    lpBalance: raw.lp_balance,
    ergValue: raw.erg_value,
    sharePercent: raw.share_percent,
  };
}

/** Convert backend snake_case estimate to frontend camelCase */
export function transformEstimate(raw: RawEstimateResponse): EstimateResponse {
  return {
    shares: raw.shares,
    ergAmount: raw.erg_amount,
    pricePerShare: raw.price_per_share,
    newTotalValue: raw.new_total_value,
  };
}

/** Convert backend snake_case tx response to frontend camelCase */
export function transformTx(raw: RawTxResponse): TxResponse {
  return {
    txId: raw.tx_id,
    txJson: raw.tx_json,
    message: raw.message,
  };
}
