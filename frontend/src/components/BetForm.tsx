import { useState, useCallback, useRef, TouchEvent } from 'react';
import { useWallet } from '../contexts/WalletContext';
import { generateSecret, bytesToHex, sha256 } from '../utils/crypto';
import { ergToNanoErg, formatErg } from '../utils/ergo';
import { buildApiUrl } from '../utils/network';
import './BetForm.css';

// ─── Helpers (until utils are expanded) ─────────────────────────────

function generateBetId(): string {
  return crypto.randomUUID();
}

async function generateCommitment(
  secret: Uint8Array,
  choice: number
): Promise<string> {
  // commitment = SHA256(secret_8bytes || choice_1byte)
  const buf = new Uint8Array(secret.length + 1);
  buf.set(secret, 0);
  buf[secret.length] = choice;
  const hash = await sha256(buf);
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

export default function BetForm() {
  const { isConnected, walletAddress, connect } = useWallet();

  const [amount, setAmount] = useState('');
  const [choice, setChoice] = useState<0 | 1 | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
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
      const commitment = await generateCommitment(secret, choice);
      const betId = generateBetId();
      const secretHex = bytesToHex(secret);

      // 2. Build API request
      const payload = {
        address: walletAddress,
        amount: amountNanoErg,
        choice,
        commitment,
        secret: secretHex,
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

      // 4. Show pending state
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
      <div className="bf-container">
        <div className="bf-connect-prompt">
          <p>Connect your wallet to start flipping</p>
          <button className="bf-connect-btn" onClick={connect}>
            Connect Wallet
          </button>
        </div>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className="bf-container">
      <h2 className="bf-title">Coin Flip</h2>

      {/* ── Amount Input ──────────────────────────────────────────── */}
      <div 
        className="bf-amount-section bf-touch-area"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <label className="bf-amount-label">Bet Amount</label>
        <div className="bf-amount-input-row">
          <input
            className="bf-amount-input"
            type="text"
            inputMode="decimal"
            placeholder="0.0"
            value={amount}
            onChange={(e) => handleAmountChange(e.target.value)}
            disabled={isSubmitting}
          />
          <span className="bf-amount-suffix">ERG</span>
        </div>
        <div className="bf-quick-picks">
          {QUICK_PICK_VALUES.map((val) => (
            <button
              key={val}
              className="bf-quick-pick"
              onClick={() => handleQuickPick(val.toString())}
              disabled={isSubmitting}
            >
              {val} ERG
            </button>
          ))}
        </div>
        {isValidAmount && (
          <div className="bf-payout-preview">
            Potential payout: <span>{payoutPreview} ERG</span>
          </div>
        )}
      </div>

      {/* ── Choice Buttons ────────────────────────────────────────── */}
      <div className="bf-choice-section">
        <span className="bf-choice-label">Pick Your Side</span>
        <div className="bf-choice-buttons">
          <button
            className={`bf-choice-btn bf-choice-btn--heads${
              choice === 0 ? ' bf-choice-btn--selected' : ''
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
            className={`bf-choice-btn bf-choice-btn--tails${
              choice === 1 ? ' bf-choice-btn--selected' : ''
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

      {/* ── Submit ───────────────────────────────────────────────── */}
      <button
        className={`bf-submit-btn${isSubmitting ? ' bf-submit-btn--loading' : ''}`}
        onClick={handleSubmit}
        disabled={!canSubmit}
      >
        {isSubmitting ? (
          <>
            <span className="bf-spinner" />
            Flipping...
          </>
        ) : (
          'Flip!'
        )}
      </button>

      {/* ── Error ────────────────────────────────────────────────── */}
      {error && <div className="bf-error">{error}</div>}

      {/* ── Pending Bet ──────────────────────────────────────────── */}
      {pendingBet && (
        <div className="bf-pending">
          <div className="bf-pending-title">
            <span className="bf-pending-spinner" />
            Bet Pending Confirmation
          </div>
          <div className="bf-pending-row">
            <span className="bf-pending-row-label">Bet ID</span>
            <span className="bf-pending-row-value">{pendingBet.betId.slice(0, 16)}...</span>
          </div>
          <div className="bf-pending-row">
            <span className="bf-pending-row-label">Amount</span>
            <span className="bf-pending-row-value">{pendingBet.amount} ERG</span>
          </div>
          <div className="bf-pending-row">
            <span className="bf-pending-row-label">Choice</span>
            <span className="bf-pending-row-value">{pendingBet.choiceLabel}</span>
          </div>
          <div className="bf-pending-row">
            <span className="bf-pending-row-label">TX</span>
            <a
              className="bf-pending-link"
              href={getExplorerTxUrl(pendingBet.txId)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {pendingBet.txId.slice(0, 16)}...
            </a>
          </div>
        </div>
      )}

      {/* ── Info ─────────────────────────────────────────────────── */}
      <div className="bf-info">
        <span className="bf-info-item">
          Odds: <strong>50/50</strong>
        </span>
        <span className="bf-info-item">
          House Edge: <strong>3%</strong>
        </span>
        <span className="bf-info-item">
          Win Payout: <strong>{PAYOUT_MULTIPLIER.toFixed(2)}x</strong>
        </span>
      </div>
    </div>
  );
}
