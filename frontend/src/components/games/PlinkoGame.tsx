import { useState, useCallback, useRef, useEffect } from 'react';
import { useWallet } from '../../contexts/WalletContext';
import {
  PLINKO_MIN_ROWS,
  PLINKO_MAX_ROWS,
  PLINKO_DEFAULT_ROWS,
  getPlinkoSlotMultiplier,
  getPlinkoMultiplierTable,
  generatePlinkoCommit,
  calculatePlinkoPayout,
} from '../../utils/plinko';
import { ergToNanoErg, formatErg } from '../../utils/ergo';
import { buildApiUrl } from '../../utils/network';
import './PlinkoGame.css';

// Quick pick values for bet amounts
const QUICK_PICK_VALUES = [0.1, 0.5, 1, 5];

// Physics constants
const GRAVITY = 0.3;
const BALL_RADIUS = 8;
const PEG_RADIUS = 4;
const BOUNCE_DAMPING = 0.7; // Energy loss on bounce
const FRICTION = 0.99; // Air resistance
const MIN_VELOCITY = 0.1; // Minimum velocity threshold
const MAX_BOUNCE_ANGLE = Math.PI / 3; // Maximum bounce angle in radians

function generateBetId(): string {
  return crypto.randomUUID();
}

interface BallPosition {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface PegPosition {
  x: number;
  y: number;
}

interface Slot {
  index: number;
  multiplier: number;
  color: string;
}

interface PlinkoGameProps {
  className?: string;
}

/**
 * Plinko Game Component with Physics Animation
 *
 * Player selects number of rows (8-16) and bets on where the ball will land.
 * More rows = higher risk = higher potential payout.
 */
const PlinkoGame: React.FC<PlinkoGameProps> = ({ className = '' }) => {
  const { isConnected, walletAddress, connect } = useWallet();

  const [amount, setAmount] = useState('');
  const [rows, setRows] = useState(PLINKO_DEFAULT_ROWS);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingBet, setPendingBet] = useState<{
    txId: string;
    betId: string;
    amount: string;
    rows: number;
  } | null>(null);
  const [result, setResult] = useState<{
    slot: number;
    multiplier: number;
    payout: number;
  } | null>(null);

