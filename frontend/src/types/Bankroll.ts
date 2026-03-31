// ─── Bankroll Dashboard Types ─────────────────────────────────

// ── TVL ──────────────────────────────────────────────────────

export interface TvlSnapshot {
  totalErg: string;       // nanoERG — total ERG in bankroll pool
  totalUsd: string;       // approximate USD value
  timestamp: string;      // ISO 8601
}

export interface TvlHistoryPoint {
  timestamp: string;      // ISO 8601
  totalErg: string;       // nanoERG
  totalUsd: string;       // approximate USD value
}

// ── House Profit ─────────────────────────────────────────────

export interface ProfitSnapshot {
  cumulativeProfitErg: string;   // nanoERG — can be negative
  cumulativeProfitUsd: string;
  dailyProfitErg: string;        // profit for last 24h
  dailyProfitUsd: string;
  timestamp: string;
}

export interface ProfitHistoryPoint {
  timestamp: string;
  cumulativeProfitErg: string;
  dailyProfitErg: string;
}

// ── Utilization ──────────────────────────────────────────────

export interface UtilizationSnapshot {
  totalBankrollErg: string;      // nanoERG — total pool
  committedErg: string;          // nanoERG — locked in active bets
  availableErg: string;          // nanoERG — free to accept bets
  utilizationPct: number;        // 0–100
  activeBetsCount: number;
  timestamp: string;
}

// ── Bet History (global, not per-player) ─────────────────────

export interface GlobalBetRecord {
  betId: string;
  txId: string;
  playerAddress: string;
  gameType: string;
  betAmount: string;             // nanoERG
  payout: string;                // nanoERG
  outcome: 'pending' | 'win' | 'loss' | 'refunded';
  houseEdge: string;             // nanoERG — house cut on this bet
  timestamp: string;
  blockHeight: number;
}

// ── LP (Liquidity Provider) Stats ────────────────────────────

export interface LpProviderStats {
  providerAddress: string;
  depositedErg: string;          // nanoERG — total deposited
  currentShares: string;         // LP token balance
  depositedUsd: string;          // approximate at deposit time
  currentValueErg: string;       // nanoERG — current value of shares
  currentValueUsd: string;
  totalReturnErg: string;        // nanoERG — profit from fees
  totalReturnUsd: string;
  apy: number;                   // annualized percentage yield
  depositCount: number;
  firstDepositAt: string;
  lastDepositAt: string;
}

export interface LpPoolSummary {
  totalProviders: number;
  totalDepositedErg: string;
  totalDepositedUsd: string;
  avgApy: number;
  bestApy: number;
  totalDistributedErg: string;   // total fees paid to LPs
  timestamp: string;
}

// ── Combined bankroll overview ───────────────────────────────

export interface BankrollOverview {
  tvl: TvlSnapshot;
  profit: ProfitSnapshot;
  utilization: UtilizationSnapshot;
  lpSummary: LpPoolSummary;
}

// ── API response shapes ──────────────────────────────────────

export interface BankrollHistoryResponse {
  tvl: TvlHistoryPoint[];
  profit: ProfitHistoryPoint[];
  granularity: 'hourly' | 'daily';
  from: string;
  to: string;
}
