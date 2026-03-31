/**
 * useBankrollPoller — Polls bankroll API endpoints at a configurable interval.
 *
 * Returns nothing; hydrates useBankrollStore via actions.
 * Auto-starts on mount, stops on unmount.
 */

import { useEffect, useRef, useCallback } from 'react';
import { useWallet } from '../contexts/WalletContext';
import { buildApiUrl } from '../utils/network';
import { useBankrollStore } from '../stores/bankrollStore';
import type {
  BankrollOverview,
  GlobalBetRecord,
  LpProviderStats,
  BankrollHistoryResponse,
} from '../types/Bankroll';

const POLL_INTERVAL = 15_000; // 15s

export function useBankrollPoller(interval: number = POLL_INTERVAL) {
  const { walletAddress } = useWallet();
  const {
    setOverview,
    setGlobalBets,
    setMyLpStats,
    setTvlHistory,
    setProfitHistory,
    setLoading,
    setLastPollAt,
  } = useBankrollStore();

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchOverview = useCallback(async () => {
    try {
      const res = await fetch(buildApiUrl('/bankroll/overview'));
      if (!res.ok) return;
      const data: BankrollOverview = await res.json();
      setOverview(data);
    } catch {
      // Silent — store retains last known good data
    }
  }, [setOverview]);

  const fetchGlobalBets = useCallback(async () => {
    try {
      const res = await fetch(buildApiUrl('/bankroll/bets?limit=50'));
      if (!res.ok) return;
      const data: GlobalBetRecord[] = await res.json();
      setGlobalBets(data);
    } catch {
      // Silent
    }
  }, [setGlobalBets]);

  const fetchLpStats = useCallback(async (addr: string) => {
    try {
      const res = await fetch(buildApiUrl(`/bankroll/lp/${addr}`));
      if (!res.ok) {
        setMyLpStats(null);
        return;
      }
      const data: LpProviderStats = await res.json();
      setMyLpStats(data);
    } catch {
      setMyLpStats(null);
    }
  }, [setMyLpStats]);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(buildApiUrl('/bankroll/history?granularity=hourly&hours=24'));
      if (!res.ok) return;
      const data: BankrollHistoryResponse = await res.json();
      setTvlHistory(data.tvl);
      setProfitHistory(data.profit);
    } catch {
      // Silent
    }
  }, [setTvlHistory, setProfitHistory]);

  const pollAll = useCallback(() => {
    setLoading('overview', true);
    setLoading('bets', true);

    Promise.all([
      fetchOverview(),
      fetchGlobalBets(),
      fetchHistory(),
    ]).finally(() => {
      setLoading('overview', false);
      setLoading('bets', false);
      setLastPollAt(Date.now());
    });

    if (walletAddress) {
      setLoading('lpStats', true);
      fetchLpStats(walletAddress).finally(() => setLoading('lpStats', false));
    }
  }, [fetchOverview, fetchGlobalBets, fetchHistory, fetchLpStats, walletAddress, setLoading, setLastPollAt]);

  useEffect(() => {
    // Initial fetch
    pollAll();

    // Polling interval
    intervalRef.current = setInterval(pollAll, interval);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [pollAll, interval]);
}

/**
 * Hook to subscribe to a hypothetical WebSocket for live bet feed.
 * Falls back gracefully — if no WS available, polling handles it.
 */
export function useBankrollWebSocket() {
  const appendGlobalBet = useBankrollStore((s) => s.appendGlobalBet);

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_BANKROLL_WS_URL;
    if (!wsUrl) return;

    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
          try {
            const bet: GlobalBetRecord = JSON.parse(event.data);
            appendGlobalBet(bet);
          } catch {
            // Ignore malformed messages
          }
        };

        ws.onclose = () => {
          // Reconnect after 5s
          reconnectTimeout = setTimeout(connect, 5000);
        };

        ws.onerror = () => {
          ws?.close();
        };
      } catch {
        reconnectTimeout = setTimeout(connect, 10000);
      }
    };

    connect();

    return () => {
      ws?.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [appendGlobalBet]);
}
