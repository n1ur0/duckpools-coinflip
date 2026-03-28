import { useState, useCallback, useRef, TouchEvent } from 'react';
import { useWallet } from '../../contexts/WalletContext';
import CoinFlip from '../../components/animations/CoinFlip';
import { generateSecret, bytesToHex, blake2b256 } from '../../utils/crypto';
import { ergToNanoErg, formatErg } from '../../utils/ergo';
import { buildApiUrl } from '../../utils/network';
import './CoinFlipGame.css';

// ─── Helpers ──────────────────────────────────────────────────────

function generateBetId(): string {
  return crypto.randomUUID();
}

function generateCommitment(
  secret: Uint8Array,
  choice: number
): string {
  // commitment = blake2b256(secret_8bytes || choice_1byte)
  // MUST match on-chain: blake2b256(secretBytes ++ choiceBytes)
  const buf = new Uint8Array(secret.length + 1);
  buf.set(secret, 0);
  buf[secret.length] = choice;
  const hash = blake2b256(buf);
  return bytesToHex(hash);
}

const HOUSE_EDGE = 0.03;
const PAYOUT_MULTIPLIER = 1 - HOUSE_EDGE; // 0.97

// Touch gesture thresholds
const SWIPE_THRESHOLD = 50; // Minimum pixels for swipe gesture
const QUICK_PICK_VALUES = [0.1, 0.5, 1, 5];

function calculatePayout(amountNanoErg: string): string {
  const nano = BigInt(amountNanoErg);
  return (nano * BigInt(Math.round(PAYOUT_MULTIPLIER * 1e9)) / BigInt(1e9)).toString();
}

function getExplorerTxUrl(txId: string): string {
  return `https://explorer.ergoplatform.com/en/transactions/${txId}`;
}

// ─── Component ──────────────────────────────────────────────────────

interface CoinFlipGameProps {
  className?: string;
}

