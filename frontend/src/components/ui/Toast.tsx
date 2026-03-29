import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import './Toast.css';

/** Toast types for different message categories. */
export type ToastType = 'success' | 'error' | 'warning' | 'info';

/** Position presets for Toast container. */
export type ToastPosition = 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';

/** Props for the reusable Toast component. */
export interface ToastProps {
  /** The toast message content. */
  message: React.ReactNode;
  /** Type of toast (affects color and icon). */
  type?: ToastType;
  /** Whether the toast is visible. */
  isVisible: boolean;
  /** Called when the toast should close. */
  onClose: () => void;
  /** Auto-dismiss timeout in ms. Default: 5000. Set to 0 to disable. */
  duration?: number;
  /** Position of the toast. Default: 'top-right'. */
  position?: ToastPosition;
  /** Additional class name for the toast. */
  className?: string;
  /** Whether to show the close button. Default: true. */
  showCloseButton?: boolean;
  /** Whether to show the icon. Default: true. */
  showIcon?: boolean;
}

/**
 * Reusable Toast component with animations and auto-dismiss.
 *
 * Features:
 * - 4 types: success, error, warning, info
 * - Auto-dismiss with configurable timeout
 * - Manual close button
 * - Framer-motion animations
 * - Position support
 * - Accessible with ARIA attributes
 *
 * @example
 * ```tsx
 * const [showToast, setShowToast] = useState(false);
 * <Toast
 *   message="Profile updated successfully!"
 *   type="success"
 *   isVisible={showToast}
 *   onClose={() => setShowToast(false)}
 *   duration={3000}
 * />
 * ```
 */
const Toast: React.FC<ToastProps> = ({
  message,
  type = 'info',
  isVisible,
  onClose,
  duration = 5000,
  position = 'top-right',
  className = '',
  showCloseButton = true,
  showIcon = true,
}) => {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-dismiss handling
  useEffect(() => {
    if (isVisible && duration > 0) {
      timeoutRef.current = setTimeout(() => {
        onClose();
      }, duration);
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [isVisible, duration, onClose]);

  // Get icon based on type
  const getIcon = () => {
    switch (type) {
      case 'success':
        return <CheckCircle className="toast__icon" size={20} />;
      case 'error':
        return <AlertCircle className="toast__icon" size={20} />;
      case 'warning':
        return <AlertTriangle className="toast__icon" size={20} />;
      case 'info':
      default:
        return <Info className="toast__icon" size={20} />;
    }
  };

  const toastClasses = [
    'toast',
    `toast--${type}`,
    className,
  ].filter(Boolean).join(' ');

  const toastContent = (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          className={toastClasses}
          role="alert"
          aria-live={type === 'error' || type === 'warning' ? 'assertive' : 'polite'}
          initial={{ opacity: 0, x: position.includes('right') ? 100 : -100, y: -20 }}
          animate={{ opacity: 1, x: 0, y: 0 }}
          exit={{ opacity: 0, x: position.includes('right') ? 100 : -100, y: -20 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          {showIcon && (
            <div className="toast__icon-container">
              {getIcon()}
            </div>
          )}
          
          <div className="toast__content">
            {typeof message === 'string' ? (
              <span className="toast__message">{message}</span>
            ) : (
              <div className="toast__message">{message}</div>
            )}
          </div>

          {showCloseButton && (
            <button
              className="toast__close"
              onClick={onClose}
              aria-label="Close toast"
              type="button"
            >
              <X size={16} />
            </button>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );

  return toastContent;
};

export default Toast;