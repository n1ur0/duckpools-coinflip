import { useBankrollPoller, useBankrollWebSocket } from '../../hooks/useBankrollPoller';
import { useBankrollStore } from '../../stores/bankrollStore';
import TvlDisplay from './TvlDisplay';
import ProfitTracker from './ProfitTracker';
import UtilizationRate from './UtilizationRate';
import BetHistoryTable from './BetHistoryTable';
import LpStats from './LpStats';
import './BankrollDashboard.css';

export default function BankrollDashboard() {
  // Start polling + optional WS
  useBankrollPoller();
  useBankrollWebSocket();

  const lastPollAt = useBankrollStore((s) => s.lastPollAt);
  const isLoadingOverview = useBankrollStore((s) => s.isLoadingOverview);

  return (
    <div className="bk-dashboard">
      {/* ── Header ─────────────────────────────────── */}
      <div className="bk-dashboard-header">
        <div className="bk-dashboard-title-row">
          <h2 className="bk-dashboard-title">&#127974; Bankroll Dashboard</h2>
          <span className={`bk-dashboard-live ${isLoadingOverview ? '' : 'bk-dashboard-live--idle'}`}>
            <span className="bk-dashboard-live-dot" />
            Live
          </span>
        </div>
        {lastPollAt && (
          <span className="bk-dashboard-poll">
            Updated {formatTimeAgo(lastPollAt)}
          </span>
        )}
      </div>

      {/* ── Top Stats Row ──────────────────────────── */}
      <div className="bk-dashboard-stats">
        <div className="bk-dashboard-stats-col">
          <TvlDisplay />
          <ProfitTracker />
        </div>
        <div className="bk-dashboard-stats-col">
          <UtilizationRate />
          <LpStats />
        </div>
      </div>

      {/* ── Bet History Table ──────────────────────── */}
      <BetHistoryTable />
    </div>
  );
}

function formatTimeAgo(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 5) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  const mins = Math.floor(diff / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}