const CoinFlipGame: React.FC<CoinFlipGameProps> = ({ className = '' }) => {
  const { isConnected, walletAddress, connect } = useWallet();

  const [amount, setAmount] = useState('');
  const [choice, setChoice] = useState<0 | 1 | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFlipping, setIsFlipping] = useState(false);
  const [result, setResult] = useState<'heads' | 'tails' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingBet, setPendingBet] = useState<{
    txId: string;
    betId: string;
    amount: string;
    choiceLabel: string;
  } | null>(null);

  // Touch gesture state
  const touchStartYRef = useRef<number>(0);
  const touchStartTimeRef = useRef<number>(0);

  // ── Validation ──────────────────────────────────────────────────

  const amountNanoErg = ergToNanoErg(amount);
  const isValidAmount =
    amount !== '' && !isNaN(parseFloat(amount)) && parseFloat(amount) > 0;
  const canSubmit =
    isConnected &&
    isValidAmount &&
    choice !== null &&
    !isSubmitting &&
    walletAddress !== undefined;

  const payoutPreview = isValidAmount
    ? formatErg(calculatePayout(amountNanoErg))
    : '0.0000';

  // ── Handlers ────────────────────────────────────────────────────

  const handleAmountChange = useCallback(
    (value: string) => {
      // Allow only valid decimal numbers
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
      const currentAmount = parseFloat(amount) || 0;
      
      if (deltaY > 0) {
        // Swipe up: increase bet
        const newAmount = currentAmount > 0 ? currentAmount * 1.5 : QUICK_PICK_VALUES[0];
        setAmount(newAmount.toFixed(2));
      } else {
        // Swipe down: decrease bet
        const newAmount = Math.max(currentAmount * 0.667, QUICK_PICK_VALUES[0]);
        setAmount(newAmount.toFixed(2));
      }
      setError(null);
    }
  }, [amount]);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit || choice === null || !walletAddress) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Generate secret & commitment
      const secret = generateSecret();
      const commitment = generateCommitment(secret, choice);
      const betId = generateBetId();

      // 2. Build API request
      // SECURITY (SEC-HIGH-2): NEVER send the secret to the backend.
      // The commit-reveal scheme requires the secret to remain private
      // until the on-chain reveal transaction. Only the commitment hash
      // is needed for bet placement.
      const payload = {
        address: walletAddress,
        amount: amountNanoErg,
        choice,
        commitment,
        betId,
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

      // 4. Trigger coin flip animation for chosen side
      const flipResult: 'heads' | 'tails' = choice === 0 ? 'heads' : 'tails';
      setResult(flipResult);
      setIsFlipping(true);

      // 5. Show pending state
      setPendingBet({
        txId: data.txId,
        betId,
        amount,
        choiceLabel: choice === 0 ? 'Heads' : 'Tails',
      });

      // Reset form
      setAmount('');
      setChoice(null);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to place bet';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [canSubmit, choice, walletAddress, amountNanoErg, amount]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className={`coinflip-game-container ${className}`}>
        <div className="coinflip-connect-prompt">
          <p>Connect your wallet to start flipping</p>
          <button className="coinflip-connect-btn" onClick={connect}>
            Connect Wallet
          </button>
        </div>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className={`coinflip-game-container ${className}`}>
      <h2 className="coinflip-title">Coin Flip</h2>

      <div className="coinflip-game-layout">
        {/* ── Main Game Area ───────────────────────────────────────── */}
        <div className="coinflip-main-area">
          {/* ── Coin Visual Area ───────────────────────────────────── */}
          <div className="coinflip-visual-area">
            <div className="coinflip-board">
              <CoinFlip 
                result={result ?? (choice === 0 ? 'heads' : choice === 1 ? 'tails' : null)}
                isFlipping={isFlipping}
                onFlipComplete={() => setIsFlipping(false)}
                size={140}
              />
              {result && (
                <div className={`coinflip-result ${result}`}>
                  {result === 'heads' ? 'HEADS' : 'TAILS'}
                </div>
              )}
            </div>
          </div>

          {/* ── Choice Buttons ───────────────────────────────────── */}
          <div className="coinflip-choice-section">
            <span className="coinflip-choice-label">Pick Your Side</span>
            <div className="coinflip-choice-buttons">
              <button
                className={`coinflip-choice-btn coinflip-choice-btn--heads${
                  choice === 0 ? ' coinflip-choice-btn--selected' : ''
                }`}
                onClick={() => {
                  setChoice(0);
                  setError(null);
                }}
                disabled={isSubmitting}
              >
                Heads
              </button>
              <button
                className={`coinflip-choice-btn coinflip-choice-btn--tails${
                  choice === 1 ? ' coinflip-choice-btn--selected' : ''
                }`}
                onClick={() => {
                  setChoice(1);
                  setError(null);
                }}
                disabled={isSubmitting}
              >
                Tails
              </button>
            </div>
          </div>
        </div>

        {/* ── Bet Controls Sidebar ──────────────────────────────────── */}
        <div className="coinflip-bet-sidebar">
          {/* ── Amount Input ───────────────────────────────────────── */}
          <div 
            className="coinflip-amount-section coinflip-touch-area"
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
          >
            <label className="coinflip-amount-label">
              Bet Amount
              <span className="coinflip-amount-hint">
                Swipe ↑↓ to adjust
              </span>
            </label>
            <div className="coinflip-amount-input-row">
              <input
                className="coinflip-amount-input"
                type="text"
                inputMode="decimal"
                placeholder="0.0"
                value={amount}
                onChange={(e) => handleAmountChange(e.target.value)}
                disabled={isSubmitting}
              />
              <span className="coinflip-amount-suffix">ERG</span>
            </div>
            <div className="coinflip-quick-picks">
              {QUICK_PICK_VALUES.map((val) => (
                <button
                  key={val}
                  className="coinflip-quick-pick"
                  onClick={() => handleQuickPick(val.toString())}
                  disabled={isSubmitting}
                >
                  {val} ERG
                </button>
              ))}
            </div>
            {isValidAmount && (
              <div className="coinflip-payout-preview">
                Potential payout: <span>{payoutPreview} ERG</span>
              </div>
            )}
          </div>

          {/* ── Submit ─────────────────────────────────────────────── */}
          <button
            className={`coinflip-submit-btn${isSubmitting ? ' coinflip-submit-btn--loading' : ''}`}
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {isSubmitting ? (
              <>
                <span className="coinflip-spinner" />
                Flipping...
              </>
            ) : (
              'Flip!'
            )}
          </button>

          {/* ── Info ─────────────────────────────────────────────── */}
          <div className="coinflip-info">
            <span className="coinflip-info-item">
              Odds: <strong>50/50</strong>
            </span>
            <span className="coinflip-info-item">
              House Edge: <strong>3%</strong>
            </span>
            <span className="coinflip-info-item">
              Win Payout: <strong>{PAYOUT_MULTIPLIER.toFixed(2)}x</strong>
            </span>
          </div>
        </div>
      </div>

      {/* ── Error ────────────────────────────────────────────────── */}
      {error && <div className="coinflip-error">{error}</div>}

      {/* ── Pending Bet ──────────────────────────────────────────── */}
      {pendingBet && (
        <div className="coinflip-pending">
          <div className="coinflip-pending-title">
            <span className="coinflip-pending-spinner" />
            Bet Pending Confirmation
          </div>
          <div className="coinflip-pending-row">
            <span className="coinflip-pending-row-label">Bet ID</span>
            <span className="coinflip-pending-row-value">{pendingBet.betId.slice(0, 16)}...</span>
          </div>
          <div className="coinflip-pending-row">
            <span className="coinflip-pending-row-label">Amount</span>
            <span className="coinflip-pending-row-value">{pendingBet.amount} ERG</span>
          </div>
          <div className="coinflip-pending-row">
            <span className="coinflip-pending-row-label">Choice</span>
            <span className="coinflip-pending-row-value">{pendingBet.choiceLabel}</span>
          </div>
          <div className="coinflip-pending-row">
            <span className="coinflip-pending-row-label">TX</span>
            <a
              className="coinflip-pending-link"
              href={getExplorerTxUrl(pendingBet.txId)}
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

export default CoinFlipGame;