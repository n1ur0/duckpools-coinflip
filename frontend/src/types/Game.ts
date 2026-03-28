// ─── Game Type ─────────────────────────────────────────────────

export type GameType = 'coinflip' | 'dice' | 'plinko';

// ─── Discriminated Union: Player's Bet Choice ─────────────────
// Use `gameType` discriminant for type narrowing:
//   if (bet.choice.gameType === 'dice') { /* TS knows rollTarget exists */ }

export interface CoinflipChoice {
  gameType: 'coinflip';
  side: 'heads' | 'tails';
}

export interface DiceChoice {
  gameType: 'dice';
  rollTarget: number;   // 2-98 (win if rngValue < rollTarget)
}

export interface PlinkoChoice {
  gameType: 'plinko';
  rows: number;         // 8-16
}

export type GameChoice = CoinflipChoice | DiceChoice | PlinkoChoice;

// ─── Discriminated Union: Actual Outcome ──────────────────────

export interface CoinflipOutcome {
  gameType: 'coinflip';
  result: 'heads' | 'tails';
}

export interface DiceOutcome {
  gameType: 'dice';
  rngValue: number;     // 0-99
}

export interface PlinkoOutcome {
  gameType: 'plinko';
  slot: number;         // 0 to rows
  multiplier: number;   // payout multiplier for that slot
}

export type GameOutcome = CoinflipOutcome | DiceOutcome | PlinkoOutcome;

// ─── Bet Record (multi-game) ──────────────────────────────────

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
  payoutMultiplier: number; // e.g. 1.94 for coinflip, variable for dice/plinko
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
  switch (choice.gameType) {
    case 'coinflip':
      return choice.side.charAt(0).toUpperCase() + choice.side.slice(1);
    case 'dice':
      return `Roll under ${choice.rollTarget}`;
    case 'plinko':
      return `${choice.rows} rows`;
  }
}

/** Format an outcome as a human-readable label. */
export function formatOutcomeLabel(outcome: GameOutcome | null): string {
  if (!outcome) return '—';
  switch (outcome.gameType) {
    case 'coinflip':
      return outcome.result.charAt(0).toUpperCase() + outcome.result.slice(1);
    case 'dice':
      return `Rolled ${outcome.rngValue}`;
    case 'plinko':
      return `Slot ${outcome.slot} (${outcome.multiplier}x)`;
  }
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
  players: LeaderboardEntry[];
  totalPlayers: number;
  sortBy: string;
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
