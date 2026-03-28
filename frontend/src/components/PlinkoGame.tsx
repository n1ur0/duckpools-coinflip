import { useState, useCallback, useEffect, useRef } from 'react';
import { useWallet } from '../contexts/WalletContext';
import {
  PLINKO_ROWS,
  getPlinkoMultiplier,
  getPlinkoAdjustedMultiplier,
  getPlinkoZoneProbability,
  getPlinkoZones,
  calculatePlinkoPayout,
  generatePlinkoCommit,
  computePlinkoRng,
  getPlinkoPath,
  isPlinkoWin,
  encodeIntConstant,
  encodeLongConstant,
  encodeCollByte,
} from '../utils/plinko';
import { bytesToHex } from '../utils/crypto';
import { ergToNanoErg, formatErg } from '../utils/ergo';
import { buildApiUrl } from '../utils/network';
import './PlinkoGame.css';

// ─── Helpers ─────────────────────────────────────────────────────

function generateBetId(): string {
  return crypto.randomUUID();
}

const HOUSE_EDGE = 0.03;

// ─── Component ─────────────────────────────────────────────────────

export default function PlinkoGame() {
  const { isConnected, walletAddress, connect } = useWallet();

  const [amount, setAmount] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingBet, setPendingBet] = useState<{
    txId: string;
    betId: string;
    amount: string;
    path: Array<'left' | 'right'>;
  } | null>(null);

  // Animation state
  const [currentPath, setCurrentPath] = useState<Array<'left' | 'right'> | null>(null);
  const [ballPosition, setBallPosition] = useState<{ row: number; offset: number } | null>(null);
  const [resultZone, setResultZone] = useState<number | null>(null);
  const [showResult, setShowResult] = useState(false);
  const animationRef = useRef<number | null>(null);

  // ── Validation ──────────────────────────────────────────────────

  const amountNanoErg = ergToNanoErg(amount);
  const isValidAmount = amount !== '' && !isNaN(parseFloat(amount)) && parseFloat(amount) > 0;
  const canSubmit = isConnected && isValidAmount && !isSubmitting && walletAddress !== undefined;

  const payoutPreview = isValidAmount
    ? formatErg(amountNanoErg * BigInt(Math.round(PLINKO_MIN_MULTIPLIER * (1 - HOUSE_EDGE))))
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

  // Simulate drop animation for preview
  const handlePreviewDrop = useCallback(async () => {
    if (currentPath) return;

    // Generate random path for preview
    const previewPath: Array<'left' | 'right'> = Array.from({ length: PLINKO_ROWS }, () =>
      Math.random() < 0.5 ? 'left' : 'right'
    );
    setCurrentPath(previewPath);

    // Animate the drop
    let row = 0;
    let offset = 0; // -rows/2 to +rows/2

    const animate = () => {
      if (row >= PLINKO_ROWS) {
        setBallPosition(null);
        const zone = offset + Math.floor(PLINKO_ROWS / 2);
        setResultZone(zone);
        setShowResult(true);
        return;
      }

      const direction = previewPath[row];
      offset += direction === 'right' ? 0.5 : -0.5;

      setBallPosition({ row, offset });

      row++;
      animationRef.current = requestAnimationFrame(() => {
        setTimeout(animate, 150); // 150ms per row
      });
    };

    animate();
  }, [currentPath]);

  const resetAnimation = useCallback(() => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
    setCurrentPath(null);
    setBallPosition(null);
    setResultZone(null);
    setShowResult(false);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit || !walletAddress) return;

    resetAnimation();
    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Generate secret & commitment
      const { secret, commitment } = await generatePlinkoCommit();
      const betId = generateBetId();
      const secretHex = bytesToHex(secret);

      // 2. Build API request
      const payload = {
        address: walletAddress,
        amount: amountNanoErg,
        commitment,
        secret: secretHex,
        betId,
        gameType: 'plinko',
      };

      // 3. Submit to backend
      const res = await fetch(buildApiUrl('/plinko/place-bet'), {
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
        path: [], // Will be populated after reveal
      });

      // Reset form
      setAmount('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to place bet';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [canSubmit, walletAddress, amountNanoErg, amount, resetAnimation]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className="plinko-container">
        <div className="plinko-connect-prompt">
          <p>Connect your wallet to play Plinko</p>
          <button className="plinko-connect-btn" onClick={connect}>
            Connect Wallet
          </button>
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────

  return (
    <div className="plinko-container">
      <h2 className="plinko-title">Plinko</h2>

      {/* ── Amount Input ──────────────────────────────────────────── */}
      <div className="plinko-amount-section">
        <label className="plinko-amount-label">Bet Amount</label>
        <div className="plinko-amount-input-row">
          <input
            className="plinko-amount-input"
            type="text"
            inputMode="decimal"
            placeholder="0.0"
            value={amount}
            onChange={(e) => handleAmountChange(e.target.value)}
            disabled={isSubmitting}
          />
          <span className="plinko-amount-suffix">ERG</span>
        </div>
        <div className="plinko-quick-picks">
          {[0.1, 0.5, 1, 5].map((val) => (
            <button
              key={val}
              className="plinko-quick-pick"
              onClick={() => handleQuickPick(val.toString())}
              disabled={isSubmitting}
            >
              {val} ERG
            </button>
          ))}
        </div>
        {isValidAmount && (
          <div className="plinko-payout-preview">
            Min potential payout: <span>{payoutPreview} ERG</span>
          </div>
        )}
      </div>

      {/* ── Plinko Board ──────────────────────────────────────────── */}
      <div className="plinko-board-section">
        <button
          className="plinko-preview-btn"
          onClick={handlePreviewDrop}
          disabled={!!currentPath || isSubmitting}
        >
          {currentPath ? 'Dropping...' : 'Preview Drop'}
        </button>

        <div className="plinko-board">
          {/* Peg rows */}
          <div className="plinko-pegs">
            {Array.from({ length: PLINKO_ROWS }, (_, row) => (
              <div key={`row-${row}`} className="plinko-peg-row">
                {Array.from({ length: row + 1 }, (_, col) => (
                  <div key={`peg-${row}-${col}`} className="plinko-peg" />
                ))}
              </div>
            ))}
          </div>

          {/* Ball animation */}
          {ballPosition && (
            <div
              className="plinko-ball"
              style={{
                top: `${ballPosition.row * 40}px`,
                left: `calc(50% + ${ballPosition.offset * 40}px - 10px)`,
              }}
            />
          )}

          {/* Landing zones */}
          <div className="plinko-zones">
            {getPlinkoZones().map(({ zone, multiplier, probability }) => (
              <div
                key={`zone-${zone}`}
                className={`plinko-zone ${showResult && resultZone === zone ? 'plinko-zone--win' : ''}`}
              >
                <div className="plinko-zone-multiplier">{multiplier.toFixed(1)}x</div>
                <div className="plinko-zone-probability">{probability.toFixed(2)}%</div>
              </div>
            ))}
          </div>
        </div>

        {showResult && resultZone !== null && (
          <div className="plinko-result">
            <h3>Result</h3>
            <p>
              Ball landed in zone {resultZone} ({getPlinkoMultiplier(resultZone)}x)
            </p>
            <p>Multiplier: {getPlinkoAdjustedMultiplier(resultZone).toFixed(2)}x</p>
            <button className="plinko-reset-btn" onClick={resetAnimation}>
              Reset
            </button>
          </div>
        )}
      </div>

      {/* ── Submit ───────────────────────────────────────────────── */}
      <button
        className={`plinko-submit-btn${isSubmitting ? ' plinko-submit-btn--loading' : ''}`}
        onClick={handleSubmit}
        disabled={!canSubmit || !!currentPath}
      >
        {isSubmitting ? (
          <>
            <span className="plinko-spinner" />
            Placing bet...
          </>
        ) : (
          'Drop!'
        )}
      </button>

      {/* ── Error ────────────────────────────────────────────────── */}
      {error && <div className="plinko-error">{error}</div>}

      {/* ── Pending Bet ──────────────────────────────────────────── */}
      {pendingBet && (
        <div className="plinko-pending">
          <div className="plinko-pending-title">
            <span className="plinko-pending-spinner" />
            Bet Pending Confirmation
          </div>
          <div className="plinko-pending-row">
            <span className="plinko-pending-row-label">Bet ID</span>
            <span className="plinko-pending-row-value">{pendingBet.betId.slice(0, 16)}...</span>
          </div>
          <div className="plinko-pending-row">
            <span className="plinko-pending-row-label">Amount</span>
            <span className="plinko-pending-row-value">{pendingBet.amount} ERG</span>
          </div>
          <div className="plinko-pending-row">
            <span className="plinko-pending-row-label">TX</span>
            <a
              className="plinko-pending-link"
              href={`https://explorer.ergoplatform.com/en/transactions/${pendingBet.txId}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {pendingBet.txId.slice(0, 16)}...
            </a>
          </div>
        </div>
      )}

      {/* ── Info ─────────────────────────────────────────────────── */}
      <div className="plinko-info">
        <span className="plinko-info-item">
          Rows: <strong>{PLINKO_ROWS}</strong>
        </span>
        <span className="plinko-info-item">
          Zones: <strong>{PLINKO_ROWS + 1}</strong>
        </span>
        <span className="plinko-info-item">
          House Edge: <strong>{(HOUSE_EDGE * 100).toFixed(1)}%</strong>
        </span>
      </div>
    </div>
  );
}
