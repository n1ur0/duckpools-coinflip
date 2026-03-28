import React from 'react';
import './animations.css';

export type GlowColor = 'gold' | 'green' | 'red' | 'blue' | 'purple';
export type GlowIntensity = 'subtle' | 'medium' | 'strong';

interface PulseGlowProps {
  children: React.ReactNode;
  color?: GlowColor;
  intensity?: GlowIntensity;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Pulse Glow Animation Component
 *
 * Wrapper component that applies a pulsing glow effect to its children.
 * Sets CSS custom property for glow color and applies animation.
 */
const PulseGlow: React.FC<PulseGlowProps> = ({
  children,
  color = 'gold',
  intensity = 'medium',
  className = '',
  style = {},
}) => {
  const prefersReducedMotion = React.useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  );

  const getGlowColor = (): string => {
    switch (color) {
      case 'gold':
        return 'rgba(240, 180, 41,';
      case 'green':
        return 'rgba(0, 255, 136,';
      case 'red':
        return 'rgba(239, 68, 68,';
      case 'blue':
        return 'rgba(59, 130, 246,';
      case 'purple':
        return 'rgba(139, 92, 246,';
      default:
        return 'rgba(240, 180, 41,';
    }
  };

  const getIntensityOpacity = (): number => {
    switch (intensity) {
      case 'subtle':
        return 0.15;
      case 'medium':
        return 0.3;
      case 'strong':
        return 0.5;
      default:
        return 0.3;
    }
  };

  const glowColor = `${getGlowColor()} ${getIntensityOpacity()})`;

  return (
    <div
      className={`pulse-glow ${className}`}
      style={{
        ...style,
        '--glow-color': glowColor,
        animation: prefersReducedMotion ? 'none' : `pulseGlow 2s ease-in-out infinite`,
      } as React.CSSProperties}
    >
      {children}
    </div>
  );
};

export default PulseGlow;
