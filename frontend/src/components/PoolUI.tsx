/**
 * PoolUI - Liquidity Pool Interface
 *
 * React component for LP deposit, withdrawal, and pool stats.
 * MAT-15: Tokenized bankroll and liquidity pool
 */

import React, { useState, useEffect, useCallback } from 'react';
import { HttpPoolClient, PoolFormatters } from '../pool/PoolClient';
import type {
  PoolStateResponse,
  APYResponse,
  LPBalanceResponse,
  EstimateResponse,
} from '../pool/types';

// ─── Types ──────────────────────────────────────────────────────────

interface PoolUIProps {
  /** Backend API base URL */
  apiUrl?: string;
  /** Connected wallet address */
  walletAddress?: string | null;
  /** ERG balance of connected wallet (nanoERG) */
  walletErgBalance?: bigint;
  /** LP token balance of connected wallet */
  walletLpBalance?: bigint;
  /** Called when a transaction needs signing */
  onSignTx?: (txJson: Record<string, unknown>) => Promise<string | null>;
  /** CSS class prefix for styling */
  className?: string;
}

interface PoolStats {
  state: PoolStateResponse | null;
  apy: APYResponse | null;
  balance: LPBalanceResponse | null;
  loading: boolean;
  error: string | null;
}

// ─── Component ──────────────────────────────────────────────────────

