import React from 'react';
import './Card.css';

/** Visual variant for the Card component. */
export type CardVariant = 'default' | 'glass' | 'elevated' | 'bordered';

/** Padding preset for the Card component. */
export type CardPadding = 'sm' | 'md' | 'lg';

/** Props for the reusable Card component. */
export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Visual style variant. Default: 'glass'. */
  variant?: CardVariant;
  /** Padding preset. Default: 'md'. */
  padding?: CardPadding;
  /** Enables hover effect with background/border change. */
  hoverable?: boolean;
  /** Applies cursor:pointer and press feedback. */
  clickable?: boolean;
  /** Card content. */
  children?: React.ReactNode;
}

/**
 * Reusable Card container supporting multiple variants (glass, elevated, bordered).
 * Matches the existing glassmorphism card pattern used across the app.
 *
 * @example
 * ```tsx
 * <Card variant="glass" padding="md">
 *   <h3>Pool Stats</h3>
 *   <p>Total liquidity: 1000 ERG</p>
 * </Card>
 * ```
 */
const Card: React.FC<CardProps> = ({
  variant = 'glass',
  padding = 'md',
  hoverable = false,
  clickable = false,
  className = '',
  children,
  ...rest
}) => {
  const classes = [
    'ui-card',
    `ui-card--${variant}`,
    `ui-card--pad-${padding}`,
    hoverable && 'ui-card--hoverable',
    clickable && 'ui-card--clickable',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className={classes} {...rest}>
      {children}
    </div>
  );
};

/** Sub-component for the card header area. */
export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...rest
}) => (
  <div className={`ui-card__header ${className}`} {...rest}>
    {children}
  </div>
);

/** Sub-component for the card body area. */
export const CardBody: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...rest
}) => (
  <div className={`ui-card__body ${className}`} {...rest}>
    {children}
  </div>
);

/** Sub-component for the card footer area. */
export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...rest
}) => (
  <div className={`ui-card__footer ${className}`} {...rest}>
    {children}
  </div>
);

export default Card;
