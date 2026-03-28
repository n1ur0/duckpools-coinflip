/**
 * DuckPools — Bet Store (Zustand)
 *
 * Tracks active/pending bets and recent results across all games.
 * Thin store — business logic stays in utils/ and services/.
 *
 * ARCH-2: Zustand stores for game state, bets, and user preferences
 */

import { create } from 'zustand';
import type { BetRecord, GameType } from '../types/Game';

// ─── Types ─────────────────────────────────────────────────────

export interface PendingBet {
  betId: string;
  txId: string;
  gameType: GameType;
  amount: string;       // ERG display string
  amountNanoErg: string; // nanoERG
  choiceLabel: string;
  submittedAt: number;   // Date.now()
}

export interface BetState {
  /** Bets waiting for on-chain confirmation */
  pendingBets: Map<string, PendingBet>;
  /** Most recent resolved bets (across all games) */
  recentResults: BetRecord[];
  /** True while a bet submission is in-flight */
  isSubmitting: boolean;
  /** Last submission error (null if none) */
  submissionError: string | null;

  // ── Actions ──
  addPendingBet: (bet: PendingBet) => void;
  resolvePendingBet: (betId: string, record: BetRecord) => void;
  failPendingBet: (betId: string, reason: string) => void;
  setSubmitting: (value: boolean) => void;
  setSubmissionError: (error: string | null) => void;
  clearSubmissionError: () => void;
  /** Trim recentResults to keep only the last N entries */
  trimRecentResults: (maxCount?: number) => void;
}

// ─── Constants ─────────────────────────────────────────────────

const DEFAULT_MAX_RESULTS = 50;

// ─── Store ─────────────────────────────────────────────────────

export const useBetStore = create<BetState>()((set) => ({
  pendingBets: new Map(),
  recentResults: [],
  isSubmitting: false,
  submissionError: null,

  addPendingBet: (bet) =>
    set((state) => {
      const next = new Map(state.pendingBets);
      next.set(bet.betId, bet);
      return { pendingBets: next };
    }),

  resolvePendingBet: (betId, record) =>
    set((state) => {
      const pending = new Map(state.pendingBets);
      pending.delete(betId);
      return {
        pendingBets: pending,
        recentResults: [record, ...state.recentResults],
      };
    }),

  failPendingBet: (betId, reason) =>
    set((state) => {
      const pending = new Map(state.pendingBets);
      pending.delete(betId);
      return {
        pendingBets: pending,
        submissionError: `Bet ${betId.slice(0, 8)}... failed: ${reason}`,
      };
    }),

  setSubmitting: (value) => set({ isSubmitting: value }),

  setSubmissionError: (error) => set({ submissionError: error }),

  clearSubmissionError: () => set({ submissionError: null }),

  trimRecentResults: (maxCount = DEFAULT_MAX_RESULTS) =>
    set((state) => ({
      recentResults: state.recentResults.slice(0, maxCount),
    })),
}));
