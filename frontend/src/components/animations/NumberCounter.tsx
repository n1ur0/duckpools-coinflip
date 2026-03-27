import React, { useEffect, useRef, useState } from 'react';

interface NumberCounterProps {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  formatNumber?: (num: number) => string;
}

/**
 * Number Counter Animation Component
 *
 * Animates a number from 0 to the target value using requestAnimationFrame.
 * Supports formatting with prefix, suffix, and custom formatters.
 */
const NumberCounter: React.FC<NumberCounterProps> = ({
  value,
  duration = 1000,
  decimals = 0,
  prefix = '',
  suffix = '',
  className = '',
  formatNumber,
}) => {
  const [displayValue, setDisplayValue] = useState(0);
  const animationRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const prefersReducedMotion = React.useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  );

  useEffect(() => {
    // If prefers reduced motion, show final value immediately
    if (prefersReducedMotion) {
      setDisplayValue(value);
      return;
    }

    // Reset to 0 when value changes
    setDisplayValue(0);

    const animate = (currentTime: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = currentTime;
      }

      const elapsed = currentTime - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // Ease out cubic function for smooth animation
      const easeOutCubic = 1 - Math.pow(1 - progress, 3);
      const currentValue = value * easeOutCubic;

      setDisplayValue(currentValue);

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      }
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current !== null) {
        cancelAnimationFrame(animationRef.current);
      }
      startTimeRef.current = null;
    };
  }, [value, duration, prefersReducedMotion]);

  const formatValue = (num: number): string => {
    const roundedValue = decimals > 0 ? parseFloat(num.toFixed(decimals)) : Math.round(num);
    return formatNumber ? formatNumber(roundedValue) : roundedValue.toLocaleString();
  };

  return (
    <span className={`number-counter ${className}`}>
      {prefix}
      {formatValue(displayValue)}
      {suffix}
    </span>
  );
};

export default NumberCounter;
