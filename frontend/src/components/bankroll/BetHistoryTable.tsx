import { useState } from 'react';
import { formatErg, formatAddress } from '../../utils/ergo';
import { useBankrollStore } from '../../stores/bankrollStore';
import type { GlobalBetRecord } from '../../types/Bankroll';
import './BetHistoryTable.css';

const PAGE_SIZE = 20;

type OutcomeFilter = 'all' | 'win' | 'loss' | 'pending';

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

function getExplorerTxUrl(txId: string): string {
  const base = import.meta.env.VITE_EXPLORER_URL || 'https://testnet.ergoplatform.com';
  return `${base}/en/transactions/${txId}`;
}

export default function BetHistoryTable() {
  const globalBets = useBankrollStore((s) => s.globalBets);
  const isLoading = useBankrollStore((s) => s.isLoadingBets);

  const [filter, setFilter] = useState<OutcomeFilter>('all');
  const [page, setPage] = useState(0);

  const filtered = filter === 'all'
    ? globalBets
    : globalBets.filter((b) => b.outcome === filter);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div className="bk-bets">
      <div className="bk-bets-header">
        <span className="bk-bets-title">&#127922; Recent Bets</span>
        <div className="bk-bets-filters">
          {(['all', 'win', 'loss', 'pending'] as OutcomeFilter[]).map((f) => (
            <button
              key={f}
              className={`bk-bets-filter ${filter === f ? 'bk-bets-filter--active' : ''}`}
              onClick={() => { setFilter(f); setPage(0); }}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {isLoading && globalBets.length === 0 ? (
        <div className="bk-bets-skeleton">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bk-bets-skeleton-row">
              {Array.from({ length: 6 }).map((_, j) => (
                <div key={j} className="bk-bets-skeleton-cell" style={{ width: [90, 60, 70, 60, 70, 80][j] }} />
              ))}
            </div>
          ))}
        </div>
      ) : paged.length === 0 ? (
        <div className="bk-bets-empty">No bets recorded yet.</div>
      ) : (
        <>
          <div className="bk-bets-table-wrap">
            <table className="bk-bets-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Player</th>
                  <th>Game</th>
                  <th>Wager</th>
                  <th>Outcome</th>
                  <th>Payout</th>
                  <th>TX</th>
                </tr>
              </thead>
              <tbody>
                {paged.map((bet) => (
                  <BetRow key={bet.betId} bet={bet} />
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="bk-bets-pagination">
              <button
                className="bk-bets-page-btn"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Prev
              </button>
              <span className="bk-bets-page-info">
                {page + 1} / {totalPages}
              </span>
              <button
                className="bk-bets-page-btn"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function BetRow({ bet }: { bet: GlobalBetRecord }) {
  return (
    <tr>
      <td className="bk-bets-date">{formatDate(bet.timestamp)}</td>
      <td className="bk-bets-player">{formatAddress(bet.playerAddress)}</td>
      <td className="bk-bets-game">{bet.gameType}</td>
      <td className="bk-bets-mono">{formatErg(bet.betAmount)} ERG</td>
      <td>
        <span className={`bk-bets-outcome bk-bets-outcome--${bet.outcome}`}>
          {bet.outcome}
        </span>
      </td>
      <td className="bk-bets-mono">
        {bet.payout && bet.payout !== '0' ? `${formatErg(bet.payout)} ERG` : '—'}
      </td>
      <td>
        <a
          className="bk-bets-tx"
          href={getExplorerTxUrl(bet.txId)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {bet.txId.slice(0, 10)}...
        </a>
      </td>
    </tr>
  );
}
