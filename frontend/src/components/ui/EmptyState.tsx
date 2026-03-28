import React from 'react';
import { LucideIcon } from 'lucide-react';
import './EmptyState.css';

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

/**
 * EmptyState component for displaying empty/placeholder content
 * 
 * @example
 * ```tsx
 * <EmptyState
 *   icon={Trophy}
 *   title="No players yet"
 *   description="Be the first to flip and top the leaderboard!"
 * />
 * ```
 */
const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  action,
  className = '',
}) => {
  return (
    <div className={`empty-state ${className}`.trim()}>
      <div className="empty-state__content">
        {Icon && <Icon className="empty-state__icon" size={48} />}
        <h3 className="empty-state__title">{title}</h3>
        <p className="empty-state__description">{description}</p>
        {action && <div className="empty-state__action">{action}</div>}
      </div>
    </div>
  );
};

export default EmptyState;