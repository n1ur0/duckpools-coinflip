import React from 'react';
import './EmptyState.css';

/** Props for the EmptyState component. */
export interface EmptyStateProps {
  /** Optional icon to display (will be rendered with muted opacity). */
  icon?: React.ReactNode;
  /** Title text for the empty state. */
  title: string;
  /** Description text for the empty state. */
  description: string;
  /** Optional call-to-action button. */
  actionButton?: React.ReactNode;
  /** Additional CSS classes. */
  className?: string;
}

/**
 * Reusable EmptyState component for displaying when there's no data to show.
 * Features a centered layout with optional icon, title, description, and CTA.
 *
 * @example
 * ```tsx
 * <EmptyState
 *   icon={<CoinIcon />}
 *   title="No bets yet"
 *   description="Place your first bet to get started"
 *   actionButton={<Button onClick={handlePlaceBet}>Place Bet</Button>}
 * />
 * ```
 */
const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionButton,
  className = '',
}) => {
  return (
    <div className={`ui-empty-state ${className}`}>
      {icon && (
        <div className="ui-empty-state__icon">
          {icon}
        </div>
      )}
      <h3 className="ui-empty-state__title">{title}</h3>
      <p className="ui-empty-state__description">{description}</p>
      {actionButton && (
        <div className="ui-empty-state__action">
          {actionButton}
        </div>
      )}
    </div>
  );
};

export default EmptyState;