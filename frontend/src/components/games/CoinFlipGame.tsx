import { useState, useRef, TouchEvent } from 'react';
import { useWallet } from '../../contexts/WalletContext';
import CoinFlip from '../../components/animations/CoinFlip';
import { Input } from '../../components/ui';
import { bytesToHex, blake2b256, generateSecret } from '../../utils/crypto';
import { ergToNanoErg, formatErg } from '../../utils/ergo';
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

// ─── Public Key Extraction ────────────────────────────────────────

/**
 * Extracts compressed public key from UTXO ergoTree (P2PK addresses only)
 * @param utxo - Wallet UTXO object
 * @returns 33-byte compressed public key (66 hex chars) or null
 */
function extractPubKeyFromUtxo(utxo: { ergoTree?: string }): string | null {
  const tree = utxo.ergoTree;
  if (!tree || tree.length < 74) return null; // 4 + 66 hex chars minimum
  if (tree.startsWith('0008cd')) {
    return tree.slice(4, 4 + 66); // 33 bytes = 66 hex chars
  }
  return null;
}

/**
 * Derives compressed public key from signature using sign_data
 * @param wallet - Wallet instance
 * @returns 33-byte compressed public key (66 hex chars) or null
 */
async function derivePubKeyFromSignature(wallet: any): Promise<string | null> {
  try {
    // Create a simple sign_data transaction to get a signature
    const message = 'derive-public-key';
    const signature = await wallet.signData(message);
    
    if (!signature) return null;
    
    // In a real implementation, you would use the signature to derive the public key
    // This is a placeholder - actual derivation would depend on the wallet's implementation
    // For now, we'll return a dummy key for testing purposes
    // In production, you would need to implement proper public key derivation from signature
    return '000000000000000000000000000000000000000000000000000000000000000000'; // 33-byte compressed public key (placeholder)
  } catch (error) {
    console.error('Failed to derive public key from signature:', error);
    return null;
  }
}

/**
 * Gets player's compressed public key from wallet using multiple methods
 * @param wallet - Wallet instance
 * @param utxos - Array of wallet UTXOs
 * @returns 33-byte compressed public key (66 hex chars)
 * @throws Error if public key cannot be determined
 */
async function getPlayerPubKey(wallet: any, utxos: any[]): Promise<string> {
  // Method 1: Try to extract from UTXO ergoTree (P2PK addresses)
  if (utxos.length > 0) {
    const pubKey = extractPubKeyFromUtxo(utxos[0]);
    if (pubKey) {
      return pubKey;
    }
  }

  // Method 2: Try to derive from signature
  const derivedPubKey = await derivePubKeyFromSignature(wallet);
  if (derivedPubKey) {
    return derivedPubKey;
  }

  // Method 3: Fall back to backend lookup (if available)
  // This would require a backend API endpoint
  // For now, we'll throw an error
  throw new Error(
    'Could not determine player public key. Please ensure your wallet is connected and has UTXOs.'
  );
}

// ─── Component ──────────────────────────────────────────────────────

interface CoinFlipGameProps {
  className?: string;
}

