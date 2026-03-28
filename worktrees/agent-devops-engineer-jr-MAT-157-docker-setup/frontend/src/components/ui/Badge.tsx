import React from 'react';
import './Badge.css';

/** Visual variant for the Badge component. */
export type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'gold';

/** Size preset for the Badge component. */
export type BadgeSize = 'sm' | 'md';

/** Props for the reusable Badge component. */
export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Visual variant. Default: 'default'. */
  variant?: BadgeVariant;
  /** Size. Default: 'md'. */
  size?: BadgeSize;
  /** Badge content (text). */
  children?: React.ReactNode;
}

/**
 * Small pill-shaped label used for status indicators, network badges, and tags.
 * Matches the existing network badge and tier badge patterns from WalletConnector and Leaderboard.
 *
 * @example
 * ```tsx
 * <Badge variant="success" size="sm">Connected</Badge>
 * <Badge variant="info">Testnet</Badge>
 * <Badge variant="gold">Gold Tier</Badge>
 * ```
 */
const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  size = 'md',
  className = '',
  children,
  ...rest
}) => {
  const classes = [
    'ui-badge',
    `ui-badge--${variant}`,
    `ui-badge--${size}`,
    className,
  ].filter(Boolean).join(' ');

  return (
    <span className={classes} {...rest}>
      {children}
    </span>
  );
};

export default Badge;
