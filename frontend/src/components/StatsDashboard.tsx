import { useState, useEffect, useCallback } from 'react';
import { BarChart3 } from 'lucide-react';
import { useWallet } from '../contexts/WalletContext';
import { buildApiUrl } from '../utils/network';
import { formatErg } from '../utils/ergo';
import type { PlayerStats } from '../types/Game';
import { EmptyState } from './ui/EmptyState';
import './StatsDashboard.css';

export default function StatsDashboard() {
  const { isConnected, walletAddress } = useWallet();

  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    if (!walletAddress) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(buildApiUrl(`/player/stats/${walletAddress}`));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PlayerStats = await res.json();
      setStats(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load stats'
      );
    } finally {
      setLoading(false);
    }
  }, [walletAddress]);

  useEffect(() => {
    if (!isConnected || !walletAddress) {
      setStats(null);
      return;
    }
    fetchStats();
  }, [isConnected, walletAddress, fetchStats]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className="sd-container">
        <p className="sd-connect">Connect your wallet to view statistics</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="sd-container">
        <h3 className="sd-title">Your Stats</h3>
        <div className="sd-skeleton-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="sd-skeleton-card" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="sd-container">
        <h3 className="sd-title">Your Stats</h3>
        <div className="sd-error">{error}</div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="sd-container">
        <h3 className="sd-title">Your Stats</h3>
        <EmptyState
          icon={<BarChart3 size={48} />}
          title="No stats yet"
          description="Place some bets to see your statistics"
        />
      </div>
    );
  }

  const netPnL = parseFloat(stats.netPnL);

  return (
    <div className="sd-container">
      <h3 className="sd-title">Your Stats</h3>

      {/* ── Stat Cards ────────────────────────────────────────────── */}
      <div className="sd-grid">
        <div className="sd-stat-card">
          <div className="sd-stat-label">Total Bets</div>
          <div className="sd-stat-value">{stats.totalBets}</div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Wins</div>
          <div className="sd-stat-value sd-stat-value--win">{stats.wins}</div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Losses</div>
          <div className="sd-stat-value sd-stat-value--loss">{stats.losses}</div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Pending</div>
          <div className="sd-stat-value sd-stat-value--gold">{stats.pending}</div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Total Wagered</div>
          <div className="sd-stat-value">{formatErg(stats.totalWagered)} ERG</div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Net P&L</div>
          <div className={`sd-stat-value ${netPnL >= 0 ? 'sd-stat-value--win' : 'sd-stat-value--loss'}`}>
            {netPnL >= 0 ? '+' : ''}{formatErg(stats.netPnL)} ERG
          </div>
        </div>
      </div>

      {/* ── Win Rate Bar ──────────────────────────────────────────── */}
      {stats.totalBets > 0 && (
        <div className="sd-winrate-section">
          <div className="sd-winrate-header">
            <span className="sd-winrate-label">Win Rate</span>
            <span className="sd-winrate-pct">{stats.winRate.toFixed(1)}%</span>
          </div>
          <div className="sd-winrate-bar">
            <div
              className="sd-winrate-fill"
              style={{ width: `${Math.min(stats.winRate, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* ── Streaks ───────────────────────────────────────────────── */}
      <div className="sd-streaks">
        <div className="sd-streak">
          <div className="sd-streak-label">Current Streak</div>
          <div
            className={`sd-streak-value ${
              stats.currentStreak > 0 ? 'sd-stat-value--win' :
              stats.currentStreak < 0 ? 'sd-stat-value--loss' : ''
            }`}
          >
            {stats.currentStreak > 0 ? `${stats.currentStreak}W` :
             stats.currentStreak < 0 ? `${Math.abs(stats.currentStreak)}L` : '—'}
          </div>
        </div>
        <div className="sd-streak">
          <div className="sd-streak-label">Best Win Streak</div>
          <div className="sd-streak-value sd-stat-value--win">
            {stats.longestWinStreak}
          </div>
        </div>
        <div className="sd-streak">
          <div className="sd-streak-label">Worst Loss Streak</div>
          <div className="sd-streak-value sd-stat-value--loss">
            {stats.longestLossStreak}
          </div>
        </div>
      </div>
    </div>
  );
}
