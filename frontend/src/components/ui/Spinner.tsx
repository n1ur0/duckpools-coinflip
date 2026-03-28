import React from 'react';
import './Spinner.css';

/** Visual variant for the Spinner component. */
export type SpinnerVariant = 'default' | 'primary' | 'success' | 'warning' | 'error';

/** Size preset for the Spinner component. */
export type SpinnerSize = 'sm' | 'md' | 'lg';

/** Props for the reusable Spinner component. */
export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Visual variant. Default: 'default'. */
  variant?: SpinnerVariant;
  /** Size. Default: 'md'. */
  size?: SpinnerSize;
  /** Custom label for screen readers. Default: 'Loading...'. */
  label?: string;
}

/**
 * Loading spinner component used for async operations and loading states.
 * Supports multiple variants, sizes, and ARIA labels for accessibility.
 *
 * @example
 * ```tsx
 * <Spinner /> // Default spinner
 * <Spinner variant="primary" size="lg" />
 * <Spinner variant="success" label="Saving changes..." />
 * ```
 */
const Spinner: React.FC<SpinnerProps> = ({
  variant = 'default',
  size = 'md',
  label = 'Loading...',
  className = '',
  ...rest
}) => {
  const classes = [
    'ui-spinner',
    `ui-spinner--${variant}`,
    `ui-spinner--${size}`,
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className={classes} role="status" aria-label={label} aria-live="polite" {...rest}>
      <div className="ui-spinner__circle" />
      <span className="ui-spinner__sr-only">{label}</span>
    </div>
  );
};

export default Spinner;
