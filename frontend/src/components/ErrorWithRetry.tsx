/**
 * ErrorWithRetry - Reusable inline error display with retry button
 *
 * Drop this into any component that fetches data to show user-friendly
 * error messages with a retry action.
 */

import { AlertTriangle, RefreshCw } from 'lucide-react';
import './ErrorWithRetry.css';

interface ErrorWithRetryProps {
  /** Error message to display (or raw error object) */
  error: string | Error | null;
  /** Label shown above the error (e.g., "Pool State") */
  label?: string;
  /** Retry callback */
  onRetry: () => void;
  /** Additional CSS class */
  className?: string;
  /** Whether a retry is currently in progress */
  isRetrying?: boolean;
}

/**
 * Get a user-friendly message from a raw error.
 * Translates common API/network errors into plain language.
 */
export function friendlyError(error: string | Error | null): string {
  if (!error) return 'Something went wrong';

  const msg = typeof error === 'string' ? error : error.message;

  // Common patterns -> user-friendly messages
  if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('net::ERR_')) {
    return 'Network error — check your connection and try again';
  }
  if (msg.includes('HTTP 500') || msg.includes('Internal Server')) {
    return 'Server error — please try again in a moment';
  }
  if (msg.includes('HTTP 502') || msg.includes('Bad Gateway')) {
    return 'Server temporarily unavailable — please retry';
  }
  if (msg.includes('HTTP 503') || msg.includes('Service Unavailable')) {
    return 'Service under maintenance — please check back shortly';
  }
  if (msg.includes('HTTP 401') || msg.includes('Unauthorized')) {
    return 'Authentication required — please reconnect your wallet';
  }
  if (msg.includes('HTTP 429') || msg.includes('Too Many')) {
    return 'Too many requests — please wait a moment and retry';
  }
  if (msg.includes('HTTP 404') || msg.includes('Not Found')) {
    return 'Resource not found — the data may have moved';
  }
  if (msg.includes('timeout') || msg.includes('Timeout') || msg.includes('TIMEOUT')) {
    return 'Request timed out — the server may be busy, please retry';
  }
  if (msg.includes('AbortError')) {
    return 'Request was cancelled';
  }

  // Return cleaned up message for unknown errors
  return msg;
}

export default function ErrorWithRetry({
  error,
  label,
  onRetry,
  className = '',
  isRetrying = false,
}: ErrorWithRetryProps) {
  if (!error) return null;

  const message = friendlyError(error);

  return (
    <div className={`ewr-container ${className}`}>
      <div className="ewr-content">
        <AlertTriangle size={16} className="ewr-icon" />
        <div className="ewr-text">
          {label && <span className="ewr-label">{label}</span>}
          <span className="ewr-message">{message}</span>
        </div>
      </div>
      <button
        className="ewr-retry-btn"
        onClick={onRetry}
        disabled={isRetrying}
        title="Retry"
      >
        <RefreshCw size={14} className={isRetrying ? 'ewr-spinning' : ''} />
        {isRetrying ? 'Retrying...' : 'Retry'}
      </button>
    </div>
  );
}
