/**
 * Reusable UI component library for DuckPools.
 *
 * All components use design tokens from index.css :root variables.
 * BEM-like naming convention: ui-{component}, ui-{component}--{modifier}, ui-{component}__{element}.
 *
 * @example
 * ```tsx
 * import { Button, Card, Input, Modal, Badge, Toggle, Tooltip, AddressInput, ToastProvider, useToast, EmptyState } from '@/components/ui';
 * ```
 */

// ── Core Components ─────────────────────────────

export { default as Button } from './Button';
export type { ButtonProps, ButtonVariant, ButtonSize } from './Button';

export { default as Card, CardHeader, CardBody, CardFooter } from './Card';
export type { CardProps, CardVariant, CardPadding } from './Card';

export { default as Input } from './Input';
export type { InputProps } from './Input';

export { default as AddressInput } from './AddressInput';
export type { AddressInputProps } from './AddressInput';

export { default as Modal } from './Modal';
export type { ModalProps, ModalSize } from './Modal';

// ── Feedback Components ─────────────────────────

export { default as Badge } from './Badge';
export type { BadgeProps, BadgeVariant, BadgeSize } from './Badge';

export { default as Toast } from './Toast';
export type { ToastProps, ToastType, ToastPosition } from './Toast';

export { ToastProvider, useToast } from './ToastProvider';
export type { ToastItem } from './ToastProvider';

export { default as Spinner } from './Spinner';
export type { SpinnerProps, SpinnerVariant, SpinnerSize } from './Spinner';

export { default as Tooltip } from './Tooltip';
export type { TooltipProps, TooltipPosition } from './Tooltip';

// ── Form Components ─────────────────────────────

export { default as Toggle } from './Toggle';
export type { ToggleProps } from './Toggle';

// ── Layout Components ───────────────────────────

export { default as EmptyState } from './EmptyState';
export type { EmptyStateProps } from './EmptyState';
