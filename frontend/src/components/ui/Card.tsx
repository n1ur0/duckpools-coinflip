import React from 'react';
import { motion, type HTMLMotionProps } from 'framer-motion';
import './Card.css';

/** Visual variant for the Card component. */
export type CardVariant = 'default' | 'glass' | 'elevated' | 'bordered';

/** Padding preset for the Card component. */
export type CardPadding = 'sm' | 'md' | 'lg';

/** Props for the reusable Card component. */
export interface CardProps extends Omit<HTMLMotionProps<'div'>, 'title'> {
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
  /** Enable entrance animation. Default: true. */
  animate?: boolean;
  /** Animation delay in seconds. Default: 0. */
  animationDelay?: number;
}

const cardVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.98 },
  visible: {
    opacity: 1, y: 0, scale: 1,
    transition: { duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] },
  },
};

const Card: React.FC<CardProps> = ({
  variant = 'glass',
  padding = 'md',
  hoverable = false,
  clickable = false,
  className = '',
  children,
  animate = true,
  animationDelay = 0,
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

  if (animate) {
    return (
      <motion.div
        className={classes}
        variants={cardVariants}
        initial="hidden"
        animate="visible"
        transition={{ delay: animationDelay }}
        whileHover={hoverable || clickable ? { scale: 1.01, y: -2 } : undefined}
        whileTap={clickable ? { scale: 0.995 } : undefined}
        {...rest}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <motion.div
      className={classes}
      whileHover={hoverable || clickable ? { scale: 1.01, y: -2 } : undefined}
      whileTap={clickable ? { scale: 0.995 } : undefined}
      {...rest}
    >
      {children}
    </motion.div>
  );
};

/** Sub-component for the card header area. */
export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '', children, ...rest
}) => (
  <div className={`ui-card__header ${className}`} {...rest}>{children}</div>
);

/** Sub-component for the card body area. */
export const CardBody: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '', children, ...rest
}) => (
  <div className={`ui-card__body ${className}`} {...rest}>{children}</div>
);

/** Sub-component for the card footer area. */
export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '', children, ...rest
}) => (
  <div className={`ui-card__footer ${className}`} {...rest}>{children}</div>
);

export default Card;
