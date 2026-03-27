import React, { useState, useEffect } from 'react';
import './animations.css';

interface ConfettiProps {
  active: boolean;
  duration?: number;
  particleCount?: number;
  className?: string;
}

/**
 * Confetti Animation Component
 *
 * Pure CSS particle confetti animation for win celebrations.
 * Renders colored divs that fall from top to bottom with rotation.
 */
const Confetti: React.FC<ConfettiProps> = ({
  active,
  duration = 3000,
  particleCount = 50,
  className = '',
}) => {
  const [particles, setParticles] = useState<Array<{ id: number; left: string; color: string; animationDuration: string; animationDelay: string; size: string }>>([]);
  const prefersReducedMotion = React.useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  );

  const colors = [
    'var(--accent-gold)',
    'var(--accent-green)',
    'var(--accent-blue, #3b82f6)',
    'var(--accent-purple, #8b5cf6)',
    '#ff6b6b',
    '#4ecdc4',
  ];

  useEffect(() => {
    if (active && !prefersReducedMotion) {
      const newParticles = Array.from({ length: particleCount }, (_, i) => ({
        id: i,
        left: `${Math.random() * 100}%`,
        color: colors[Math.floor(Math.random() * colors.length)],
        animationDuration: `${2 + Math.random() * 3}s`,
        animationDelay: `${Math.random() * 0.5}s`,
        size: `${5 + Math.random() * 10}px`,
      }));

      setParticles(newParticles);

      // Clear particles after animation
      const timer = setTimeout(() => {
        setParticles([]);
      }, duration);

      return () => clearTimeout(timer);
    } else {
      setParticles([]);
    }
  }, [active, duration, particleCount, prefersReducedMotion]);

  if (!active || prefersReducedMotion || particles.length === 0) {
    return null;
  }

  return (
    <div
      className={`confetti-container ${className}`}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        overflow: 'hidden',
        zIndex: 'var(--z-toast, 500)',
      }}
      role="presentation"
      aria-label="Confetti celebration animation"
    >
      {particles.map((particle) => (
        <div
          key={particle.id}
          style={{
            position: 'absolute',
            top: '-10px',
            left: particle.left,
            width: particle.size,
            height: particle.size,
            backgroundColor: particle.color,
            borderRadius: Math.random() > 0.5 ? '50%' : '2px',
            animation: `confettiFall ${particle.animationDuration} ease-out forwards`,
            animationDelay: particle.animationDelay,
          }}
        />
      ))}
    </div>
  );
};

export default Confetti;