  // Animation state
  const [ballPosition, setBallPosition] = useState<BallPosition>({ x: 0, y: 0, vx: 0, vy: 0 });
  const [pegPositions, setPegPositions] = useState<PegPosition[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [boardWidth, setBoardWidth] = useState(300);
  const [boardHeight, setBoardHeight] = useState(400);
  
  const boardRef = useRef<HTMLDivElement>(null);
  const animationFrameRef = useRef<number>(0);

  // ── Initialization ────────────────────────────────────────────────

  useEffect(() => {
    // Generate peg positions based on number of rows
    const generatePegPositions = () => {
      const positions: PegPosition[] = [];
      const pegSpacing = boardWidth / (rows + 1);
      const rowSpacing = boardHeight / (rows + 2);
      
      for (let row = 1; row <= rows; row++) {
        const pegCount = row;
        const startY = row * rowSpacing;
        const startX = (boardWidth - (pegCount - 1) * pegSpacing) / 2;
        
        for (let col = 0; col < pegCount; col++) {
          positions.push({
            x: startX + col * pegSpacing,
            y: startY,
          });
        }
      }
      
      return positions;
    };

    // Generate slot information
    const generateSlots = () => {
      const multiplierTable = getPlinkoMultiplierTable(rows);
      
      return multiplierTable.map((multiplier, index) => {
        // Generate color based on multiplier (green for low, yellow for medium, red for high)
        let color = 'var(--accent-green)';
        if (multiplier > 3) color = 'var(--accent-yellow)';
        if (multiplier > 10) color = 'var(--accent-red)';
        
        return {
          index,
          multiplier,
          color,
        };
      });
    };

    // Initialize board
    if (boardRef.current) {
      setPegPositions(generatePegPositions());
      setSlots(generateSlots());
    }
  }, [rows, boardWidth, boardHeight]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (boardRef.current) {
        const width = Math.min(boardRef.current.clientWidth - 40, 400);
        const height = width * 1.2;
        setBoardWidth(width);
        setBoardHeight(height);
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // ── Validation ──────────────────────────────────────────────────

  const amountNanoErg = ergToNanoErg(amount);
  const isValidAmount =
    amount !== '' && !isNaN(parseFloat(amount)) && parseFloat(amount) > 0;
  const isValidRows = rows >= PLINKO_MIN_ROWS && rows <= PLINKO_MAX_ROWS;
  const canSubmit =
    isConnected &&
    isValidAmount &&
    isValidRows &&
    !isSubmitting &&
    !isAnimating &&
    walletAddress !== undefined;

  // Calculate potential payout
  const getPotentialPayout = () => {
    if (!isValidAmount) return '0.0000';
    // Use the average multiplier for display
    const avgMultiplier = 2.5; // Rough average multiplier
    return formatErg(Math.floor(Number(amountNanoErg) * avgMultiplier));
  };

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

  const handleRowsChange = useCallback(
    (value: string) => {
      const newRows = parseInt(value, 10);
      if (!isNaN(newRows) && newRows >= PLINKO_MIN_ROWS && newRows <= PLINKO_MAX_ROWS) {
        setRows(newRows);
        setError(null);
      }
    },
    []
  );

  // ── Physics Animation ─────────────────────────────────────────────

  const animateBallDrop = useCallback((finalSlot: number) => {
    setIsAnimating(true);
    setResult(null);
    
    // Initialize ball position at top center with slight random horizontal velocity
    let currentPos: BallPosition = {
      x: boardWidth / 2 + (Math.random() - 0.5) * 10,
      y: 20,
      vx: (Math.random() - 0.5) * 0.5,
      vy: 0,
    };
    
    // Store the target slot for final guidance
    const targetX = ((finalSlot + 0.5) / (rows + 1)) * boardWidth;
    
    // Physics helper functions
    const checkPegCollision = (ballPos: BallPosition, peg: PegPosition): boolean => {
      const dx = ballPos.x - peg.x;
      const dy = ballPos.y - peg.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      return distance < (BALL_RADIUS + PEG_RADIUS);
    };
    
    const handlePegBounce = (ballPos: BallPosition, peg: PegPosition): BallPosition => {
      // Calculate collision normal
      const dx = ballPos.x - peg.x;
      const dy = ballPos.y - peg.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      // Normalize collision vector
      const nx = dx / distance;
      const ny = dy / distance;
      
      // Calculate relative velocity along collision normal
      const relativeVelocity = ballPos.vx * nx + ballPos.vy * ny;
      
      // Don't bounce if velocities are separating
      if (relativeVelocity > 0) {
        return ballPos;
      }
      
      // Calculate new velocity with bounce damping
      const bounceFactor = -BOUNCE_DAMPING;
      const newVx = ballPos.vx + bounceFactor * relativeVelocity * nx;
      const newVy = ballPos.vy + bounceFactor * relativeVelocity * ny;
      
      // Limit bounce angle to prevent unrealistic bouncing
      const velocity = Math.sqrt(newVx * newVx + newVy * newVy);
      let angle = Math.atan2(newVy, newVx);
      
      // Constrain angle to reasonable range
      if (Math.abs(angle) > MAX_BOUNCE_ANGLE) {
        angle = Math.sign(angle) * MAX_BOUNCE_ANGLE;
      }
      
      // Apply angle constraint
      const constrainedVx = velocity * Math.cos(angle);
      const constrainedVy = velocity * Math.sin(angle);
      
      // Move ball outside of peg to prevent sticking
      const overlap = (BALL_RADIUS + PEG_RADIUS) - distance;
      const separateX = nx * overlap * 1.1;
      const separateY = ny * overlap * 1.1;
      
      return {
        x: ballPos.x + separateX,
        y: ballPos.y + separateY,
        vx: constrainedVx,
        vy: constrainedVy
      };
    };
    
    const applyBoundaryConstraints = (ballPos: BallPosition): BallPosition => {
      let { x, y, vx, vy } = ballPos;
      
      // Left and right wall collisions
      if (x - BALL_RADIUS < 0) {
        x = BALL_RADIUS;
        vx = Math.abs(vx) * BOUNCE_DAMPING;
      } else if (x + BALL_RADIUS > boardWidth) {
        x = boardWidth - BALL_RADIUS;
        vx = -Math.abs(vx) * BOUNCE_DAMPING;
      }
      
      // Apply gentle guidance toward target slot when near the bottom
      if (y > boardHeight * 0.7) {
        const guidanceForce = 0.002;
        const diffX = targetX - x;
        vx += diffX * guidanceForce;
      }
      
      return { x, y, vx, vy };
    };
    
    const animate = () => {
      // Apply gravity
      currentPos.vy += GRAVITY;
      
      // Apply friction
      currentPos.vx *= FRICTION;
      currentPos.vy *= FRICTION;
      
      // Update position
      currentPos.x += currentPos.vx;
      currentPos.y += currentPos.vy;
      
      // Apply boundary constraints
      currentPos = applyBoundaryConstraints(currentPos);
      
      // Check for peg collisions
      for (const peg of pegPositions) {
        if (checkPegCollision(currentPos, peg)) {
          currentPos = handlePegBounce(currentPos, peg);
        }
      }
      
      // Minimum velocity threshold to stop tiny movements
      if (Math.abs(currentPos.vx) < MIN_VELOCITY) {
        currentPos.vx = 0;
      }
      if (Math.abs(currentPos.vy) < MIN_VELOCITY && currentPos.y > boardHeight * 0.8) {
        currentPos.vy = 0;
      }
      
      // Check if ball reached bottom
      if (currentPos.y >= boardHeight - 30) {
        currentPos.y = boardHeight - 30;
        currentPos.vy = 0;
        currentPos.vx = 0;
        
        // Ball has landed
        setBallPosition(currentPos);
        
        // Show result after a short delay
        setTimeout(() => {
          setIsAnimating(false);
        }, 500);
        
        return;
      }
      
      setBallPosition(currentPos);
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    
    animationFrameRef.current = requestAnimationFrame(animate);
  }, [boardWidth, boardHeight, rows, pegPositions]);

  // ── Bet Submission ───────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    if (!canSubmit || !walletAddress) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Generate secret & commitment
      const { secret, commitment } = await generatePlinkoCommit(rows);
      const betId = generateBetId();

      // 2. Build API request
      // SECURITY (SEC-HIGH-2): NEVER send the secret to the backend.
      // The commit-reveal scheme requires the secret to remain private
      // until the on-chain reveal transaction. Only the commitment hash
      // is needed for bet placement.
      const payload = {
        address: walletAddress,
        amount: amountNanoErg,
        rows,
        commitment,
        betId,
      };
      // 3. Submit to backend
      const res = await fetch(buildApiUrl('/place-plinko-bet'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || `Server error ${res.status}`);
      }

      // 4. Simulate ball drop animation
      // For now, use a random slot - in production this would come from the blockchain
      const simulatedSlot = Math.floor(Math.random() * (rows + 1));
      const multiplier = getPlinkoSlotMultiplier(rows, simulatedSlot);
      const payout = calculatePlinkoPayout(Number(amountNanoErg), rows, simulatedSlot);
      
      setResult({
        slot: simulatedSlot,
        multiplier,
        payout,
      });
      
      // Start animation
      setTimeout(() => {
        animateBallDrop(simulatedSlot);
      }, 500);

      // 5. Show pending state
      setPendingBet({
        txId: data.txId,
        betId,
        amount,
        rows,
      });

      // Reset form
      setAmount('');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to place bet';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [canSubmit, rows, walletAddress, amountNanoErg, amount, animateBallDrop]);

  // ── Cleanup ─────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // ── Not connected ───────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className={`plinko-game-container ${className}`}>
        <div className="plinko-connect-prompt">
          <p>Connect your wallet to start playing</p>
          <button className="plinko-connect-btn" onClick={connect}>
            Connect Wallet
          </button>
        </div>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className={`plinko-game-container ${className}`}>
      <h2 className="plinko-title">Plinko Game</h2>

      {/* ── Game Board ─────────────────────────────────────────────── */}
      <div 
        ref={boardRef}
        className="plinko-board"
        style={{ width: boardWidth, height: boardHeight }}
      >
        {/* Pegs */}
        {pegPositions.map((peg, index) => (
          <div
            key={`peg-${index}`}
            className="plinko-peg"
            style={{
              left: peg.x - PEG_RADIUS,
              top: peg.y - PEG_RADIUS,
              width: PEG_RADIUS * 2,
              height: PEG_RADIUS * 2,
            }}
          />
        ))}
        
        {/* Ball */}
        <div
          className="plinko-ball"
          style={{
            left: ballPosition.x - BALL_RADIUS,
            top: ballPosition.y - BALL_RADIUS,
            width: BALL_RADIUS * 2,
            height: BALL_RADIUS * 2,
          }}
        />
        
        {/* Slots */}
        {slots.map((slot, index) => (
          <div
            key={`slot-${index}`}
            className="plinko-slot"
            style={{
              left: (index * boardWidth) / (rows + 1),
              bottom: 0,
              width: boardWidth / (rows + 1),
              backgroundColor: slot.color,
            }}
          >
            <span className="plinko-slot-multiplier">
              {slot.multiplier.toFixed(1)}x
            </span>
          </div>
        ))}
      </div>

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
            disabled={isSubmitting || isAnimating}
          />
          <span className="plinko-amount-suffix">ERG</span>
        </div>
        <div className="plinko-quick-picks">
          {QUICK_PICK_VALUES.map((val) => (
            <button
              key={val}
              className="plinko-quick-pick"
              onClick={() => handleQuickPick(val.toString())}
              disabled={isSubmitting || isAnimating}
            >
              {val} ERG
            </button>
          ))}
        </div>
        {isValidAmount && (
          <div className="plinko-payout-preview">
            Potential payout: <span>{getPotentialPayout()} ERG</span>
          </div>
        )}
      </div>

      {/* ── Rows Selector ─────────────────────────────────────────── */}
      <div className="plinko-rows-section">
        <label className="plinko-rows-label">
          Number of Rows: {rows}
        </label>
        <div className="plinko-rows-input-row">
          <input
            className="plinko-rows-input"
            type="range"
            min={PLINKO_MIN_ROWS}
            max={PLINKO_MAX_ROWS}
            value={rows}
            onChange={(e) => handleRowsChange(e.target.value)}
            disabled={isSubmitting || isAnimating}
          />
          <div className="plinko-rows-display">
            <span>{PLINKO_MIN_ROWS} (Low Risk)</span>
            <span>{PLINKO_MAX_ROWS} (High Risk)</span>
          </div>
        </div>
      </div>

      {/* ── Submit Button ──────────────────────────────────────────── */}
      <button
        className={`plinko-submit-btn${isSubmitting ? ' plinko-submit-btn--loading' : ''}`}
        onClick={handleSubmit}
        disabled={!canSubmit}
      >
        {isSubmitting ? (
          <>
            <span className="plinko-spinner" />
            Placing Bet...
          </>
        ) : (
          'Drop Ball'
        )}
      </button>

      {/* ── Result Display ─────────────────────────────────────────── */}
      {result && !isAnimating && (
        <div className="plinko-result">
          <h3 className="plinko-result-title">Result</h3>
          <div className="plinko-result-details">
            <span className="plinko-result-slot">
              Slot: <strong>{result.slot}</strong>
            </span>
            <span className="plinko-result-multiplier">
              Multiplier: <strong>{result.multiplier.toFixed(2)}x</strong>
            </span>
            <span className="plinko-result-payout">
              Payout: <strong>{formatErg(result.payout)} ERG</strong>
            </span>
          </div>
        </div>
      )}

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
            <span className="plinko-pending-row-label">Rows</span>
            <span className="plinko-pending-row-value">{pendingBet.rows}</span>
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
    </div>
  );
};

export default PlinkoGame;