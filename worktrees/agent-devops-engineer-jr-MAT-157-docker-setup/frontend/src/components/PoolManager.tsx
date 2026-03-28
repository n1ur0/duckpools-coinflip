import { useState, useEffect, useCallback } from 'react';
import { useWallet } from '../contexts/WalletContext';
import { buildApiUrl } from '../utils/network';
import { ergToNanoErg, formatErg } from '../utils/ergo';
import type { PoolState } from '../types/Game';
import './PoolManager.css';

export default function PoolManager() {
  const { isConnected, walletAddress } = useWallet();

  const [poolState, setPoolState] = useState<PoolState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Action state
  const [actionType, setActionType] = useState<'deposit' | 'withdraw' | null>(null);
  const [amount, setAmount] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{
    type: 'success' | 'error' | 'loading';
    text: string;
  } | null>(null);

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
    fetchPoolState();
    const interval = setInterval(fetchPoolState, 30_000);
    return () => clearInterval(interval);
  }, [fetchPoolState]);

  const handleAction = useCallback(async () => {
    if (!actionType || !amount || !walletAddress) return;

    const nanoErg = ergToNanoErg(amount);
    if (nanoErg === '0') return;

    setActionLoading(true);
    setStatusMsg({ type: 'loading', text: 'Processing...' });

    try {
      const endpoint = actionType === 'deposit' ? '/pool/deposit' : '/pool/withdraw';
      const res = await fetch(buildApiUrl(endpoint), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address: walletAddress, amount: nanoErg }),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || `Request failed (${res.status})`);
      }

      setStatusMsg({
        type: 'success',
        text: `${actionType === 'deposit' ? 'Deposit' : 'Withdrawal'} submitted! TX: ${data.txId || 'pending'}`,
      });
      setAmount('');
      setActionType(null);
      fetchPoolState();
    } catch (err) {
      setStatusMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Action failed',
      });
    } finally {
      setActionLoading(false);
    }
  }, [actionType, amount, walletAddress, fetchPoolState]);

  // ── Loading ─────────────────────────────────────────────────────

  if (loading && !poolState) {
    return (
      <div className="pm-container">
        <h3 className="pm-title">Pool Manager</h3>
        <div className="pm-loading">Loading pool state...</div>
      </div>
    );
  }

  if (error && !poolState) {
    return (
      <div className="pm-container">
        <h3 className="pm-title">Pool Manager</h3>
        <div className="pm-error">{error}</div>
      </div>
    );
  }

  if (!poolState) return null;

  const houseEdgePct = (poolState.houseEdge * 100).toFixed(1);

  return (
    <div className="pm-container">
      <h3 className="pm-title">Pool Manager</h3>

      {/* ── Pool Stats ─────────────────────────────────────────────── */}
      <div className="pm-stats">
        <div className="pm-stat">
          <div className="pm-stat-label">TVL</div>
          <div className="pm-stat-value pm-stat-value--gold">
            {formatErg(poolState.liquidity)} ERG
          </div>
        </div>
        <div className="pm-stat">
          <div className="pm-stat-label">Total Bets</div>
          <div className="pm-stat-value">{poolState.totalBets}</div>
        </div>
        <div className="pm-stat">
          <div className="pm-stat-label">Player Wins</div>
          <div className="pm-stat-value" style={{ color: 'var(--accent-green, #00ff88)' }}>
            {poolState.playerWins}
          </div>
        </div>
        <div className="pm-stat">
          <div className="pm-stat-label">House Wins</div>
          <div className="pm-stat-value" style={{ color: 'var(--accent-red, #ef4444)' }}>
            {poolState.houseWins}
          </div>
        </div>
        <div className="pm-stat">
          <div className="pm-stat-label">House Edge</div>
          <div className="pm-stat-value">{houseEdgePct}%</div>
        </div>
        <div className="pm-stat">
          <div className="pm-stat-label">Total Fees</div>
          <div className="pm-stat-value">{formatErg(poolState.totalFees)} ERG</div>
        </div>
      </div>

      {/* ── Actions (require connected wallet) ─────────────────────── */}
      {!isConnected ? (
        <p className="pm-connect">
          Connect your wallet to deposit or withdraw from the pool
        </p>
      ) : actionType === null ? (
        <div className="pm-actions">
          <button
            className="pm-action-btn pm-action-btn--deposit"
            onClick={() => setActionType('deposit')}
          >
            Deposit
          </button>
          <button
            className="pm-action-btn pm-action-btn--withdraw"
            onClick={() => setActionType('withdraw')}
          >
            Withdraw
          </button>
        </div>
      ) : (
        <div>
          <div className="pm-amount-row">
            <input
              className="pm-amount-input"
              type="text"
              inputMode="decimal"
              placeholder={`Amount to ${actionType}`}
              value={amount}
              onChange={(e) =>
                e.target.value === '' || /^\d*\.?\d*$/.test(e.target.value)
                  ? setAmount(e.target.value)
                  : undefined
              }
              disabled={actionLoading}
            />
            <span className="pm-amount-suffix">ERG</span>
            <button
              className="pm-action-btn pm-action-btn--withdraw"
              style={{ flex: 'none', padding: '10px 16px' }}
              onClick={() => {
                setActionType(null);
                setAmount('');
                setStatusMsg(null);
              }}
            >
              Cancel
            </button>
          </div>
          <button
            className="pm-action-btn pm-action-btn--deposit"
            onClick={handleAction}
            disabled={!amount || parseFloat(amount) <= 0 || actionLoading}
          >
            {actionLoading ? (
              <>
                <span className="pm-spinner" />
                Processing...
              </>
            ) : (
              `Confirm ${actionType === 'deposit' ? 'Deposit' : 'Withdrawal'}`
            )}
          </button>
        </div>
      )}

      {/* ── Status ─────────────────────────────────────────────────── */}
      {statusMsg && (
        <div className={`pm-status pm-status--${statusMsg.type}`}>
          {statusMsg.text}
        </div>
      )}
    </div>
  );
}
