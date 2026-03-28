import { useState, useEffect, useCallback } from 'react';
import { Coins } from 'lucide-react';
import { useWallet } from '../contexts/WalletContext';
import { buildApiUrl } from '../utils/network';
import { formatErg } from '../utils/ergo';
import { Button } from './ui/Button';
import { EmptyState } from './ui/EmptyState';
import type { PoolState } from '../types/Pool';
import './PoolManager.css';

export default function PoolManager() {
  const { isConnected, walletAddress } = useWallet();

  const [poolState, setPoolState] = useState<PoolState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPoolState = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(buildApiUrl('/pool/state'));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data: PoolState = await res.json();
      setPoolState(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load pool state'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isConnected) {
      setPoolState(null);
      return;
    }

    fetchPoolState();
  }, [isConnected, fetchPoolState]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className="pm-container">
        <p className="pm-connect">Connect your wallet to view pool state</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="pm-container">
        <h3 className="pm-title">Pool State</h3>
        <div className="pm-skeleton">
          <div className="pm-skeleton-card" style={{ height: 100, marginBottom: 16 }} />
          <div className="pm-skeleton-row" style={{ height: 60, marginBottom: 12 }} />
          <div className="pm-skeleton-row" style={{ height: 60 }} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pm-container">
        <h3 className="pm-title">Pool State</h3>
        <div className="pm-error">{error}</div>
      </div>
    );
  }

  if (!poolState || parseFloat(poolState.totalLiquidity) === 0) {
    return (
      <div className="pm-container">
        <h3 className="pm-title">Pool State</h3>
        <EmptyState
          icon={<Coins size={48} />}
          title="No liquidity in pool"
          description="Be the first to provide liquidity to the pool"
          actionButton={
            <Button variant="primary" onClick={() => {}}>
              Deposit ERG
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="pm-container">
      <h3 className="pm-title">Pool State</h3>
      
      <div className="pm-stats-grid">
        <div className="pm-stat-card">
          <div className="pm-stat-label">Total Liquidity</div>
          <div className="pm-stat-value">{formatErg(poolState.totalLiquidity)} ERG</div>
        </div>
        <div className="pm-stat-card">
          <div className="pm-stat-label">Total Bets</div>
          <div className="pm-stat-value">{poolState.totalBets}</div>
        </div>
        <div className="pm-stat-card">
          <div className="pm-stat-label">House Edge</div>
          <div className="pm-stat-value">{poolState.houseEdge}%</div>
        </div>
      </div>

      <div className="pm-actions">
        <Button variant="primary" onClick={() => {}}>
          Deposit ERG
        </Button>
        <Button variant="outline" onClick={() => {}}>
          Withdraw
        </Button>
      </div>
    </div>
  );
}