/**
 * Reusable UI component library for DuckPools.
 *
 * All components use design tokens from index.css :root variables.
 * BEM-like naming convention: ui-{component}, ui-{component}--{modifier}, ui-{component}__{element}.
 *
 * @example
 * ```tsx
 * import { Button, Card, Input, Modal, Badge, Toggle } from '@/components/ui';
 * ```
 */

export { default as Button } from './Button';
export type { ButtonProps, ButtonVariant, ButtonSize } from './Button';

export { default as Card, CardHeader, CardBody, CardFooter } from './Card';
export type { CardProps, CardVariant, CardPadding } from './Card';

export { default as Input } from './Input';
export type { InputProps } from './Input';

export { default as Modal } from './Modal';
export type { ModalProps, ModalSize } from './Modal';

export { default as Badge } from './Badge';
export type { BadgeProps, BadgeVariant, BadgeSize } from './Badge';

export { default as Toggle } from './Toggle';
export type { ToggleProps } from './Toggle';
