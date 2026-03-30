/**
 * useBankrollStatus — Fetches bankroll status from the backend
 * and exposes max bet cap for the coinflip game.
 *
 * Backend endpoint: GET /bankroll/status
 * Returns: { balance, exposure, capacity, maxBet }
 *   - maxBet: maximum single bet amount in nanoERG
 *
 * Falls back to a sensible default if the endpoint is unavailable.
 */

import { useState, useEffect, useCallback } from 'react';
import { buildApiUrl } from '../utils/network';

export interface BankrollStatus {
  /** Total bankroll balance in nanoERG */
  balance: string;
  /** Current exposure (open bets) in nanoERG */
  exposure: string;
  /** Available capacity in nanoERG */
  capacity: string;
  /** Maximum single bet in nanoERG */
  maxBet: string;
}

/** Default max bet: 10 ERG in nanoERG */
const DEFAULT_MAX_BET_NANOERG = '10000000000';

const FETCH_INTERVAL = 60_000; // 1 minute

export function useBankrollStatus() {
  const [status, setStatus] = useState<BankrollStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(buildApiUrl('/bankroll/status'));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data: BankrollStatus = await res.json();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch bankroll');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, FETCH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  /** Max bet in nanoERG — falls back to default if unavailable */
  const maxBetNanoErg = status?.maxBet || DEFAULT_MAX_BET_NANOERG;

  /** Max bet in ERG (for display) */
  const maxBetErg = Number(maxBetNanoErg) / 1e9;

  return {
    status,
    maxBetNanoErg,
    maxBetErg,
    loading,
    error,
    refetch: fetchStatus,
  };
}
