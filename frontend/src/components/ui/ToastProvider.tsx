import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Toast from './Toast';
import './Toast.css';

/** Individual toast item interface */
export interface ToastItem {
  id: string;
  message: ReactNode;
  type: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  showCloseButton?: boolean;
  showIcon?: boolean;
}

/** Toast context interface */
interface ToastContextType {
  /** Show a success toast */
  success: (message: ReactNode, options?: Omit<ToastItem, 'id' | 'type'>) => void;
  /** Show an error toast */
  error: (message: ReactNode, options?: Omit<ToastItem, 'id' | 'type'>) => void;
  /** Show a warning toast */
  warning: (message: ReactNode, options?: Omit<ToastItem, 'id' | 'type'>) => void;
  /** Show an info toast */
  info: (message: ReactNode, options?: Omit<ToastItem, 'id' | 'type'>) => void;
  /** Show a custom toast */
  show: (message: ReactNode, type: ToastItem['type'], options?: Omit<ToastItem, 'id' | 'type'>) => void;
  /** Remove a specific toast by id */
  remove: (id: string) => void;
  /** Clear all toasts */
  clearAll: () => void;
}

/** Default toast options */
const DEFAULT_TOAST_OPTIONS: Omit<ToastItem, 'id' | 'message' | 'type'> = {
  duration: 5000,
  position: 'top-right',
  showCloseButton: true,
  showIcon: true,
};

/** Toast context */
const ToastContext = createContext<ToastContextType | undefined>(undefined);

/** Hook to use toast functionality */
export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

/** Props for the ToastProvider component */
export interface ToastProviderProps {
  /** Maximum number of toasts to show at once */
  maxToasts?: number;
  /** Children components */
  children: ReactNode;
  /** Container z-index */
  zIndex?: number;
}

/**
 * ToastProvider component that manages multiple toasts with stacking functionality.
 * Provides context for showing toasts anywhere in the app.
 *
 * @example
 * ```tsx
 * // Wrap your app with ToastProvider
 * <ToastProvider>
 *   <App />
 * </ToastProvider>
 *
 * // Use toasts in any component
 * const toast = useToast();
 * toast.success('Operation completed!');
 * toast.error('Something went wrong');
 * ```
 */
const ToastProvider: React.FC<ToastProviderProps> = ({
  maxToasts = 5,
  children,
  zIndex = 9999,
}) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  /** Generate unique ID for toasts */
  const generateId = useCallback(() => `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`, []);

  /** Add a new toast */
  const addToast = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = generateId();
    const newToast: ToastItem = { id, ...DEFAULT_TOAST_OPTIONS, ...toast };
    
    setToasts(prev => {
      // Remove oldest toast if we exceed maxToasts
      const updated = [...prev, newToast];
      return updated.slice(-maxToasts);
    });

    // Auto-remove after duration
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, newToast.duration);
    }
  }, [generateId, maxToasts]);

  /** Show a success toast */
  const success = useCallback((message: ReactNode, options?: Omit<ToastItem, 'id' | 'type'>) => {
    addToast({ message, type: 'success', ...options });
  }, [addToast]);

  /** Show an error toast */
  const error = useCallback((message: ReactNode, options?: Omit<ToastItem, 'id' | 'type'>) => {
    addToast({ message, type: 'error', ...options });
  }, [addToast]);

  /** Show a warning toast */
  const warning = useCallback((message: ReactNode, options?: Omit<ToastItem, 'id' | 'type'>) => {
    addToast({ message, type: 'warning', ...options });
  }, [addToast]);

  /** Show an info toast */
  const info = useCallback((message: ReactNode, options?: Omit<ToastItem, 'id' | 'type'>) => {
    addToast({ message, type: 'info', ...options });
  }, [addToast]);

  /** Show a custom toast */
  const show = useCallback((message: ReactNode, type: ToastItem['type'], options?: Omit<ToastItem, 'id' | 'type'>) => {
    addToast({ message, type, ...options });
  }, [addToast]);

  /** Remove a specific toast */
  const remove = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  /** Clear all toasts */
  const clearAll = useCallback(() => {
    setToasts([]);
  }, []);

  const contextValue: ToastContextType = {
    success,
    error,
    warning,
    info,
    show,
    remove,
    clearAll,
  };

  /** Group toasts by position */
  const toastsByPosition = toasts.reduce((acc, toast) => {
    const position = toast.position || 'top-right';
    if (!acc[position]) {
      acc[position] = [];
    }
    acc[position].push(toast);
    return acc;
  }, {} as Record<string, ToastItem[]>);

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      
      {/* Render toast containers for each position */}
      {Object.entries(toastsByPosition).map(([position, positionToasts]) => (
        <div
          key={position}
          className={`toast-provider toast-provider--${position}`}
          style={{ 
            position: 'fixed',
            zIndex,
            pointerEvents: 'none',
          }}
        >
          <AnimatePresence>
            {positionToasts.map((toast, index) => {
              // Calculate stack offset (newer toasts appear above)
              const stackOffset = index * 4;
              
              return (
                <motion.div
                  key={toast.id}
                  className="toast-provider__toast-wrapper"
                  style={{
                    position: 'absolute',
                    ...(position === 'top-right' && { top: `${16 + stackOffset}px`, right: '16px' }),
                    ...(position === 'top-left' && { top: `${16 + stackOffset}px`, left: '16px' }),
                    ...(position === 'bottom-right' && { bottom: `${16 + stackOffset}px`, right: '16px' }),
                    ...(position === 'bottom-left' && { bottom: `${16 + stackOffset}px`, left: '16px' }),
                    pointerEvents: 'auto',
                  }}
                  initial={{ opacity: 0, x: position.includes('right') ? 100 : -100, y: -20 }}
                  animate={{ opacity: 1, x: 0, y: 0 }}
                  exit={{ opacity: 0, x: position.includes('right') ? 100 : -100, y: -20 }}
                  transition={{ duration: 0.2, ease: 'easeOut' }}
                >
                  <Toast
                    message={toast.message}
                    type={toast.type}
                    isVisible={true}
                    onClose={() => remove(toast.id)}
                    duration={0} // Disable auto-dismiss since we handle it in the provider
                    position={toast.position}
                    showCloseButton={toast.showCloseButton}
                    showIcon={toast.showIcon}
                  />
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      ))}
    </ToastContext.Provider>
  );
};

ToastProvider.displayName = 'ToastProvider';

export default ToastProvider;