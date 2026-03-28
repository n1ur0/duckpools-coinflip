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

  

  const getCoinClassName = () => {
    const classes = ['coin'];
    
    // Add size class
    if (size <= 60) classes.push('coin--size-sm');
    else if (size <= 90) classes.push('coin--size-md');
    else if (size <= 110) classes.push('coin--size-lg');
    else classes.push('coin--size-xl');
    
    // Add coin side class
    if (result === 'heads') classes.push('coin--heads');
    else if (result === 'tails') classes.push('coin--tails');
    
    // Add flipping class
    if (isFlipping && !prefersReducedMotion) {
      classes.push('coin--flipping');
      if (result === 'heads') classes.push('coin--heads-flipping');
      else if (result === 'tails') classes.push('coin--tails-flipping');
    }
    
    return classes.join(' ');
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
      }}
      role="img"
      aria-label={isFlipping ? 'Flipping coin' : `Coin result: ${result}`}
    >
      <div className={getCoinClassName()}>
        {getCoinLabel()}
      </div>
    </div>
  );
};

export default CoinFlip;
