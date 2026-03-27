import { useState, useEffect, useCallback } from 'react';
import { useWallet } from '../contexts/WalletContext';
import { buildApiUrl } from '../utils/network';
import type { CompPoints } from '../types/Game';
import './CompPoints.css';

const TIER_ORDER = ['bronze', 'silver', 'gold', 'diamond'];

function getTierClass(tier: string): string {
  const normalized = tier.toLowerCase();
  if (normalized === 'diamond') return 'cp-tier-name--diamond';
  if (normalized === 'gold') return 'cp-tier-name--gold';
  if (normalized === 'silver') return 'cp-tier-name--silver';
  return 'cp-tier-name--bronze';
}

function getFillClass(tier: string): string {
  const normalized = tier.toLowerCase();
  if (normalized === 'diamond') return 'cp-progress-fill--diamond';
  if (normalized === 'gold') return 'cp-progress-fill--gold';
  if (normalized === 'silver') return 'cp-progress-fill--silver';
  return 'cp-progress-fill--bronze';
}

export default function CompPoints() {
  const { isConnected, walletAddress } = useWallet();

  const [comp, setComp] = useState<CompPoints | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchComp = useCallback(async () => {
    if (!walletAddress) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(buildApiUrl(`/player/comp/${walletAddress}`));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: CompPoints = await res.json();
      setComp(data);
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
      setComp(null);
      return;
    }
    fetchComp();
  }, [isConnected, walletAddress, fetchComp]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className="cp-container">
        <p className="cp-connect">Connect your wallet to view comp points</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="cp-container">
        <h3 className="cp-title">Comp Points</h3>
        <div className="cp-skeleton" />
        <div className="cp-skeleton" style={{ marginTop: 12 }} />
        <div className="cp-skeleton" style={{ marginTop: 12, height: 50 }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="cp-container">
        <h3 className="cp-title">Comp Points</h3>
        <div className="cp-error">{error}</div>
      </div>
    );
  }

  if (!comp) return null;

  const isMaxTier = !comp.nextTier || TIER_ORDER.indexOf(comp.tier.toLowerCase()) >= TIER_ORDER.length - 1;
  const progressPct = isMaxTier ? 100 : Math.min(comp.tierProgress * 100, 100);

  return (
    <div className="cp-container">
      <h3 className="cp-title">Comp Points</h3>

      {/* ── Tier Header ────────────────────────────────────────────── */}
      <div className="cp-tier-header">
        <span className={`cp-tier-name ${getTierClass(comp.tier)}`}>
          {comp.tier}
        </span>
        <span className="cp-points-value">
          {comp.points.toLocaleString()} pts
        </span>
      </div>

      {/* ── Progress Bar ───────────────────────────────────────────── */}
      <div className="cp-progress-section">
        <div className="cp-progress-header">
          <span>{comp.tier}</span>
          <span>
            {isMaxTier
              ? 'MAX TIER'
              : `${comp.pointsToNextTier.toLocaleString()} pts to ${comp.nextTier}`}
          </span>
        </div>
        <div className="cp-progress-bar">
          <div
            className={`cp-progress-fill ${getFillClass(comp.tier)}`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* ── Stats ──────────────────────────────────────────────────── */}
      <div className="cp-stats">
        <div className="cp-stat">
          <div className="cp-stat-label">Total Earned</div>
          <div className="cp-stat-value">
            {comp.totalEarned.toLocaleString()}
          </div>
        </div>
        <div className="cp-stat">
          <div className="cp-stat-label">Current Points</div>
          <div className="cp-stat-value">
            {comp.points.toLocaleString()}
          </div>
        </div>
      </div>

      {/* ── Benefits ───────────────────────────────────────────────── */}
      {comp.benefits && comp.benefits.length > 0 && (
        <div className="cp-benefits">
          <div className="cp-benefits-title">
            {comp.tier} Benefits
          </div>
          <ul className="cp-benefits-list">
            {comp.benefits.map((benefit, i) => (
              <li key={i}>{benefit}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
