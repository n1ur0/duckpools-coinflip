/**
 * DuckPools — Bankroll Store (Zustand)
 *
 * Real-time bankroll state: TVL, profit, utilization, LP data.
 * Thin store — data hydration comes from API hooks.
 */

import { create } from 'zustand';
import type {
  BankrollOverview,
  TvlSnapshot,
  ProfitSnapshot,
  UtilizationSnapshot,
  LpPoolSummary,
  GlobalBetRecord,
  LpProviderStats,
  TvlHistoryPoint,
  ProfitHistoryPoint,
} from '../types/Bankroll';

// ─── State ───────────────────────────────────────────────────

export interface BankrollState {
  /** Current overview (latest snapshot of everything) */
  overview: BankrollOverview | null;
  /** Individual pieces for granular updates */
  tvl: TvlSnapshot | null;
  profit: ProfitSnapshot | null;
  utilization: UtilizationSnapshot | null;
  lpSummary: LpPoolSummary | null;

  /** Historical data for charts */
  tvlHistory: TvlHistoryPoint[];
  profitHistory: ProfitHistoryPoint[];

  /** Global bet feed (recent bets across all players) */
  globalBets: GlobalBetRecord[];

  /** Connected wallet's LP stats (null if not an LP) */
  myLpStats: LpProviderStats | null;

  /** Loading states */
  isLoadingOverview: boolean;
  isLoadingBets: boolean;
  isLoadingLpStats: boolean;
  lastPollAt: number | null;

  // ── Actions ──
  setOverview: (data: BankrollOverview) => void;
  setTvl: (data: TvlSnapshot) => void;
  setProfit: (data: ProfitSnapshot) => void;
  setUtilization: (data: UtilizationSnapshot) => void;
  setLpSummary: (data: LpPoolSummary) => void;
  setTvlHistory: (data: TvlHistoryPoint[]) => void;
  setProfitHistory: (data: ProfitHistoryPoint[]) => void;
  appendGlobalBet: (bet: GlobalBetRecord) => void;
  setGlobalBets: (bets: GlobalBetRecord[]) => void;
  setMyLpStats: (data: LpProviderStats | null) => void;
  setLoading: (key: 'overview' | 'bets' | 'lpStats', value: boolean) => void;
  setLastPollAt: (ts: number) => void;
  reset: () => void;
}

// ─── Initial ─────────────────────────────────────────────────

const initialState = {
  overview: null,
  tvl: null,
  profit: null,
  utilization: null,
  lpSummary: null,
  tvlHistory: [],
  profitHistory: [],
  globalBets: [],
  myLpStats: null,
  isLoadingOverview: false,
  isLoadingBets: false,
  isLoadingLpStats: false,
  lastPollAt: null,
};

// ─── Store ───────────────────────────────────────────────────

export const useBankrollStore = create<BankrollState>()((set) => ({
  ...initialState,

  setOverview: (data) => set({
    overview: data,
    tvl: data.tvl,
    profit: data.profit,
    utilization: data.utilization,
    lpSummary: data.lpSummary,
  }),

  setTvl: (data) => set({ tvl: data }),
  setProfit: (data) => set({ profit: data }),
  setUtilization: (data) => set({ utilization: data }),
  setLpSummary: (data) => set({ lpSummary: data }),
  setTvlHistory: (data) => set({ tvlHistory: data }),
  setProfitHistory: (data) => set({ profitHistory: data }),

  appendGlobalBet: (bet) =>
    set((state) => ({
      globalBets: [bet, ...state.globalBets].slice(0, 100),
    })),

  setGlobalBets: (bets) => set({ globalBets: bets }),
  setMyLpStats: (data) => set({ myLpStats: data }),

  setLoading: (key, value) =>
    set({ [`isLoading${key.charAt(0).toUpperCase() + key.slice(1)}`]: value }),

  setLastPollAt: (ts) => set({ lastPollAt: ts }),

  reset: () => set(initialState),
}));
