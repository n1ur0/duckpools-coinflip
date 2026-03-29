import React from 'react';
import { motion, type HTMLMotionProps } from 'framer-motion';
import './Button.css';

/** Available visual variants for the Button component. */
export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success' | 'gold';

/** Available sizes for the Button component. */
export type ButtonSize = 'sm' | 'md' | 'lg';

/** Props for the reusable Button component. */
export interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'size'> {
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
  whileTap = { scale: 0.97 },
  whileHover = !disabled && !loading ? { scale: 1.02 } : undefined,
  transition = { type: 'spring' as const, stiffness: 400, damping: 20 },
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
    <motion.button
      className={classes}
      disabled={isDisabled}
      whileTap={isDisabled ? undefined : whileTap}
      whileHover={whileHover}
      transition={transition}
      {...rest}
    >
      {loading ? (
        <span className="ui-btn__spinner" />
      ) : (
        iconStart && <span className="ui-btn__icon ui-btn__icon--start">{iconStart}</span>
      )}
      {children && <span>{children}</span>}
      {!loading && iconEnd && <span className="ui-btn__icon ui-btn__icon--end">{iconEnd}</span>}
    </motion.button>
  );
};

export default Button;
