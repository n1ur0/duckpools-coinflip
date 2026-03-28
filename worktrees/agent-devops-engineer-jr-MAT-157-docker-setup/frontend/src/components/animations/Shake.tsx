import React from 'react';
import './animations.css';

export type ShakeIntensity = 'soft' | 'hard';

interface ShakeProps {
  children: React.ReactNode;
  trigger: boolean;
  intensity?: ShakeIntensity;
  className?: string;
  onAnimationEnd?: () => void;
}

/**
 * Shake Animation Component
 *
 * Wrapper component that applies a shake animation to its children
 * when the trigger prop changes from false to true.
 */
const Shake: React.FC<ShakeProps> = ({
  children,
  trigger,
  intensity = 'soft',
  className = '',
  onAnimationEnd,
}) => {
  const prefersReducedMotion = React.useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  );

  const getAnimationName = () => {
    if (!trigger) return 'none';
    if (prefersReducedMotion) return 'none';
    return intensity === 'hard' ? 'shakeHard' : 'shake';
  };

  const getDuration = () => {
    return intensity === 'hard' ? '0.5s' : '0.4s';
  };

  const handleAnimationEnd = () => {
    if (onAnimationEnd) {
      onAnimationEnd();
    }
  };

  return (
    <div
      className={`shake ${className}`}
      style={{
        display: 'inline-block',
        animation: trigger && !prefersReducedMotion ? `${getAnimationName()} ${getDuration()} ease-in-out` : 'none',
      }}
      onAnimationEnd={handleAnimationEnd}
    >
      {children}
    </div>
  );
};

export default Shake;
