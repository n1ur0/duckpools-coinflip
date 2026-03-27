import React from 'react';
import './animations.css';

export type CoinSide = 'heads' | 'tails' | null;

interface CoinFlipProps {
  result: CoinSide;
  isFlipping: boolean;
  onFlipComplete?: () => void;
  size?: number;
  className?: string;
}

/**
 * 3D Coin Flip Animation Component
 *
 * Shows a 3D coin that flips with CSS transform animation.
 * Gold for heads, silver/blue for tails.
 */
const CoinFlip: React.FC<CoinFlipProps> = ({
  result,
  isFlipping,
  onFlipComplete,
  size = 120,
  className = '',
}) => {
  const prefersReducedMotion = React.useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  );

  React.useEffect(() => {
    if (isFlipping && !prefersReducedMotion && onFlipComplete) {
      const timer = setTimeout(onFlipComplete, 2000); // 2s animation
      return () => clearTimeout(timer);
    }
  }, [isFlipping, onFlipComplete, prefersReducedMotion]);

  const getAnimationName = () => {
    if (!isFlipping) return 'none';
    if (prefersReducedMotion) return 'none';
    return result === 'heads' ? 'coinFlipHeads' : 'coinFlipTails';
  };

  const getCoinColor = () => {
    if (isFlipping) return 'var(--accent-gold)';
    if (result === 'heads') return 'var(--accent-gold)';
    if (result === 'tails') return 'var(--accent-blue, #3b82f6)';
    return 'var(--accent-gold)';
  };

  const getCoinLabel = () => {
    if (isFlipping) return '?';
    if (result === 'heads') return 'H';
    if (result === 'tails') return 'T';
    return '?';
  };

  return (
    <div
      className={`coin-flip-container ${className}`}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        perspective: '1000px',
      }}
      role="img"
      aria-label={isFlipping ? 'Flipping coin' : `Coin result: ${result}`}
    >
      <div
        style={{
          width: '100%',
          height: '100%',
          borderRadius: '50%',
          background: `linear-gradient(135deg, ${getCoinColor()}, ${getCoinColor()}dd)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: `${size * 0.4}px`,
          fontWeight: 'bold',
          color: '#fff',
          textShadow: '0 2px 4px rgba(0,0,0,0.3)',
          animation: isFlipping && !prefersReducedMotion ? `${getAnimationName()} 2s ease-out forwards` : 'none',
          boxShadow: '0 8px 20px rgba(0,0,0,0.3), inset 0 2px 4px rgba(255,255,255,0.2)',
          transition: isFlipping ? 'none' : 'transform 0.3s ease',
        }}
      >
        {getCoinLabel()}
      </div>
    </div>
  );
};

export default CoinFlip;
