import { useState, useEffect, useCallback } from 'react';
import { buildApiUrl } from '../utils/network';
import { formatErg, formatAddress } from '../utils/ergo';
import type { LeaderboardEntry, LeaderboardResponse } from '../types/Game';
import './Leaderboard.css';

function getExplorerAddressUrl(address: string): string {
  return `https://explorer.ergoplatform.com/en/addresses/${address}`;
}

export default function Leaderboard() {
  const [data, setData] = useState<LeaderboardEntry[]>([]);
  const [totalPlayers, setTotalPlayers] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLeaderboard = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(buildApiUrl('/leaderboard'));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const json: LeaderboardResponse = await res.json();
      setData(json.players);
      setTotalPlayers(json.totalPlayers);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load leaderboard'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLeaderboard();

    // Listen for bet placement events to refresh immediately
    const handleBetPlaced = () => fetchLeaderboard();
    window.addEventListener('duckpools:bet-placed', handleBetPlaced);

    return () => {
      window.removeEventListener('duckpools:bet-placed', handleBetPlaced);
    };
  }, [fetchLeaderboard]);

  return (
    <div className="lb-container">
      <h3 className="lb-title">Leaderboard</h3>
      <p className="lb-subtitle">Top players by performance</p>

      {error && <div className="lb-error">{error}</div>}

      {loading ? (
        <div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="lb-skeleton-row">
              <div className="lb-skeleton-cell" style={{ width: 40 }} />
              <div className="lb-skeleton-cell" style={{ width: 100 }} />
              <div className="lb-skeleton-cell" style={{ width: 50 }} />
              <div className="lb-skeleton-cell" style={{ width: 80 }} />
              <div className="lb-skeleton-cell" style={{ width: 60 }} />
            </div>
          ))}
        </div>
      ) : data.length === 0 ? (
        <div className="lb-empty">No players yet. Be the first to flip!</div>
      ) : (
        <div className="lb-table-wrap">
          <table className="lb-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'center' }}>#</th>
                <th>Player</th>
                <th>Bets</th>
                <th>Net PnL</th>
                <th>Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {data.map((entry) => {
                const pnl = parseFloat(entry.netPnL);
                const rankClass =
                  entry.rank <= 3 ? `lb-rank--${entry.rank}` : '';

                return (
                  <tr key={entry.address}>
                    <td className={`lb-rank ${rankClass}`}>
                      {entry.rank}
                    </td>
                    <td>
                      <a
                        className="lb-address"
                        href={getExplorerAddressUrl(entry.address)}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {formatAddress(entry.address, 6)}
                      </a>
                    </td>
                    <td className="lb-rank">{entry.totalBets}</td>
                    <td>
                      <span
                        className={`lb-pnl ${
                          pnl > 0
                            ? 'lb-pnl--positive'
                            : pnl < 0
                            ? 'lb-pnl--negative'
                            : 'lb-pnl--zero'
                        }`}
                      >
                        {pnl > 0 ? '+' : ''}
                        {formatErg(entry.netPnL)} ERG
                      </span>
                    </td>
                    <td className="lb-rank">{entry.winRate.toFixed(1)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPlayers > 0 && (
        <p
          style={{
            marginTop: 12,
            fontSize: '0.78rem',
            color: 'var(--text-secondary, #8892b0)',
            textAlign: 'center',
          }}
        >
          Showing top {data.length} of {totalPlayers} players
        </p>
      )}
    </div>
  );
}
