import { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw } from 'lucide-react';
import { useWallet } from '../contexts/WalletContext';
import { buildApiUrl } from '../utils/network';
import { formatErg } from '../utils/ergo';
import type { BetRecord } from '../types/Game';
import { formatChoiceLabel } from '../types/Game';
import './GameHistory.css';

const REFRESH_INTERVAL = 30_000;

function getExplorerTxUrl(txId: string): string {
  return `https://explorer.ergoplatform.com/en/transactions/${txId}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export default function GameHistory() {
  const { isConnected, walletAddress } = useWallet();

  const [bets, setBets] = useState<BetRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHistory = useCallback(async (showSpinner = true) => {
    if (!walletAddress) return;

    if (showSpinner) setLoading(true);
    else setRefreshing(true);
    setError(null);

    try {
      const res = await fetch(buildApiUrl(`/history/${walletAddress}`));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data: BetRecord[] = await res.json();
      setBets(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load history'
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [walletAddress]);

  // Initial fetch + auto-refresh
  useEffect(() => {
    if (!isConnected || !walletAddress) {
      setBets([]);
      return;
    }

    fetchHistory();
    intervalRef.current = setInterval(() => fetchHistory(false), REFRESH_INTERVAL);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isConnected, walletAddress, fetchHistory]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className="gh-container">
        <p className="gh-connect">Connect your wallet to view bet history</p>
      </div>
    );
  }

  return (
    <div className="gh-container">
      <div className="gh-title">
        <span>Bet History</span>
        <button
          className={`gh-refresh-btn${refreshing ? ' gh-refresh-btn--spinning' : ''}`}
          onClick={() => fetchHistory(false)}
          disabled={refreshing}
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {error && <div className="gh-error">{error}</div>}

      {loading ? (
        <div className="gh-skeleton">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="gh-skeleton-row">
              <div className="gh-skeleton-cell" style={{ width: 100 }} />
              <div className="gh-skeleton-cell" style={{ width: 60 }} />
              <div className="gh-skeleton-cell" style={{ width: 70 }} />
              <div className="gh-skeleton-cell" style={{ width: 60 }} />
              <div className="gh-skeleton-cell" style={{ width: 90 }} />
            </div>
          ))}
        </div>
      ) : bets.length === 0 ? (
        <div className="gh-empty">No bets yet. Place your first flip!</div>
      ) : (
        <div className="gh-table-wrap">
          <table className="gh-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Choice</th>
                <th>Amount</th>
                <th>Outcome</th>
                <th>Payout</th>
                <th>TX</th>
              </tr>
            </thead>
            <tbody>
              {bets.map((bet) => (
                <tr key={bet.betId}>
                  <td className="gh-date">{formatDate(bet.timestamp)}</td>
                  <td>
                    <span className={`gh-choice-badge gh-choice-badge--${bet.gameType}`}>
                      {formatChoiceLabel(bet.choice)}
                    </span>
                  </td>
                  <td className="gh-mono">{formatErg(bet.betAmount)} ERG</td>
                  <td>
                    <span className={`gh-outcome gh-outcome--${bet.outcome}`}>
                      {bet.outcome}
                    </span>
                  </td>
                  <td className="gh-mono">
                    {bet.payout && bet.payout !== '0'
                      ? `${formatErg(bet.payout)} ERG`
                      : '—'}
                  </td>
                  <td>
                    <a
                      className="gh-tx-link"
                      href={getExplorerTxUrl(bet.txId)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {bet.txId.slice(0, 10)}...
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
