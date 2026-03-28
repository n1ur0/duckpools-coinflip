import React, { useState, useRef, useEffect } from 'react';
import './Tooltip.css';

/** Position presets for the Tooltip component. */
export type TooltipPosition = 'top' | 'bottom' | 'left' | 'right';

/** Props for the reusable Tooltip component. */
export interface TooltipProps {
  /** Content to display in the tooltip (string or React node). */
  content: React.ReactNode;
  /** Position of the tooltip relative to the trigger. Default: 'top'. */
  position?: TooltipPosition;
  /** The element that triggers the tooltip on hover. */
  children: React.ReactElement;
  /** Additional class name for the tooltip. */
  className?: string;
  /** Delay before showing tooltip (ms). Default: 200. */
  delay?: number;
}

/**
 * Reusable Tooltip component that shows content on hover.
 *
 * Features:
 * - 200ms delay before showing
 * - Position options (top, bottom, left, right)
 * - Arrow pointing to trigger element
 * - Uses CSS custom properties for colors
 *
 * @example
 * ```tsx
 * <Tooltip content="This is a tooltip" position="top">
 *   <Button>Hover me</Button>
 * </Tooltip>
 * ```
 */
const Tooltip: React.FC<TooltipProps> = ({
  content,
  position = 'top',
  children,
  className = '',
  delay = 200,
}) => {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggerRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [arrowOffset, setArrowOffset] = useState(0);

  const handleMouseEnter = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setVisible(true);
    }, delay);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setVisible(false);
    }, 50); // Faster hide than show for better UX
  };

  // Calculate arrow position based on trigger center
  useEffect(() => {
    if (visible && triggerRef.current && tooltipRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();

      // Calculate the center position relative to the tooltip
      if (position === 'top' || position === 'bottom') {
        setArrowOffset((triggerRect.left + triggerRect.width / 2) - tooltipRect.left);
      } else {
        setArrowOffset((triggerRect.top + triggerRect.height / 2) - tooltipRect.top);
      }
    }
  }, [visible, position]);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Clone child element to add ref and event handlers
  const triggerWithEvents = React.cloneElement(children, {
    ref: triggerRef,
    onMouseEnter: (e: React.MouseEvent) => {
      handleMouseEnter();
      if (children.props.onMouseEnter) {
        children.props.onMouseEnter(e);
      }
    },
    onMouseLeave: (e: React.MouseEvent) => {
      handleMouseLeave();
      if (children.props.onMouseLeave) {
        children.props.onMouseLeave(e);
      }
    },
  });

  const tooltipClasses = [
    'ui-tooltip',
    `ui-tooltip--${position}`,
    visible && 'ui-tooltip--visible',
    className,
  ].filter(Boolean).join(' ');

  const arrowStyle: React.CSSProperties = {
    '--arrow-offset': `${arrowOffset}px`,
  } as React.CSSProperties;

  return (
    <>
      {triggerWithEvents}
      <div
        ref={tooltipRef}
        className={tooltipClasses}
        style={arrowStyle}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <div className="ui-tooltip__content">{content}</div>
        <div className={`ui-tooltip__arrow ui-tooltip__arrow--${position}`} />
      </div>
    </>
  );
};

export default Tooltip;