export function PoolUI({
  apiUrl = '/api',
  walletAddress = null,
  walletErgBalance = 0n,
  walletLpBalance = 0n,
  onSignTx,
  className = 'pool-ui',
}: PoolUIProps) {
  const client = React.useMemo(() => new HttpPoolClient(apiUrl), [apiUrl]);

  const [stats, setStats] = useState<PoolStats>({
    state: null,
    apy: null,
    balance: null,
    loading: true,
    error: null,
  });

  // ─── Active Tab ──────────────────────────────────────────────────

  const [activeTab, setActiveTab] = useState<'deposit' | 'withdraw'>('deposit');
  const [depositAmount, setDepositAmount] = useState('');
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [depositEstimate, setDepositEstimate] = useState<EstimateResponse | null>(null);
  const [withdrawEstimate, setWithdrawEstimate] = useState<EstimateResponse | null>(null);
  const [txStatus, setTxStatus] = useState<{ loading: boolean; message: string; error: string | null }>({
    loading: false,
    message: '',
    error: null,
  });

  // ─── Fetch Pool Data ─────────────────────────────────────────────

  const fetchPoolData = useCallback(async () => {
    try {
      setStats(prev => ({ ...prev, loading: true, error: null }));

      const [state, apy] = await Promise.all([
        client.getPoolState(),
        client.getAPY(),
      ]);

      let balance: LPBalanceResponse | null = null;
      if (walletAddress) {
        try {
          balance = await client.getBalance(walletAddress);
        } catch {
          // Balance fetch may fail if no LP tokens yet
        }
      }

      setStats({ state, apy, balance, loading: false, error: null });
    } catch (err) {
      setStats({
        state: null,
        apy: null,
        balance: null,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to load pool data',
      });
    }
  }, [client, walletAddress]);

  useEffect(() => {
    fetchPoolData();
    const interval = setInterval(fetchPoolData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchPoolData]);

  // ─── Deposit Estimate ────────────────────────────────────────────

  useEffect(() => {
    if (activeTab !== 'deposit' || !depositAmount) {
      setDepositEstimate(null);
      return;
    }

    const amountNano = BigInt(Math.round(parseFloat(depositAmount) * 1e9));
    if (amountNano <= 0n) {
      setDepositEstimate(null);
      return;
    }

    const debounce = setTimeout(async () => {
      try {
        const estimate = await client.estimateDeposit(Number(amountNano));
        setDepositEstimate(estimate);
      } catch {
        setDepositEstimate(null);
      }
    }, 500);

    return () => clearTimeout(debounce);
  }, [activeTab, depositAmount, client]);

  // ─── Withdraw Estimate ───────────────────────────────────────────

  useEffect(() => {
    if (activeTab !== 'withdraw' || !withdrawAmount) {
      setWithdrawEstimate(null);
      return;
    }

    const shares = BigInt(withdrawAmount);
    if (shares <= 0n) {
      setWithdrawEstimate(null);
      return;
    }

    const debounce = setTimeout(async () => {
      try {
        const estimate = await client.estimateWithdraw(Number(shares));
        setWithdrawEstimate(estimate);
      } catch {
        setWithdrawEstimate(null);
      }
    }, 500);

    return () => clearTimeout(debounce);
  }, [activeTab, withdrawAmount, client]);

  // ─── Handlers ────────────────────────────────────────────────────

  const handleDeposit = async () => {
    if (!walletAddress || !depositAmount) return;

    const amountNano = BigInt(Math.round(parseFloat(depositAmount) * 1e9));
    if (amountNano <= 0n || amountNano > walletErgBalance) return;

    setTxStatus({ loading: true, message: 'Building deposit transaction...', error: null });

    try {
      const result = await client.buildDepositTx(Number(amountNano), walletAddress);

      if (onSignTx) {
        const txId = await onSignTx(result.txJson);
        if (txId) {
          setTxStatus({ loading: false, message: `Deposit submitted! TX: ${txId}`, error: null });
          setDepositAmount('');
          setDepositEstimate(null);
          fetchPoolData();
        } else {
          setTxStatus({ loading: false, message: '', error: 'Transaction signing cancelled' });
        }
      } else {
        setTxStatus({ loading: false, message: 'Transaction built (no wallet connected for signing)', error: null });
      }
    } catch (err) {
      setTxStatus({
        loading: false,
        message: '',
        error: err instanceof Error ? err.message : 'Deposit failed',
      });
    }
  };

  const handleWithdraw = async () => {
    if (!walletAddress || !withdrawAmount) return;

    const shares = BigInt(withdrawAmount);
    if (shares <= 0n || shares > walletLpBalance) return;

    setTxStatus({ loading: true, message: 'Creating withdrawal request...', error: null });

    try {
      const result = await client.requestWithdraw(Number(shares), walletAddress);

      if (onSignTx) {
        const txId = await onSignTx(result.txJson);
        if (txId) {
          setTxStatus({
            loading: false,
            message: `Withdrawal requested! TX: ${txId}. Cooldown: ${stats.state?.cooldownHours || '?'}h`,
            error: null,
          });
          setWithdrawAmount('');
          setWithdrawEstimate(null);
          fetchPoolData();
        } else {
          setTxStatus({ loading: false, message: '', error: 'Transaction signing cancelled' });
        }
      } else {
        setTxStatus({ loading: false, message: 'Request built (no wallet connected)', error: null });
      }
    } catch (err) {
      setTxStatus({
        loading: false,
        message: '',
        error: err instanceof Error ? err.message : 'Withdrawal request failed',
      });
    }
  };

  // ─── Render ──────────────────────────────────────────────────────

  if (stats.loading) {
    return <div className={`${className} ${className}--loading`}>Loading pool data...</div>;
  }

  if (stats.error) {
    return (
      <div className={`${className} ${className}--error`}>
        <p>Failed to load pool: {stats.error}</p>
        <button onClick={fetchPoolData}>Retry</button>
      </div>
    );
  }

  if (!stats.state) return null;

  const { state, apy, balance } = stats;
  const isConnected = !!walletAddress;
  const ergBalance = PoolFormatters.nanoErgToCompact(walletErgBalance);

  return (
    <div className={className}>
      {/* ─── Pool Stats Header ───────────────────────────────────── */}
      <div className={`${className}__stats`}>
        <div className={`${className}__stat`}>
          <span className={`${className}__stat-label`}>Total Value Locked</span>
          <span className={`${className}__stat-value`}>
            {state.totalValueErg} ERG
          </span>
        </div>
        <div className={`${className}__stat`}>
          <span className={`${className}__stat-label`}>APY</span>
          <span className={`${className}__stat-value ${className}__stat-value--green`}>
            {apy ? PoolFormatters.formatPercent(apy.apyPercent) : '--'}
          </span>
        </div>
        <div className={`${className}__stat`}>
          <span className={`${className}__stat-label`}>LP Token Price</span>
          <span className={`${className}__stat-value`}>
            {state.pricePerShareErg} ERG
          </span>
        </div>
        <div className={`${className}__stat`}>
          <span className={`${className}__stat-label`}>House Edge</span>
          <span className={`${className}__stat-value`}>
            {(state.houseEdgeBps / 100).toFixed(1)}%
          </span>
        </div>
        <div className={`${className}__stat`}>
          <span className={`${className}__stat-label`}>Pending Bets</span>
          <span className={`${className}__stat-value`}>
            {state.pendingBets}
          </span>
        </div>
        <div className={`${className}__stat`}>
          <span className={`${className}__stat-label`}>Withdraw Cooldown</span>
          <span className={`${className}__stat-value`}>
            {PoolFormatters.formatCooldown(state.cooldownBlocks)}
          </span>
        </div>
      </div>

      {/* ─── User Balance (if connected) ──────────────────────────── */}
      {isConnected && (
        <div className={`${className}__user-balance`}>
          <div>
            <span>Your LP Balance: </span>
            <strong>{balance ? PoolFormatters.nanoErgToCompact(balance.ergValue) : '0'} ERG</strong>
            {balance && <span> ({PoolFormatters.formatPercent(balance.sharePercent)} of pool)</span>}
          </div>
          <div>
            <span>Wallet Balance: </span>
            <strong>{ergBalance} ERG</strong>
          </div>
        </div>
      )}

      {/* ─── Tab Switcher ─────────────────────────────────────────── */}
      <div className={`${className}__tabs`}>
        <button
          className={`${className}__tab ${activeTab === 'deposit' ? `${className}__tab--active` : ''}`}
          onClick={() => setActiveTab('deposit')}
        >
          Deposit
        </button>
        <button
          className={`${className}__tab ${activeTab === 'withdraw' ? `${className}__tab--active` : ''}`}
          onClick={() => setActiveTab('withdraw')}
          disabled={!isConnected || walletLpBalance === 0n}
        >
          Withdraw
        </button>
      </div>

      {/* ─── Deposit Panel ────────────────────────────────────────── */}
      {activeTab === 'deposit' && (
        <div className={`${className}__panel`}>
          <div className={`${className}__field`}>
            <label>Deposit Amount (ERG)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              placeholder="0.0"
              value={depositAmount}
              onChange={(e) => setDepositAmount(e.target.value)}
              disabled={!isConnected}
            />
            <button
              className={`${className}__max-btn`}
              onClick={() => setDepositAmount(ergBalance)}
              disabled={!isConnected}
            >
              MAX
            </button>
          </div>

          {depositEstimate && (
            <div className={`${className}__estimate`}>
              <p>You will receive approximately:</p>
              <p className={`${className}__estimate-value`}>
                {PoolFormatters.formatLPAmount(depositEstimate.shares)} LP tokens
              </p>
              <p className={`${className}__estimate-detail`}>
                Price: {PoolFormatters.nanoErgToCompact(depositEstimate.pricePerShare)} ERG per share
              </p>
            </div>
          )}

          {!isConnected && (
            <p className={`${className}__connect-prompt`}>
              Connect your wallet to deposit ERG
            </p>
          )}

          <button
            className={`${className}__action-btn`}
            onClick={handleDeposit}
            disabled={!isConnected || !depositAmount || parseFloat(depositAmount) <= 0}
          >
            Deposit ERG
          </button>
        </div>
      )}

      {/* ─── Withdraw Panel ───────────────────────────────────────── */}
      {activeTab === 'withdraw' && (
        <div className={`${className}__panel`}>
          <div className={`${className}__field`}>
            <label>LP Shares to Withdraw</label>
            <input
              type="number"
              step="1"
              min="0"
              placeholder="0"
              value={withdrawAmount}
              onChange={(e) => setWithdrawAmount(e.target.value)}
            />
            <button
              className={`${className}__max-btn`}
              onClick={() => setWithdrawAmount(walletLpBalance.toString())}
            >
              MAX
            </button>
          </div>

          {withdrawEstimate && (
            <div className={`${className}__estimate`}>
              <p>You will receive approximately:</p>
              <p className={`${className}__estimate-value`}>
                {PoolFormatters.nanoErgToCompact(withdrawEstimate.ergAmount)} ERG
              </p>
              <p className={`${className}__estimate-detail`}>
                Price: {PoolFormatters.nanoErgToCompact(withdrawEstimate.pricePerShare)} ERG per share
              </p>
              {state && (
                <p className={`${className}__estimate-detail`}>
                  Cooldown: {PoolFormatters.formatCooldown(state.cooldownBlocks)} before execution
                </p>
              )}
            </div>
          )}

          <button
            className={`${className}__action-btn`}
            onClick={handleWithdraw}
            disabled={!withdrawAmount || BigInt(withdrawAmount) <= 0n || BigInt(withdrawAmount) > walletLpBalance}
          >
            Request Withdrawal
          </button>
        </div>
      )}

      {/* ─── Transaction Status ───────────────────────────────────── */}
      {txStatus.message && (
        <div className={`${className}__tx-status ${className}__tx-status--${txStatus.error ? 'error' : 'success'}`}>
          {txStatus.message}
        </div>
      )}
      {txStatus.loading && (
        <div className={`${className}__tx-status ${className}__tx-status--loading`}>
          Processing...
        </div>
      )}

      {/* ─── Risk Warning ─────────────────────────────────────────── */}
      <div className={`${className}__risk-warning`}>
        <strong>Risk Notice:</strong> LPs can lose ERG if players go on winning streaks.
        Bankroll variance is real. Only deposit what you can afford to lose.
      </div>

      {/* ─── APY Details ──────────────────────────────────────────── */}
      {apy && (
        <div className={`${className}__apy-details`}>
          <h3>Yield Estimates</h3>
          <div className={`${className}__apy-grid`}>
            <div>Daily: {PoolFormatters.nanoErgToCompact(apy.estimatedDailyProfitErg)} ERG</div>
            <div>Monthly: {PoolFormatters.nanoErgToCompact(apy.estimatedMonthlyProfitErg)} ERG</div>
            <div>Yearly: {PoolFormatters.nanoErgToCompact(apy.estimatedYearlyProfitErg)} ERG</div>
          </div>
          <p className={`${className}__apy-note`}>
            Based on {apy.betsPerBlock} bets/block at avg {apy.avgBetSizeErg} ERG.
            Actual returns depend on betting volume.
          </p>
        </div>
      )}
    </div>
  );
}

export default PoolUI;