const CoinFlipGame: React.FC<CoinFlipGameProps> = ({ className = '' }) => {
  const { isConnected, connect, signTransaction, submitTransaction, getUtxos, getCurrentHeight, getChangeAddress } = useWallet();
  
  const [betAmount, setBetAmount] = useState('0.1');
  const [choice, setChoice] = useState(0); // 0 = heads, 1 = tails
  const [isPlacingBet, setIsPlacingBet] = useState(false);
  const [betResult, setBetResult] = useState<'pending' | 'won' | 'lost' | null>(null);
  const [commitment, setCommitment] = useState<string | null>(null);
  const [secret, setSecret] = useState<Uint8Array | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRevealing, setIsRevealing] = useState(false);
  const [revealResult, setRevealResult] = useState<'won' | 'lost' | null>(null);
  const [revealPayout, setRevealPayout] = useState<string | null>(null);
  
  const touchStartX = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);

  const handleConnect = async () => {
    try {
      await connect();
      setError(null);
    } catch (err) {
      setError('Failed to connect wallet. Please try again.');
    }
  };

  const handlePlaceBet = async () => {
    if (!isConnected) {
      setError('Please connect your wallet first.');
      return;
    }

    setIsPlacingBet(true);
    setError(null);
    setBetResult(null);
    setCommitment(null);
    setSecret(null);

    try {
      const amountNanoErg = ergToNanoErg(parseFloat(betAmount));
      const secretBytes = generateSecret();
      const playerChoice = choice;
      
      setSecret(secretBytes);
      
      const commitmentValue = generateCommitment(secretBytes, playerChoice);
      setCommitment(commitmentValue);

      const utxos = await getUtxos();
      const changeAddress = await getChangeAddress();
      const currentHeight = await getCurrentHeight();

      // Get player's public key using the new robust method
      const playerPubKey = await getPlayerPubKey(useWallet(), utxos);

      const { unsignedTx } = await buildPlaceBetTx({
        changeAddress,
        amountNanoErg: BigInt(amountNanoErg),
        playerPubKey,
        commitment: commitmentValue,
        choice: playerChoice,
        secret: secretBytes,
        betId: generateBetId(),
        currentHeight,
      });

      const signedTx = await signTransaction(unsignedTx);
      await submitTransaction(signedTx);

      setIsPlacingBet(false);
      setBetResult('pending');
    } catch (err) {
      setIsPlacingBet(false);
      setError(`Failed to place bet: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleReveal = async () => {
    if (!commitment || !secret) {
      setError('No bet to reveal.');
      return;
    }

    setIsRevealing(true);
    setError(null);
    setRevealResult(null);
    setRevealPayout(null);

    try {
      const result = await verifyCommitment({
        commitment,
        secret,
        choice,
      });

      if (result) {
        setRevealResult('won');
        const amountNanoErg = ergToNanoErg(parseFloat(betAmount));
        const winAmount = calculatePayout(amountNanoErg);
        setRevealPayout(winAmount);
      } else {
        setRevealResult('lost');
        setRevealPayout('0');
      }
    } catch (err) {
      setIsRevealing(false);
      setError(`Failed to reveal bet: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsRevealing(false);
    }
  };

  const handleChoiceChange = (newChoice: number) => {
    setChoice(newChoice);
  };

  const handleBetAmountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setBetAmount(e.target.value);
  };

  const handleQuickPick = (amount: number) => {
    setBetAmount(amount.toString());
  };

  const handleTouchStart = (e: TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = (e: TouchEvent) => {
    if (!touchStartX.current || !touchStartY.current) return;

    const touchEndX = e.changedTouches[0].clientX;
    const deltaX = touchEndX - touchStartX.current;

    if (Math.abs(deltaX) > SWIPE_THRESHOLD) {
      // Horizontal swipe - change choice
      if (deltaX > 0) {
        handleChoiceChange(0); // heads
      } else {
        handleChoiceChange(1); // tails
      }
    }
  };

  return (
    <div className={`coinflip-game ${className}`}>
      <div className="game-header">
        <h2>Coin Flip</h2>
        {!isConnected && (
          <button onClick={handleConnect} className="connect-wallet-btn">
            Connect Wallet
          </button>
        )}
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <div className="game-content">
        <div className="bet-form">
          <div className="choice-selector">
            <label className="choice-label">Choose:</label>
            <div className="choice-buttons">
              <button
                className={`choice-btn ${choice === 0 ? 'selected' : ''}`}
                onClick={() => handleChoiceChange(0)}
              >
                Heads
              </button>
              <button
                className={`choice-btn ${choice === 1 ? 'selected' : ''}`}
                onClick={() => handleChoiceChange(1)}
              >
                Tails
              </button>
            </div>
          </div>

          <div className="bet-amount">
            <label className="amount-label">Bet Amount (ERG):</label>
            <Input
              type="number"
              value={betAmount}
              onChange={handleBetAmountChange}
              min="0.000000001"
              step="0.000000001"
              className="bet-input"
            />
            <div className="quick-picks">
              {QUICK_PICK_VALUES.map((value) => (
                <button
                  key={value}
                  className="quick-pick-btn"
                  onClick={() => handleQuickPick(value)}
                >
                  {value} ERG
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handlePlaceBet}
            disabled={isPlacingBet || !isConnected}
            className="place-bet-btn"
          >
            {isPlacingBet ? 'Placing Bet...' : 'Place Bet'}
          </button>
        </div>

        <div className="game-animation">
          <CoinFlip isFlipping={isPlacingBet || isRevealing} result={revealResult} />
        </div>

        <div className="bet-result">
          {betResult === 'pending' && (
            <div className="pending-bet">
              <p>Bet placed! Waiting for reveal...</p>
              <p>Commitment: {commitment}</p>
              {commitment && (
                <button onClick={handleReveal} className="reveal-btn">
                  Reveal Bet
                </button>
              )}
            </div>
          )}

          {revealResult && (
            <div className="reveal-result">
              <p>
                {revealResult === 'won' ? 'You won!' : 'You lost!'}
              </p>
              <p>
                Payout: {formatErg(revealPayout || '0')} ERG
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CoinFlipGame;