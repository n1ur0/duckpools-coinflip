import { useState, useCallback, useRef, TouchEvent } from 'react';
import { useWallet } from '../../contexts/WalletContext';
import { generateDiceCommit, getDiceMultiplier, DICE_MIN_TARGET, DICE_MAX_TARGET, DICE_DEFAULT_TARGET } from '../../utils/dice';
import { ergToNanoErg, formatErg } from '../../utils/ergo';
import { buildApiUrl } from '../../utils/network';
import './DiceGame.css';

// Quick pick values for bet amounts
const QUICK_PICK_VALUES = [0.1, 0.5, 1, 5];

// Touch gesture thresholds
const SWIPE_THRESHOLD = 50;

function generateBetId(): string {
  return crypto.randomUUID();
}

interface DiceGameProps {
  className?: string;
}

/**
 * Dice Game Component with Touch Support
 *
 * Player selects a roll target (2-98) and bets the roll will be UNDER that number.
 * Lower targets = higher risk = higher payout.
 */
const DiceGame: React.FC<DiceGameProps> = ({ className = '' }) => {
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

  // Touch gesture state
  const touchStartYRef = useRef<number>(0);
  const touchStartTimeRef = useRef<number>(0);

  // ── Validation ──────────────────────────────────────────────────

  const amountNanoErg = ergToNanoErg(amount);
  const isValidAmount =
    amount !== '' && !isNaN(parseFloat(amount)) && parseFloat(amount) > 0;
  const isValidRollTarget =
    rollTarget >= DICE_MIN_TARGET && rollTarget <= DICE_MAX_TARGET;
  const canSubmit =
    isConnected &&
    isValidAmount &&
    isValidRollTarget &&
    !isSubmitting &&
    walletAddress !== undefined;

  const multiplier = getDiceMultiplier(rollTarget);
  const payoutPreview = isValidAmount
    ? formatErg(Math.floor(Number(amountNanoErg) * multiplier))
    : '0.0000';

  // ── Handlers ────────────────────────────────────────────────────

  const handleAmountChange = useCallback(
    (value: string) => {
      if (value === '' || /^\d*\.?\d*$/.test(value)) {
        setAmount(value);
        setError(null);
      }
    },
    []
  );

  const handleQuickPick = useCallback((value: string) => {
    setAmount(value);
    setError(null);
  }, []);

  const handleRollTargetChange = useCallback(
    (value: string) => {
      const target = parseInt(value, 10);
      if (!isNaN(target) && target >= DICE_MIN_TARGET && target <= DICE_MAX_TARGET) {
        setRollTarget(target);
        setError(null);
      }
    },
    []
  );

  // ── Touch Gesture Handlers ─────────────────────────────────────────

  const handleTouchStart = useCallback((e: TouchEvent) => {
    touchStartYRef.current = e.touches[0].clientY;
    touchStartTimeRef.current = Date.now();
  }, []);

  const handleTouchEnd = useCallback((e: TouchEvent) => {
    const touchEndY = e.changedTouches[0].clientY;
    const deltaY = touchStartYRef.current - touchEndY;
    const deltaTime = Date.now() - touchStartTimeRef.current;

    // Only process if gesture was quick enough (< 300ms) and exceeded threshold
    if (deltaTime < 300 && Math.abs(deltaY) > SWIPE_THRESHOLD) {
      const currentTarget = rollTarget;
      
      if (deltaY > 0) {
        // Swipe up: increase risk (lower target)
        const newTarget = Math.max(DICE_MIN_TARGET, currentTarget - 5);
        setRollTarget(newTarget);
      } else {
        // Swipe down: decrease risk (higher target)
        const newTarget = Math.min(DICE_MAX_TARGET, currentTarget + 5);
        setRollTarget(newTarget);
      }
      setError(null);
    }
  }, [rollTarget]);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit || !walletAddress) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Generate secret & commitment
      const { secret, commitment } = await generateDiceCommit(rollTarget);
      const betId = generateBetId();
      const secretHex = Array.from(secret)
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');

      // 2. Build API request
      const payload = {
        address: walletAddress,
        amount: amountNanoErg,
        rollTarget,
        commitment,
        secret: secretHex,
        betId,
      };

      // 3. Submit to backend
      const res = await fetch(buildApiUrl('/place-dice-bet'), {
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
  }, [canSubmit, rollTarget, walletAddress, amountNanoErg, amount]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className={`dice-game-container ${className}`}>
        <div className="dice-connect-prompt">
          <p>Connect your wallet to start playing</p>
          <button className="dice-connect-btn" onClick={connect}>
            Connect Wallet
          </button>
        </div>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className={`dice-game-container ${className}`}>
      <h2 className="dice-title">Dice Game</h2>

      {/* ── Amount Input ──────────────────────────────────────────── */}
      <div className="dice-amount-section">
        <label className="dice-amount-label">Bet Amount</label>
        <div className="dice-amount-input-row">
          <input
            className="dice-amount-input"
            type="text"
            inputMode="decimal"
            placeholder="0.0"
            value={amount}
            onChange={(e) => handleAmountChange(e.target.value)}
            disabled={isSubmitting}
          />
          <span className="dice-amount-suffix">ERG</span>
        </div>
        <div className="dice-quick-picks">
          {QUICK_PICK_VALUES.map((val) => (
            <button
              key={val}
              className="dice-quick-pick"
              onClick={() => handleQuickPick(val.toString())}
              disabled={isSubmitting}
            >
              {val} ERG
            </button>
          ))}
        </div>
        {isValidAmount && (
          <div className="dice-payout-preview">
            Potential payout: <span>{payoutPreview} ERG</span>
          </div>
        )}
      </div>

      {/* ── Roll Target ───────────────────────────────────────────── */}
      <div 
        className="dice-target-section dice-touch-area"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <label className="dice-target-label">
          Roll Target (UNDER {rollTarget})
          <span className="dice-target-hint">
            Swipe ↑↓ to adjust
          </span>
        </label>
        <div className="dice-target-input-row">
          <input
            className="dice-target-input"
            type="range"
            min={DICE_MIN_TARGET}
            max={DICE_MAX_TARGET}
            value={rollTarget}
            onChange={(e) => handleRollTargetChange(e.target.value)}
            disabled={isSubmitting}
          />
          <span className="dice-target-value">{rollTarget}</span>
        </div>
        <div className="dice-stats">
          <span className="dice-stat">
            Win Chance: <strong>{rollTarget}%</strong>
          </span>
          <span className="dice-stat">
            Multiplier: <strong>{multiplier.toFixed(2)}x</strong>
          </span>
        </div>
      </div>

      {/* ── Submit ───────────────────────────────────────────────── */}
      <button
        className={`dice-submit-btn${isSubmitting ? ' dice-submit-btn--loading' : ''}`}
        onClick={handleSubmit}
        disabled={!canSubmit}
      >
        {isSubmitting ? (
          <>
            <span className="dice-spinner" />
            Rolling...
          </>
        ) : (
          'Roll Dice'
        )}
      </button>

      {/* ── Error ────────────────────────────────────────────────── */}
      {error && <div className="dice-error">{error}</div>}

      {/* ── Pending Bet ──────────────────────────────────────────── */}
      {pendingBet && (
        <div className="dice-pending">
          <div className="dice-pending-title">
            <span className="dice-pending-spinner" />
            Bet Pending Confirmation
          </div>
          <div className="dice-pending-row">
            <span className="dice-pending-row-label">Bet ID</span>
            <span className="dice-pending-row-value">{pendingBet.betId.slice(0, 16)}...</span>
          </div>
          <div className="dice-pending-row">
            <span className="dice-pending-row-label">Amount</span>
            <span className="dice-pending-row-value">{pendingBet.amount} ERG</span>
          </div>
          <div className="dice-pending-row">
            <span className="dice-pending-row-label">Target</span>
            <span className="dice-pending-row-value">UNDER {pendingBet.rollTarget}</span>
          </div>
          <div className="dice-pending-row">
            <span className="dice-pending-row-label">TX</span>
            <a
              className="dice-pending-link"
              href={`https://explorer.ergoplatform.com/en/transactions/${pendingBet.txId}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {pendingBet.txId.slice(0, 16)}...
            </a>
          </div>
        </div>
      )}
    </div>
  );
};

export default DiceGame;