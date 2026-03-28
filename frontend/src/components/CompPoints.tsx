import { useState, useEffect, useCallback } from 'react';
import { useWallet } from '../contexts/WalletContext';
import { buildApiUrl } from '../utils/network';
import { Skeleton } from './ui/Skeleton';
import './CompPoints.css';

export interface CompPointsData {
  totalPoints: number;
  currentTier: string;
  pointsToNextTier: number;
  totalEarned: number;
  history: Array<{
    id: string;
    points: number;
    description: string;
    timestamp: string;
  }>;
}

export default function CompPoints() {
  const { isConnected, walletAddress } = useWallet();

  const [compPoints, setCompPoints] = useState<CompPointsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCompPoints = useCallback(async () => {
    if (!walletAddress) return;
    
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(buildApiUrl(`/player/comp/${walletAddress}`));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data: CompPointsData = await res.json();
      setCompPoints(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load comp points'
      );
    } finally {
      setLoading(false);
    }
  }, [walletAddress]);

  useEffect(() => {
    if (!isConnected || !walletAddress) {
      setCompPoints(null);
      return;
    }

    fetchCompPoints();
  }, [isConnected, walletAddress, fetchCompPoints]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className="cp-container">
        <p className="cp-connect">Connect your wallet to view comp points</p>
      </div>
    );
  }

  return (
    <div className="cp-container">
      <h3 className="cp-title">Comp Points</h3>

      {error && <div className="cp-error">{error}</div>}

      {loading ? (
        <div className="cp-skeleton">
          <div className="cp-skeleton-card">
            <Skeleton height={80} />
          </div>
          <div className="cp-skeleton-list">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="cp-skeleton-item">
                <Skeleton height={40} />
              </div>
            ))}
          </div>
        </div>
      ) : compPoints ? (
        <div className="cp-content">
          {/* Points summary card */}
          <div className="cp-summary-card">
            <div className="cp-points-display">
              <div className="cp-points-number">{compPoints.totalPoints.toLocaleString()}</div>
              <div className="cp-points-label">Total Points</div>
            </div>
            <div className="cp-tier-info">
              <div className="cp-tier-badge">{compPoints.currentTier}</div>
              <div className="cp-tier-progress">
                {compPoints.pointsToNextTier} points to next tier
              </div>
            </div>
          </div>

          {/* Points history */}
          <div className="cp-history">
            <h4 className="cp-history-title">Recent Activity</h4>
            {compPoints.history.length > 0 ? (
              <div className="cp-history-list">
                {compPoints.history.map((item) => (
                  <div key={item.id} className="cp-history-item">
                    <div className="cp-history-points">+{item.points}</div>
                    <div className="cp-history-desc">{item.description}</div>
                    <div className="cp-history-date">
                      {new Date(item.timestamp).toLocaleDateString()}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="cp-empty-history">No activity yet</p>
            )}
          </div>
        </div>
      ) : (
        <p className="cp-empty">No comp points data available</p>
      )}
    </div>
  );
}