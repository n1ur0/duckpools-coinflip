/**
 * DuckPools — Game Store (Zustand)
 *
 * Central store for game-specific settings.
 * Single game (coinflip) — no game switching needed.
 *
 * ARCH-2: Zustand stores for game state, bets, and user preferences
 */

import { create } from 'zustand';

// ─── Types ─────────────────────────────────────────────────────

export interface GameState {
  // Coinflip-specific settings can go here if needed
  // Currently minimal since coinflip has no config beyond heads/tails
}

// ─── Store ─────────────────────────────────────────────────────

export const useGameStore = create<GameState>()(() => ({}));
