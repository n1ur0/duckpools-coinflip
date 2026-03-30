import React, { createContext, useContext, useReducer, useCallback } from 'react';
import Toast, { ToastType, ToastPosition } from './Toast';
import { generateUUID } from '../../utils/crypto';

/** Individual toast item with unique ID */
export interface ToastItem {
  id: string;
  message: React.ReactNode;
  type: ToastType;
  duration?: number;
  position: ToastPosition;
  showCloseButton?: boolean;
  showIcon?: boolean;
}

/** Toast context state */
interface ToastState {
  toasts: ToastItem[];
}

/** Toast context actions */
type ToastAction =
  | { type: 'ADD_TOAST'; payload: Omit<ToastItem, 'id'> }
  | { type: 'REMOVE_TOAST'; payload: string }
  | { type: 'CLEAR_ALL_TOASTS' };

/** Toast context type */
interface ToastContextType {
  showToast: (message: React.ReactNode, type?: ToastType, duration?: number) => void;
  showError: (message: React.ReactNode, duration?: number) => void;
  showSuccess: (message: React.ReactNode, duration?: number) => void;
  showWarning: (message: React.ReactNode, duration?: number) => void;
  showInfo: (message: React.ReactNode, duration?: number) => void;
  removeToast: (id: string) => void;
  clearAllToasts: () => void;
}

// Initial state
const initialState: ToastState = {
  toasts: [],
};

// Reducer function
function toastReducer(state: ToastState, action: ToastAction): ToastState {
  switch (action.type) {
    case 'ADD_TOAST':
      return {
        ...state,
        toasts: [...state.toasts, { ...action.payload, id: generateUUID() }],
      };
    case 'REMOVE_TOAST':
      return {
        ...state,
        toasts: state.toasts.filter((toast) => toast.id !== action.payload),
      };
    case 'CLEAR_ALL_TOASTS':
      return {
        ...state,
        toasts: [],
      };
    default:
      return state;
  }
}

// Create context
const ToastContext = createContext<ToastContextType | undefined>(undefined);

/** Toast Provider component */
export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(toastReducer, initialState);

  const showToast = useCallback(
    (message: React.ReactNode, type: ToastType = 'info', duration?: number) => {
      dispatch({
        type: 'ADD_TOAST',
        payload: {
          message,
          type,
          duration,
          position: 'top-right',
          showCloseButton: true,
          showIcon: true,
        },
      });
    },
    []
  );

  const showError = useCallback(
    (message: React.ReactNode, duration?: number) => {
      showToast(message, 'error', duration);
    },
    [showToast]
  );

  const showSuccess = useCallback(
    (message: React.ReactNode, duration?: number) => {
      showToast(message, 'success', duration);
    },
    [showToast]
  );

  const showWarning = useCallback(
    (message: React.ReactNode, duration?: number) => {
      showToast(message, 'warning', duration);
    },
    [showToast]
  );

  const showInfo = useCallback(
    (message: React.ReactNode, duration?: number) => {
      showToast(message, 'info', duration);
    },
    [showToast]
  );

  const removeToast = useCallback((id: string) => {
    dispatch({ type: 'REMOVE_TOAST', payload: id });
  }, []);

  const clearAllToasts = useCallback(() => {
    dispatch({ type: 'CLEAR_ALL_TOASTS' });
  }, []);

  const contextValue: ToastContextType = {
    showToast,
    showError,
    showSuccess,
    showWarning,
    showInfo,
    removeToast,
    clearAllToasts,
  };

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <ToastContainer toasts={state.toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
};

/** Hook for using toast functionality */
export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

/** Toast Container component for rendering multiple toasts */
const ToastContainer: React.FC<{
  toasts: ToastItem[];
  removeToast: (id: string) => void;
}> = ({ toasts, removeToast }) => {
  // Group toasts by position
  const toastsByPosition = toasts.reduce((acc, toast) => {
    if (!acc[toast.position]) {
      acc[toast.position] = [];
    }
    acc[toast.position].push(toast);
    return acc;
  }, {} as Record<ToastPosition, ToastItem[]>);

  return (
    <>
      {Object.entries(toastsByPosition).map(([position, positionToasts]) => (
        <div
          key={position}
          className={`toast-container toast-container--${position}`}
          style={{
            position: 'fixed',
            zIndex: 9999,
            ...(position === 'top-right' && { top: 20, right: 20 }),
            ...(position === 'top-left' && { top: 20, left: 20 }),
            ...(position === 'bottom-right' && { bottom: 20, right: 20 }),
            ...(position === 'bottom-left' && { bottom: 20, left: 20 }),
          }}
        >
          {positionToasts.map((toast, index) => (
            <div
              key={toast.id}
              style={{ marginBottom: index < positionToasts.length - 1 ? 12 : 0 }}
            >
              <Toast
                message={toast.message}
                type={toast.type}
                isVisible={true}
                onClose={() => removeToast(toast.id)}
                duration={toast.duration}
                position={toast.position as ToastPosition}
                showCloseButton={toast.showCloseButton}
                showIcon={toast.showIcon}
              />
            </div>
          ))}
        </div>
      ))}
    </>
  );
};

export default ToastProvider;