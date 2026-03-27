import React from 'react';
import './Button.css';

/** Available visual variants for the Button component. */
export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success' | 'gold';

/** Available sizes for the Button component. */
export type ButtonSize = 'sm' | 'md' | 'lg';

/** Props for the reusable Button component. */
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style variant. Default: 'primary'. */
  variant?: ButtonVariant;
  /** Size preset. Default: 'md'. */
  size?: ButtonSize;
  /** Shows a spinner and disables interaction when true. */
  loading?: boolean;
  /** Takes the full width of its container. */
  fullWidth?: boolean;
  /** Icon element placed before the label. */
  iconStart?: React.ReactNode;
  /** Icon element placed after the label. */
  iconEnd?: React.ReactNode;
  /** Button content (label text or elements). */
  children?: React.ReactNode;
}

/**
 * Reusable Button component supporting multiple variants, sizes, loading states, and icon slots.
 * Uses design tokens from CSS custom properties.
 *
 * @example
 * ```tsx
 * <Button variant="primary" size="lg" onClick={handleSubmit}>Place Bet</Button>
 * <Button variant="secondary" iconStart={<Icon />} loading={isPending}>Connect</Button>
 * ```
 */
const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  iconStart,
  iconEnd,
  children,
  disabled,
  className = '',
  ...rest
}) => {
  const classes = [
    'ui-btn',
    `ui-btn--${variant}`,
    `ui-btn--${size}`,
    loading && 'ui-btn--loading',
    fullWidth && 'ui-btn--fullWidth',
    className,
  ].filter(Boolean).join(' ');

  const isDisabled = disabled || loading;

  return (
    <button className={classes} disabled={isDisabled} {...rest}>
      {loading ? (
        <span className="ui-btn__spinner" />
      ) : (
        iconStart && <span className="ui-btn__icon ui-btn__icon--start">{iconStart}</span>
      )}
      {children && <span>{children}</span>}
      {!loading && iconEnd && <span className="ui-btn__icon ui-btn__icon--end">{iconEnd}</span>}
    </button>
  );
};

export default Button;
