import { useState, useCallback, useMemo } from 'react';
import { useWallet } from '../contexts/WalletContext';
import { generateSecret, bytesToHex } from '../utils/crypto';
import { ergToNanoErg, formatErg } from '../utils/ergo';
import { buildApiUrl } from '../utils/network';
import {
  DICE_MIN_TARGET,
  DICE_MAX_TARGET,
  DICE_DEFAULT_TARGET,
  getDiceHouseEdge,
  getDiceMultiplier,
  getDiceWinProbability,
  calculateDicePayout,
  generateDiceCommit,
} from '../utils/dice';
import './DiceForm.css';

// ─── Helpers ──────────────────────────────────────────────────

function generateBetId(): string {
  return crypto.randomUUID();
}

function getExplorerTxUrl(txId: string): string {
  return `https://explorer.ergoplatform.com/en/transactions/${txId}`;
}

// ─── Component ────────────────────────────────────────────────

export default function DiceForm() {
  const { isConnected, walletAddress, connect } = useWallet();

  const [amount, setAmount] = useState('');
  const [rollTarget, setRollTarget] = useState(DICE_DEFAULT_TARGET);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingBet, setPendingBet] = useState<{
    txId: string;
    betId: string;
    amount: string;
    rollTarget: number;
  } | null>(null);

  // ── Computed values ─────────────────────────────────────────

  const amountNanoErg = ergToNanoErg(amount);
  const isValidAmount =
    amount !== '' && !isNaN(parseFloat(amount)) && parseFloat(amount) > 0;
  const canSubmit =
    isConnected &&
    isValidAmount &&
    !isSubmitting &&
    walletAddress !== undefined;

  const houseEdge = useMemo(() => getDiceHouseEdge(rollTarget), [rollTarget]);
  const multiplier = useMemo(() => getDiceMultiplier(rollTarget), [rollTarget]);
  const winProb = useMemo(() => getDiceWinProbability(rollTarget), [rollTarget]);
  const payoutNanoErg = useMemo(
    () => (isValidAmount ? calculateDicePayout(parseInt(amountNanoErg, 10), rollTarget) : 0n),
    [isValidAmount, amountNanoErg, rollTarget]
  );

  // ── Risk level classification ──────────────────────────────

  const riskLevel = useMemo(() => {
    if (rollTarget <= 10) return 'high';
    if (rollTarget <= 30) return 'medium-high';
    if (rollTarget <= 60) return 'medium';
    if (rollTarget <= 85) return 'low';
    return 'safe';
  }, [rollTarget]);

  // ── Handlers ───────────────────────────────────────────────

  const handleAmountChange = useCallback((value: string) => {
    if (value === '' || /^\d*\.?\d*$/.test(value)) {
      setAmount(value);
      setError(null);
    }
  }, []);

  const handleQuickPick = useCallback((value: string) => {
    setAmount(value);
    setError(null);
  }, []);

  const handleQuickTarget = useCallback((target: number) => {
    setRollTarget(target);
    setError(null);
  }, []);

  const handleSliderChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setRollTarget(parseInt(e.target.value, 10));
    setError(null);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit || !walletAddress) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Generate secret & commitment (dice-specific: includes rollTarget)
      const secret = generateSecret();
      const { commitment } = await generateDiceCommit(rollTarget, secret);
      const betId = generateBetId();
      const secretHex = bytesToHex(secret);

      // 2. Build API request (game_type=dice for backend routing)
      const payload = {
        address: walletAddress,
        amount: amountNanoErg,
        game_type: 'dice',
        roll_target: rollTarget,
        commitment,
        secret: secretHex,
        bet_id: betId,
      };

      // 3. Submit to backend
      const res = await fetch(buildApiUrl('/place-bet'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || `Server error ${res.status}`);
      }

      // 4. Show pending state
      setPendingBet({
        txId: data.txId,
        betId,
        amount,
        rollTarget,
      });

      // Reset form
      setAmount('');
      setRollTarget(DICE_DEFAULT_TARGET);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to place bet';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [canSubmit, walletAddress, amountNanoErg, amount, rollTarget]);

  // ── Not connected ──────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className="df-container">
        <div className="df-connect-prompt">
          <p>Connect your wallet to start rolling</p>
          <button className="df-connect-btn" onClick={connect}>
            Connect Wallet
          </button>
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────

  return (
    <div className="df-container">
      <h2 className="df-title">Dice</h2>

      {/* ── Amount Input ──────────────────────────────────────── */}
      <div className="df-amount-section">
        <label className="df-amount-label">Bet Amount</label>
        <div className="df-amount-input-row">
          <input
            className="df-amount-input"
            type="text"
            inputMode="decimal"
            placeholder="0.0"
            value={amount}
            onChange={(e) => handleAmountChange(e.target.value)}
            disabled={isSubmitting}
          />
          <span className="df-amount-suffix">ERG</span>
        </div>
        <div className="df-quick-picks">
          {[0.1, 0.5, 1, 5, 10].map((val) => (
            <button
              key={val}
              className="df-quick-pick"
              onClick={() => handleQuickPick(val.toString())}
              disabled={isSubmitting}
            >
              {val} ERG
            </button>
          ))}
        </div>
      </div>

      {/* ── Roll Target (Slider + Number) ────────────────────── */}
      <div className="df-target-section">
        <label className="df-target-label">
          Roll Under Target
          <span className="df-target-value">{rollTarget}</span>
        </label>

        <div className="df-slider-row">
          <span className="df-slider-bound">2</span>
          <input
            className="df-slider"
            type="range"
            min={DICE_MIN_TARGET}
            max={DICE_MAX_TARGET}
            value={rollTarget}
            onChange={handleSliderChange}
            disabled={isSubmitting}
          />
          <span className="df-slider-bound">98</span>
        </div>

        <div className="df-target-presets">
          {[5, 25, 50, 75, 95].map((target) => (
            <button
              key={target}
              className={`df-target-preset${
                rollTarget === target ? ' df-target-preset--active' : ''
              }`}
              onClick={() => handleQuickTarget(target)}
              disabled={isSubmitting}
            >
              {target}
            </button>
          ))}
        </div>
      </div>

      {/* ── Live Stats Panel ──────────────────────────────────── */}
      <div className={`df-stats-panel df-stats-panel--${riskLevel}`}>
        <div className="df-stat">
          <span className="df-stat-label">Win Chance</span>
          <span className="df-stat-value df-stat-value--prob">{winProb}%</span>
        </div>
        <div className="df-stat">
          <span className="df-stat-label">Multiplier</span>
          <span className="df-stat-value df-stat-value--multi">{multiplier.toFixed(4)}x</span>
        </div>
        <div className="df-stat">
          <span className="df-stat-label">House Edge</span>
          <span className="df-stat-value df-stat-value--edge">{(houseEdge * 100).toFixed(1)}%</span>
        </div>
        {isValidAmount && (
          <div className="df-stat">
            <span className="df-stat-label">Potential Win</span>
            <span className="df-stat-value df-stat-value--payout">
              {formatErg(payoutNanoErg.toString())} ERG
            </span>
          </div>
        )}
      </div>

      {/* ── Risk Bar Visualization ────────────────────────────── */}
      <div className="df-risk-bar">
        <div
          className="df-risk-bar-fill"
          style={{
            width: `${rollTarget}%`,
            background:
              riskLevel === 'high'
                ? 'linear-gradient(90deg, #ef4444, #f59e0b)'
                : riskLevel === 'medium-high'
                ? 'linear-gradient(90deg, #f59e0b, #eab308)'
                : riskLevel === 'medium'
                ? 'linear-gradient(90deg, #eab308, #f0b429)'
                : riskLevel === 'low'
                ? 'linear-gradient(90deg, #f0b429, #22c55e)'
                : 'linear-gradient(90deg, #22c55e, #00ff88)',
          }}
        />
        <div className="df-risk-bar-labels">
          <span>Risky</span>
          <span>Safe</span>
        </div>
      </div>

      {/* ── Submit ───────────────────────────────────────────── */}
      <button
        className={`df-submit-btn${isSubmitting ? ' df-submit-btn--loading' : ''}`}
        onClick={handleSubmit}
        disabled={!canSubmit}
      >
        {isSubmitting ? (
          <>
            <span className="df-spinner" />
            Rolling...
          </>
        ) : (
          'Roll Dice!'
        )}
      </button>

      {/* ── Error ────────────────────────────────────────────── */}
      {error && <div className="df-error">{error}</div>}

      {/* ── Pending Bet ──────────────────────────────────────── */}
      {pendingBet && (
        <div className="df-pending">
          <div className="df-pending-title">
            <span className="df-pending-spinner" />
            Bet Pending Confirmation
          </div>
          <div className="df-pending-row">
            <span className="df-pending-row-label">Bet ID</span>
            <span className="df-pending-row-value">{pendingBet.betId.slice(0, 16)}...</span>
          </div>
          <div className="df-pending-row">
            <span className="df-pending-row-label">Amount</span>
            <span className="df-pending-row-value">{pendingBet.amount} ERG</span>
          </div>
          <div className="df-pending-row">
            <span className="df-pending-row-label">Roll Under</span>
            <span className="df-pending-row-value">{pendingBet.rollTarget}</span>
          </div>
          <div className="df-pending-row">
            <span className="df-pending-row-label">Multiplier</span>
            <span className="df-pending-row-value">
              {getDiceMultiplier(pendingBet.rollTarget).toFixed(4)}x
            </span>
          </div>
          <div className="df-pending-row">
            <span className="df-pending-row-label">TX</span>
            <a
              className="df-pending-link"
              href={getExplorerTxUrl(pendingBet.txId)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {pendingBet.txId.slice(0, 16)}...
            </a>
          </div>
        </div>
      )}

      {/* ── Info ─────────────────────────────────────────────── */}
      <div className="df-info">
        <span className="df-info-item">
          RNG: <strong>SHA256</strong>
        </span>
        <span className="df-info-item">
          Provably Fair: <strong>Commit-Reveal</strong>
        </span>
      </div>
    </div>
  );
}
