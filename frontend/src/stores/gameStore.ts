/**
 * DuckPools — Game Store (Zustand)
 *
 * Central store for active game selection and game-specific settings.
 * Replaces the `activeGame` useState that was prop-drilled through App → GameNav.
 *
 * ARCH-2: Zustand stores for game state, bets, and user preferences
 */

import { create } from 'zustand';
import type { GameType } from '../types/Game';

// ─── Types ─────────────────────────────────────────────────────

export interface GameState {
  /** Currently selected game tab */
  activeGame: GameType;
  /** Plinko configuration (only used when activeGame === 'plinko') */
  plinkoRows: number;
  /** Dice roll target (only used when activeGame === 'dice') */
  diceTarget: number;

  // ── Actions ──
  setActiveGame: (game: GameType) => void;
  setPlinkoRows: (rows: number) => void;
  setDiceTarget: (target: number) => void;
}

// ─── Constants ─────────────────────────────────────────────────

const PLINKO_ROWS_MIN = 8;
const PLINKO_ROWS_MAX = 16;
const DICE_TARGET_MIN = 2;
const DICE_TARGET_MAX = 98;

// ─── Store ─────────────────────────────────────────────────────

export const useGameStore = create<GameState>()((set) => ({
  activeGame: 'coinflip' as GameType,
  plinkoRows: 12,
  diceTarget: 50,

  setActiveGame: (game) => set({ activeGame: game }),

  setPlinkoRows: (rows) =>
    set({
      plinkoRows: Math.max(PLINKO_ROWS_MIN, Math.min(PLINKO_ROWS_MAX, rows)),
    }),

  setDiceTarget: (target) =>
    set({
      diceTarget: Math.max(DICE_TARGET_MIN, Math.min(DICE_TARGET_MAX, target)),
    }),
}));
