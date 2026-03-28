export type GameType = 'coinflip' | 'dice' | 'plinko' | 'crash';

export interface BetChoice {
  value: number;    // 0 = Heads, 1 = Tails
  label: string;    // "Heads" or "Tails"
}

export interface BetRecord {
  betId: string;
  txId: string;
  boxId: string;
  playerAddress: string;
  choice: BetChoice;
  betAmount: string;       // nanoERG
  outcome: 'pending' | 'win' | 'loss' | 'refunded';
  actualOutcome: number | null;  // 0 or 1
  payout: string;          // nanoERG
  timestamp: string;       // ISO 8601
  blockHeight: number;
  resolvedAtHeight: number | null;
}

export interface PoolState {
  liquidity: string;       // nanoERG
  totalBets: number;
  playerWins: number;
  houseWins: number;
  totalFees: string;       // nanoERG
  houseEdge: number;       // e.g. 0.03
}

export interface PlayerStats {
  address: string;
  totalBets: number;
  wins: number;
  losses: number;
  pending: number;
  winRate: number;
  totalWagered: string;
  totalWon: string;
  totalLost: string;
  netPnL: string;
  biggestWin: string;
  currentStreak: number;
  longestWinStreak: number;
  longestLossStreak: number;
  compPoints: number;
  compTier: string;
}

export interface LeaderboardEntry {
  rank: number;
  address: string;
  totalBets: number;
  netPnL: string;
  winRate: number;
  compPoints: number;
  compTier: string;
}

export interface LeaderboardResponse {
  leaderboard: LeaderboardEntry[];
  total: number;
}

export interface CompPoints {
  address: string;
  points: number;
  tier: string;
  tierProgress: number;
  nextTier: string;
  pointsToNextTier: number;
  totalEarned: number;
  benefits: string[];
}
