import React, { useRef, useEffect, useState } from 'react';
import './animations.css';

export type FadeDirection = 'up' | 'down' | 'left' | 'right' | 'none';

interface FadeInProps {
  children: React.ReactNode;
  delay?: number;
  duration?: number;
  direction?: FadeDirection;
  className?: string;
  threshold?: number;
}

/**
 * Fade In Animation Component
 *
 * Wrapper component that triggers fade+slide entrance animation
 * when element comes into viewport using IntersectionObserver.
 */
const FadeIn: React.FC<FadeInProps> = ({
  children,
  delay = 0,
  duration = 400,
  direction = 'up',
  className = '',
  threshold = 0.1,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const elementRef = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = React.useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  );

  useEffect(() => {
    const element = elementRef.current;
    if (!element || prefersReducedMotion) {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
          }
        });
      },
      { threshold }
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [threshold, prefersReducedMotion]);

  const getAnimationName = () => {
    if (prefersReducedMotion) return 'none';
    switch (direction) {
      case 'up':
        return 'fadeInUp';
      case 'down':
        return 'fadeInDown';
      case 'left':
        return 'slideInLeft';
      case 'right':
        return 'slideInRight';
      case 'none':
      default:
        return 'fadeIn';
    }
  };

  return (
    <div
      ref={elementRef}
      className={`fade-in ${className}`}
      style={{
        opacity: isVisible || prefersReducedMotion ? 1 : 0,
        animation: isVisible && !prefersReducedMotion
          ? `${getAnimationName()} ${duration}ms ease-out ${delay}ms forwards`
          : 'none',
      }}
    >
      {children}
    </div>
  );
};

export default FadeIn;
