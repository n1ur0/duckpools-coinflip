import React from 'react';
import './EmptyState.css';

/** Props for the EmptyState component. */
export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Icon to display (optional). */
  icon?: React.ReactNode;
  /** Title text to display. */
  title: string;
  /** Description text (optional). */
  description?: string;
  /** Action button/CTA (optional). */
  actionButton?: React.ReactNode;
  /** Additional CSS classes. */
  className?: string;
}

/**
 * Reusable EmptyState component for displaying empty data states.
 * Features centered layout with optional icon, title, description, and CTA.
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
  ...rest
}) => {
  const classes = [
    'ui-empty-state',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className={classes} {...rest}>
      {icon && (
        <div className="ui-empty-state__icon">
          {icon}
        </div>
      )}
      
      <h3 className="ui-empty-state__title">
        {title}
      </h3>
      
      {description && (
        <p className="ui-empty-state__description">
          {description}
        </p>
      )}
      
      {actionButton && (
        <div className="ui-empty-state__action">
          {actionButton}
        </div>
      )}
    </div>
  );
};

export default EmptyState;