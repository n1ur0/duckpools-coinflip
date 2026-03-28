// ─── Game Type ─────────────────────────────────────────────────

export type GameType = 'coinflip';

// ─── Player's Bet Choice ─────────────────────────────────────

export interface CoinflipChoice {
  gameType: 'coinflip';
  side: 'heads' | 'tails';
}

export type GameChoice = CoinflipChoice;

// ─── Actual Outcome ──────────────────────────────────────────

export interface CoinflipOutcome {
  gameType: 'coinflip';
  result: 'heads' | 'tails';
}

export type GameOutcome = CoinflipOutcome;

// ─── Bet Record ──────────────────────────────────────────────

export interface BetRecord {
  betId: string;
  txId: string;
  boxId: string;
  playerAddress: string;
  gameType: GameType;
  choice: GameChoice;
  betAmount: string;       // nanoERG
  outcome: 'pending' | 'win' | 'loss' | 'refunded';
  actualOutcome: GameOutcome | null;
  payout: string;          // nanoERG
  payoutMultiplier: number; // e.g. 1.94 for coinflip
  timestamp: string;       // ISO 8601
  blockHeight: number;
  resolvedAtHeight: number | null;
}

// ─── Legacy compat (DO NOT use in new code) ───────────────────
// @deprecated Use GameChoice discriminated union instead

/** @deprecated Use CoinflipChoice */
export interface BetChoice {
  value: number;    // 0 = Heads, 1 = Tails
  label: string;    // "Heads" or "Tails"
}

// ─── Helpers ──────────────────────────────────────────────────

/** Format a player's choice as a human-readable label. */
export function formatChoiceLabel(choice: GameChoice): string {
  return choice.side.charAt(0).toUpperCase() + choice.side.slice(1);
}

/** Format an outcome as a human-readable label. */
export function formatOutcomeLabel(outcome: GameOutcome | null): string {
  if (!outcome) return '—';
  return outcome.result.charAt(0).toUpperCase() + outcome.result.slice(1);
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
}

export interface LeaderboardEntry {
  rank: number;
  address: string;
  totalBets: number;
  netPnL: string;
  winRate: number;
}

export interface LeaderboardResponse {
  players: LeaderboardEntry[];
  totalPlayers: number;
  sortBy: string;
}
