import React, { useRef, useEffect, useState } from 'react';
import './animations.css';

export type SlideFrom = 'left' | 'right' | 'bottom' | 'top';

interface SlideInProps {
  children: React.ReactNode;
  from?: SlideFrom;
  delay?: number;
  duration?: number;
  className?: string;
  threshold?: number;
}

/**
 * Slide In Animation Component
 *
 * Wrapper component that triggers directional slide entrance animation
 * when element comes into viewport using IntersectionObserver.
 */
const SlideIn: React.FC<SlideInProps> = ({
  children,
  from = 'left',
  delay = 0,
  duration = 300,
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
    switch (from) {
      case 'left':
        return 'slideInLeft';
      case 'right':
        return 'slideInRight';
      case 'bottom':
        return 'slideInBottom';
      case 'top':
        return 'slideInTop';
      default:
        return 'slideInLeft';
    }
  };

  return (
    <div
      ref={elementRef}
      className={`slide-in ${className}`}
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

export default SlideIn;
