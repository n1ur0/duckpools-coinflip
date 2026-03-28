/**
 * DuckPools — Store unit tests
 *
 * ARCH-2: Zustand stores for bets and user preferences
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useBetStore } from '../betStore';
import { usePreferencesStore } from '../preferencesStore';
import type { PendingBet } from '../betStore';

// ─── Bet Store ─────────────────────────────────────────────────

describe('useBetStore', () => {
  const mockPending: PendingBet = {
    betId: 'test-bet-001',
    txId: 'test-tx-001',
    gameType: 'coinflip',
    amount: '1.0',
    amountNanoErg: '1000000000',
    choiceLabel: 'Heads',
    submittedAt: Date.now(),
  };

  beforeEach(() => {
    useBetStore.setState({
      pendingBets: new Map(),
      recentResults: [],
      isSubmitting: false,
      submissionError: null,
    });
  });

  it('has correct defaults', () => {
    const state = useBetStore.getState();
    expect(state.pendingBets.size).toBe(0);
    expect(state.recentResults).toEqual([]);
    expect(state.isSubmitting).toBe(false);
    expect(state.submissionError).toBeNull();
  });

  it('addPendingBet adds to the map', () => {
    useBetStore.getState().addPendingBet(mockPending);
    const state = useBetStore.getState();
    expect(state.pendingBets.size).toBe(1);
    expect(state.pendingBets.get('test-bet-001')).toEqual(mockPending);
  });

  it('resolvePendingBet removes from pending and adds to recent', () => {
    useBetStore.getState().addPendingBet(mockPending);

    const record = {
      betId: 'test-bet-001',
      txId: 'test-tx-001',
      boxId: 'box-001',
      playerAddress: 'addr',
      gameType: 'coinflip' as const,
      choice: { gameType: 'coinflip' as const, side: 'heads' as const },
      betAmount: '1000000000',
      outcome: 'win' as const,
      actualOutcome: { gameType: 'coinflip' as const, result: 'heads' as const },
      payout: '970000000',
      payoutMultiplier: 0.97,
      timestamp: new Date().toISOString(),
      blockHeight: 100,
      resolvedAtHeight: 102,
    };

    useBetStore.getState().resolvePendingBet('test-bet-001', record);
    const state = useBetStore.getState();
    expect(state.pendingBets.size).toBe(0);
    expect(state.recentResults).toHaveLength(1);
    expect(state.recentResults[0].betId).toBe('test-bet-001');
  });

  it('failPendingBet removes from pending and sets error', () => {
    useBetStore.getState().addPendingBet(mockPending);
    useBetStore.getState().failPendingBet('test-bet-001', 'timeout');
    const state = useBetStore.getState();
    expect(state.pendingBets.size).toBe(0);
    expect(state.submissionError).toContain('timeout');
  });

  it('setSubmitting toggles submission state', () => {
    useBetStore.getState().setSubmitting(true);
    expect(useBetStore.getState().isSubmitting).toBe(true);
    useBetStore.getState().setSubmitting(false);
    expect(useBetStore.getState().isSubmitting).toBe(false);
  });

  it('clearSubmissionError clears the error', () => {
    useBetStore.setState({ submissionError: 'some error' });
    useBetStore.getState().clearSubmissionError();
    expect(useBetStore.getState().submissionError).toBeNull();
  });

  it('trimRecentResults caps the array', () => {
    // Add 60 results
    for (let i = 0; i < 60; i++) {
      useBetStore.setState({
        recentResults: [
          ...useBetStore.getState().recentResults,
          {
            betId: `bet-${i}`,
            txId: `tx-${i}`,
            boxId: `box-${i}`,
            playerAddress: 'addr',
            gameType: 'coinflip' as const,
            choice: { gameType: 'coinflip' as const, side: 'heads' as const },
            betAmount: '1000000000',
            outcome: 'win' as const,
            actualOutcome: { gameType: 'coinflip' as const, result: 'heads' as const },
            payout: '970000000',
            payoutMultiplier: 0.97,
            timestamp: new Date().toISOString(),
            blockHeight: 100,
            resolvedAtHeight: 102,
          },
        ],
      });
    }
    expect(useBetStore.getState().recentResults).toHaveLength(60);
    useBetStore.getState().trimRecentResults(10);
    expect(useBetStore.getState().recentResults).toHaveLength(10);
  });
});

// ─── Preferences Store ─────────────────────────────────────────

describe('usePreferencesStore', () => {
  beforeEach(() => {
    // Reset to defaults (including localStorage side-effect from persist)
    usePreferencesStore.getState().resetPreferences();
  });

  it('has correct defaults', () => {
    const state = usePreferencesStore.getState();
    expect(state.quickBetAmount).toBe(0.1);
    expect(state.defaultRiskLevel).toBe('medium');
    expect(state.showAnimations).toBe(true);
    expect(state.currency).toBe('ERG');
    expect(state.soundEnabled).toBe(true);
    expect(state.compactHistory).toBe(false);
  });

  it('setQuickBetAmount clamps to valid range', () => {
    usePreferencesStore.getState().setQuickBetAmount(0.001);
    expect(usePreferencesStore.getState().quickBetAmount).toBe(0.01);

    usePreferencesStore.getState().setQuickBetAmount(5000);
    expect(usePreferencesStore.getState().quickBetAmount).toBe(1000);

    usePreferencesStore.getState().setQuickBetAmount(5);
    expect(usePreferencesStore.getState().quickBetAmount).toBe(5);
  });

  it('setCurrency changes display currency', () => {
    usePreferencesStore.getState().setCurrency('USD');
    expect(usePreferencesStore.getState().currency).toBe('USD');
  });

  it('resetPreferences restores all defaults', () => {
    usePreferencesStore.getState().setQuickBetAmount(10);
    usePreferencesStore.getState().setCurrency('USD');
    usePreferencesStore.getState().setSoundEnabled(false);
    usePreferencesStore.getState().resetPreferences();
    const state = usePreferencesStore.getState();
    expect(state.quickBetAmount).toBe(0.1);
    expect(state.currency).toBe('ERG');
    expect(state.soundEnabled).toBe(true);
  });
});
