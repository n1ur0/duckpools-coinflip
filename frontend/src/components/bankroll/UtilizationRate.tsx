import { useBankrollStore } from '../../stores/bankrollStore';
import { formatErg } from '../../utils/ergo';
import './UtilizationRate.css';

export default function UtilizationRate() {
  const util = useBankrollStore((s) => s.utilization);
  const isLoading = useBankrollStore((s) => s.isLoadingOverview);

  const pct = util?.utilizationPct ?? 0;

  return (
    <div className="bk-util">
      <div className="bk-util-icon">&#128296;</div>
      <div className="bk-util-label">Bankroll Utilization</div>

      {isLoading && !util ? (
        <div className="bk-util-skeleton-wrap">
          <div className="bk-util-skeleton-circle" />
        </div>
      ) : util ? (
        <div className="bk-util-body">
          {/* Ring gauge */}
          <div className="bk-util-gauge">
            <svg viewBox="0 0 100 100" className="bk-util-svg">
              <circle
                cx="50" cy="50" r="42"
                fill="none"
                stroke="rgba(255,255,255,0.06)"
                strokeWidth="8"
              />
              <circle
                cx="50" cy="50" r="42"
                fill="none"
                stroke={pct > 80 ? 'var(--accent-red, #ef4444)' : pct > 50 ? 'var(--accent-gold, #f0b429)' : 'var(--accent-green, #00ff88)'}
                strokeWidth="8"
                strokeDasharray={`${(pct / 100) * 264} 264`}
                strokeLinecap="round"
                transform="rotate(-90 50 50)"
                className="bk-util-gauge-fill"
              />
              <text x="50" y="50" textAnchor="middle" dominantBaseline="central"
                className="bk-util-gauge-text">
                {pct.toFixed(1)}%
              </text>
            </svg>
          </div>

          {/* Breakdown */}
          <div className="bk-util-details">
            <div className="bk-util-row">
              <span className="bk-util-key">Committed</span>
              <span className="bk-util-val">{formatErg(util.committedErg)} ERG</span>
            </div>
            <div className="bk-util-row">
              <span className="bk-util-key">Available</span>
              <span className="bk-util-val">{formatErg(util.availableErg)} ERG</span>
            </div>
            <div className="bk-util-row">
              <span className="bk-util-key">Active Bets</span>
              <span className="bk-util-val">{util.activeBetsCount}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="bk-util-na">No data</div>
      )}
    </div>
  );
}
