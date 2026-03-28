import { useState, useCallback, useRef, TouchEvent } from 'react';
import { useWallet } from '../../contexts/WalletContext';
import CoinFlip from '../../components/animations/CoinFlip';
import { Button, Input } from '../../components/ui';
import { bytesToHex, blake2b256, generateSecret } from '../../utils/crypto';
import { ergToNanoErg, formatErg } from '../../utils/ergo';
import { buildApiUrl } from '../../utils/network';
import { isOnChainEnabled } from '../../config/contract';
import { buildPlaceBetTx, verifyCommitment } from '../../services/coinflipService';
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

// ─── Component ──────────────────────────────────────────────────────

interface CoinFlipGameProps {
  className?: string;
}

const CoinFlipGame: React.FC<CoinFlipGameProps> = ({ className = '' }) => {
  const { isConnected, walletAddress, connect, signTransaction, submitTransaction, getUtxos, getCurrentHeight, getChangeAddress } = useWallet();

  const [amount, setAmount] = useState('');
  const [choice, setChoice] = useState<0 | 1 | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFlipping, setIsFlipping] = useState(false);
  const [result, setResult] = useState<'heads' | 'tails' | null>(null);
  const [winOutcome, setWinOutcome] = useState<'win' | 'loss' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [betPlaced, setBetPlaced] = useState<{
    betId: string;
    amount: string;
    choiceLabel: string;
    commitment: string;
    txId?: string;
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

      // Sanity-check commitment (should always pass)
      if (!verifyCommitment(secret, choice, commitment)) {
        throw new Error('Commitment verification failed — internal error');
      }

      let txId = '';

      if (isOnChainEnabled()) {
        // ── ON-CHAIN FLOW ──────────────────────────────────────
        // Build unsigned EIP-12 transaction using Fleet SDK,
        // then sign via Nautilus and broadcast.

        const [utxos, currentHeight, changeAddressRaw] = await Promise.all([
          getUtxos(),
          getCurrentHeight(),
          getChangeAddress(),
        ]);

        const changeAddress = changeAddressRaw ?? walletAddress;
        if (!changeAddress) {
          throw new Error('Could not get change address from wallet');
        }

        if (utxos.length === 0) {
          throw new Error('No UTXOs available in wallet. Fund your wallet first.');
        }

        // TODO: Get player's compressed public key from wallet.
        //       EIP-12 doesn't expose this directly. Options:
        //       (a) Derive from first UTXO's ergoTree (P2PK: 0008cd<pk>)
        //       (b) Backend provides player pub key lookup
        //       (c) Use sign_data to get a signature, derive pub key
        // For now, extract from first UTXO's ergoTree if P2PK.
        const playerPubKey = extractPubKeyFromUtxo(utxos[0]);
        if (!playerPubKey) {
          throw new Error(
            'Could not determine player public key. Ensure your UTXO is a P2PK address.'
          );
        }

        const { unsignedTx, timeoutHeight } = await buildPlaceBetTx({
          changeAddress,
          amountNanoErg: BigInt(amountNanoErg),
          playerPubKey,
          commitment,
          choice,
          secret,
          betId,
          currentHeight,
          utxos: utxos as any, // Fleet SDK Box type compat
        });

        // 2. Sign via Nautilus — THIS triggers the wallet popup
        const signedTx = await signTransaction(unsignedTx as any);
        if (!signedTx) {
          throw new Error('Transaction signing was rejected or failed');
        }

        // 3. Broadcast to the Ergo network
        txId = (await submitTransaction(signedTx as any)) ?? '';
        if (!txId) {
          throw new Error('Transaction broadcast failed');
        }

        console.log(`[CoinFlip] On-chain bet placed: txId=${txId}, timeout=${timeoutHeight}`);
      } else {
        // ── OFF-CHAIN FALLBACK ─────────────────────────────────
        // Contract not compiled yet (MAT-344 blocker).
        // Send to backend for in-memory tracking only.
        // No real ERG moves — this is frontend theater.

        const payload = {
          address: walletAddress,
          amount: amountNanoErg,
          choice,
          commitment,
          betId,
        };

        const res = await fetch(buildApiUrl('/place-bet'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const data = await res.json();

        if (!res.ok || !data.success) {
          throw new Error(data.error || `Server error ${res.status}`);
        }

        console.warn(
          '[CoinFlip] OFF-CHAIN MODE — contract not compiled yet (MAT-344). ' +
          'No real ERG was moved. Outcome cannot be determined on-chain.'
        );
      }

      // 4. Show "Bet Placed — Pending On-Chain Reveal" state.
      // NO Math.random() — outcomes come from on-chain reveal.
      setBetPlaced({
        betId,
        amount,
        choiceLabel: choice === 0 ? 'Heads' : 'Tails',
        commitment,
        txId: txId || undefined,
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
  }, [canSubmit, choice, walletAddress, amountNanoErg, amount, signTransaction, submitTransaction, getUtxos, getCurrentHeight, getChangeAddress]);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className={`coinflip-game-container ${className}`}>
        <div className="coinflip-connect-prompt">
          <p>Connect your wallet to start flipping</p>
          <Button 
            className="coinflip-connect-btn" 
            onClick={connect}
            variant="primary"
            size="lg"
          >
            Connect Wallet
          </Button>
        </div>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className={`coinflip-game-container ${className}`}>
      <h2 className="coinflip-title">Coin Flip</h2>

      {!isOnChainEnabled() && (
        <div className="coinflip-offchain-banner">
          ⚠️ Off-chain mode — contract not yet deployed (MAT-344)
        </div>
      )}

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
              {!isFlipping && result && (
                <div className="coinflip-result-section">
                  {/* Enhanced result display with icon */}
                  <div className={`coinflip-result-wrapper ${result}`}>
                    <div className={`coinflip-result-icon ${result}`}>
                      {result === 'heads' ? '◉' : '◎'}
                    </div>
                    <div className={`coinflip-result-text ${result}`}>
                      {result === 'heads' ? 'HEADS' : 'TAILS'}
                    </div>
                  </div>
                  
                  {/* Enhanced win/loss outcome with bet amount */}
                  {winOutcome && (
                    <div className={`coinflip-outcome ${winOutcome}`}>
                      <div className="coinflip-outcome-icon">
                        {winOutcome === 'win' ? '✦' : '✕'}
                      </div>
                      <div className="coinflip-outcome-text">
                        {winOutcome === 'win' ? 'YOU WIN!' : 'YOU LOSE'}
                      </div>
                      {betPlaced && (
                        <div className="coinflip-bet-amount">
                          Bet: {betPlaced.amount} ERG
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ── Choice Buttons ───────────────────────────────────── */}
          <div className="coinflip-choice-section">
            <span className="coinflip-choice-label">Pick Your Side</span>
            <div className="coinflip-choice-buttons">
              <Button
                className={`coinflip-choice-btn coinflip-choice-btn--heads${
                  choice === 0 ? ' coinflip-choice-btn--selected' : ''
                }`}
                variant={choice === 0 ? "primary" : "secondary"}
                onClick={() => {
                  setChoice(0);
                  setError(null);
                }}
                disabled={isSubmitting}
                fullWidth
              >
                Heads
              </Button>
              <Button
                className={`coinflip-choice-btn coinflip-choice-btn--tails${
                  choice === 1 ? ' coinflip-choice-btn--selected' : ''
                }`}
                variant={choice === 1 ? "primary" : "secondary"}
                onClick={() => {
                  setChoice(1);
                  setError(null);
                }}
                disabled={isSubmitting}
                fullWidth
              >
                Tails
              </Button>
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
            <Input
              className="coinflip-amount-input"
              type="text"
              inputMode="decimal"
              placeholder="0.0"
              value={amount}
              onChange={(e) => handleAmountChange(e.target.value)}
              disabled={isSubmitting}
              suffix="ERG"
              error={error || undefined}
            />
            <div className="coinflip-quick-picks">
              {QUICK_PICK_VALUES.map((val) => (
                <Button
                  key={val}
                  className="coinflip-quick-pick"
                  variant="ghost"
                  size="sm"
                  onClick={() => handleQuickPick(val.toString())}
                  disabled={isSubmitting}
                >
                  {val} ERG
                </Button>
              ))}
            </div>
            {isValidAmount && (
              <div className="coinflip-payout-preview">
                Potential payout: <span>{payoutPreview} ERG</span>
              </div>
            )}
          </div>

          {/* ── Submit ─────────────────────────────────────────────── */}
          <Button
            className={`coinflip-submit-btn${isSubmitting ? ' coinflip-submit-btn--loading' : ''}`}
            variant="primary"
            size="lg"
            onClick={handleSubmit}
            disabled={!canSubmit}
            loading={isSubmitting}
            fullWidth
          >
            {isSubmitting
              ? isOnChainEnabled() ? 'Signing...' : 'Flipping...'
              : 'Flip!'}
          </Button>

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

      {/* ── Result Actions (for when on-chain reveal completes) ─── */}
      {!isFlipping && result && winOutcome && (
        <div className="coinflip-result-actions">
          <button
            className="coinflip-flip-again-btn"
            onClick={() => {
              setResult(null);
              setWinOutcome(null);
              setBetPlaced(null);
              setError(null);
            }}
          >
            Flip Again
          </button>
        </div>
      )}

      {/* ── Bet Placed — Pending On-Chain Reveal ─────────────── */}
      {betPlaced && !result && (
        <div className="coinflip-pending">
          <div className="coinflip-pending-title">
            <span className="coinflip-pending-spinner" />
            Bet Placed — Awaiting On-Chain Reveal
          </div>
          <div className="coinflip-pending-row">
            <span className="coinflip-pending-row-label">Bet ID</span>
            <span className="coinflip-pending-row-value">{betPlaced.betId.slice(0, 16)}...</span>
          </div>
          <div className="coinflip-pending-row">
            <span className="coinflip-pending-row-label">Amount</span>
            <span className="coinflip-pending-row-value">{betPlaced.amount} ERG</span>
          </div>
          <div className="coinflip-pending-row">
            <span className="coinflip-pending-row-label">Choice</span>
            <span className="coinflip-pending-row-value">{betPlaced.choiceLabel}</span>
          </div>
          <div className="coinflip-pending-row">
            <span className="coinflip-pending-row-label">Commitment</span>
            <span className="coinflip-pending-row-value">{betPlaced.commitment.slice(0, 16)}...</span>
          </div>
          {betPlaced.txId && (
            <div className="coinflip-pending-row">
              <span className="coinflip-pending-row-label">Transaction</span>
              <span className="coinflip-pending-row-value">
                <a
                  href={`https://explorer.ergoplatform.com/en/transactions/${betPlaced.txId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="coinflip-tx-link"
                >
                  {betPlaced.txId.slice(0, 16)}...
                </a>
              </span>
            </div>
          )}
          <div className="coinflip-pending-note">
            {isOnChainEnabled()
              ? 'Outcome will be revealed on-chain when the house processes the bet.'
              : '⚠️ Off-chain mode — no real transaction was broadcast (MAT-344).'}
          </div>
          <button
            className="coinflip-flip-again-btn"
            onClick={() => {
              setBetPlaced(null);
              setError(null);
            }}
          >
            Place Another Bet
          </button>
        </div>
      )}
    </div>
  );
};

// ── Utility: Extract player public key from P2PK UTXO ──────────────

/**
 * Extract the 33-byte compressed public key from a P2PK UTXO's ergoTree.
 *
 * P2PK ErgoTree format: 0008cd<33-byte-pk>
 * The public key is bytes 4..37 of the ergoTree hex string.
 *
 * Returns null if the UTXO is not a standard P2PK box.
 */
function extractPubKeyFromUtxo(utxo: { ergoTree?: string }): string | null {
  const tree = utxo.ergoTree;
  if (!tree || tree.length < 74) return null; // 4 + 66 hex chars minimum
  if (tree.startsWith('0008cd')) {
    return tree.slice(4, 4 + 66); // 33 bytes = 66 hex chars
  }
  return null;
}

export default CoinFlipGame;
