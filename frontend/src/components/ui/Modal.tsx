import React, { useEffect, useRef, useCallback } from 'react';
import './Modal.css';

/** Size presets for the Modal component. */
export type ModalSize = 'sm' | 'md' | 'lg';

/** Props for the reusable Modal component. */
export interface ModalProps {
  /** Controls visibility. */
  isOpen: boolean;
  /** Called when the modal should close (backdrop click, escape, close button). */
  onClose: () => void;
  /** Title displayed in the header. Optional -- pass null for no header. */
  title?: React.ReactNode;
  /** Size preset. Default: 'md'. */
  size?: ModalSize;
  /** Primary content area. */
  children?: React.ReactNode;
  /** Footer content (typically action buttons). */
  footer?: React.ReactNode;
  /** Additional class name for the modal panel. */
  className?: string;
}

/**
 * Reusable Modal component with backdrop, entrance/exit animations, escape key handling,
 * focus trapping, and body scroll lock.
 *
 * @example
 * ```tsx
 * const [open, setOpen] = useState(false);
 * <Modal isOpen={open} onClose={() => setOpen(false)} title="Confirm Bet" footer={<Button>Confirm</Button>}>
 *   <p>You are about to place a bet of 1.0 ERG on Heads.</p>
 * </Modal>
 * ```
 */
const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  size = 'md',
  children,
  footer,
  className = '',
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const [closing, setClosing] = React.useState(false);
  const prevFocusRef = useRef<HTMLElement | null>(null);

  /** Close with exit animation. */
  const handleClose = useCallback(() => {
    setClosing(true);
    // Wait for animation before actually unmounting
    setTimeout(() => {
      setClosing(false);
      onClose();
    }, 120);
  }, [onClose]);

  /** Close on Escape key. */
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleClose]);

  /** Body scroll lock + focus management. */
  useEffect(() => {
    if (isOpen) {
      prevFocusRef.current = document.activeElement as HTMLElement;
      document.body.classList.add('ui-modal-locked');

      // Focus the modal panel for focus trapping
      requestAnimationFrame(() => {
        panelRef.current?.focus();
      });
    } else {
      document.body.classList.remove('ui-modal-locked');
      // Restore focus
      prevFocusRef.current?.focus();
    }

    return () => {
      document.body.classList.remove('ui-modal-locked');
    };
  }, [isOpen]);

  /** Focus trap: cycle focus within the modal. */
  useEffect(() => {
    if (!isOpen) return;

    const panel = panelRef.current;
    if (!panel) return;

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const focusable = panel.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    panel.addEventListener('keydown', handleTabKey);
    return () => panel.removeEventListener('keydown', handleTabKey);
  }, [isOpen]);

  if (!isOpen) return null;

  const panelClasses = [
    'ui-modal',
    `ui-modal--${size}`,
    closing && 'ui-modal--closing',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div
      className={`ui-modal-backdrop ${closing ? 'ui-modal-backdrop--closing' : ''}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        ref={panelRef}
        className={panelClasses}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : 'Dialog'}
        tabIndex={-1}
      >
        {title !== undefined && (
          <div className="ui-modal__header">
            <h2 className="ui-modal__title">{title}</h2>
            <button
              className="ui-modal__close"
              onClick={handleClose}
              aria-label="Close dialog"
              type="button"
            >
              ✕
            </button>
          </div>
        )}
        {title === undefined && (
          <button
            className="ui-modal__close"
            onClick={handleClose}
            aria-label="Close dialog"
            type="button"
            style={{ position: 'absolute', top: 16, right: 16 }}
          >
            ✕
          </button>
        )}
        <div className="ui-modal__body">{children}</div>
        {footer && <div className="ui-modal__footer">{footer}</div>}
      </div>
    </div>
  );
};

export default Modal;
