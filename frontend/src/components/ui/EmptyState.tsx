import React from 'react';
import './EmptyState.css';

interface EmptyStateProps {
  /** Lucide icon or emoji character */
  icon?: React.ReactNode;
  /** Primary message */
  message: string;
  /** Optional secondary description */
  description?: string;
  /** Optional CTA button */
  action?: {
    label: string;
    onClick: () => void;
  };
  /** Size variant */
  size?: 'sm' | 'md';
  className?: string;
}

/**
 * Reusable empty state component.
 * Centered layout with muted icon, message, optional description and CTA.
 */
const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  message,
  description,
  action,
  size = 'md',
  className = '',
}) => {
  return (
    <div className={`empty-state empty-state--${size} ${className}`}>
      {icon && <div className="empty-state-icon">{icon}</div>}
      <p className="empty-state-message">{message}</p>
      {description && <p className="empty-state-description">{description}</p>}
      {action && (
        <button className="empty-state-action" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
};

export default EmptyState;
