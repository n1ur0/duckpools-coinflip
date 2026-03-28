/**
 * DuckPools — Preferences Store (Zustand + persist)
 *
 * User settings persisted to localStorage. Survives page reloads.
 *
 * ARCH-2: Zustand stores for game state, bets, and user preferences
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ─── Types ─────────────────────────────────────────────────────

export type RiskLevel = 'low' | 'medium' | 'high';
export type CurrencyDisplay = 'ERG' | 'USD';

export interface PreferencesState {
  /** Default bet amount when opening a game */
  quickBetAmount: number;
  /** Risk profile for dice game default target */
  defaultRiskLevel: RiskLevel;
  /** Enable/disable animations (respect prefers-reduced-motion) */
  showAnimations: boolean;
  /** Currency display mode */
  currency: CurrencyDisplay;
  /** Whether to show bet result sound effects */
  soundEnabled: boolean;
  /** Compact vs full bet history display */
  compactHistory: boolean;

  // ── Actions ──
  setQuickBetAmount: (amount: number) => void;
  setDefaultRiskLevel: (level: RiskLevel) => void;
  setShowAnimations: (show: boolean) => void;
  setCurrency: (currency: CurrencyDisplay) => void;
  setSoundEnabled: (enabled: boolean) => void;
  setCompactHistory: (compact: boolean) => void;
  /** Reset all preferences to defaults */
  resetPreferences: () => void;
}

// ─── Defaults ──────────────────────────────────────────────────

const DEFAULTS = {
  quickBetAmount: 0.1,
  defaultRiskLevel: 'medium' as RiskLevel,
  showAnimations: true,
  currency: 'ERG' as CurrencyDisplay,
  soundEnabled: true,
  compactHistory: false,
};

// ─── Store ─────────────────────────────────────────────────────

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      ...DEFAULTS,

      setQuickBetAmount: (amount: number) =>
        set({ quickBetAmount: Math.max(0.01, Math.min(1000, amount)) }),

      setDefaultRiskLevel: (level: RiskLevel) =>
        set({ defaultRiskLevel: level }),

      setShowAnimations: (show: boolean) =>
        set({ showAnimations: show }),

      setCurrency: (currency: CurrencyDisplay) =>
        set({ currency: currency }),

      setSoundEnabled: (enabled: boolean) =>
        set({ soundEnabled: enabled }),

      setCompactHistory: (compact: boolean) =>
        set({ compactHistory: compact }),

      resetPreferences: () => set(DEFAULTS),
    }),
    {
      name: 'duckpools-preferences',
      // Only persist data fields (exclude action functions)
      partialize: (state) => ({
        quickBetAmount: state.quickBetAmount,
        defaultRiskLevel: state.defaultRiskLevel,
        showAnimations: state.showAnimations,
        currency: state.currency,
        soundEnabled: state.soundEnabled,
        compactHistory: state.compactHistory,
      }),
    }
  )
);
