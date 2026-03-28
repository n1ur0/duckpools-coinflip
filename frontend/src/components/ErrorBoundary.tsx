/**
 * ErrorBoundary - Catches React rendering errors with recovery UI
 *
 * Can be used globally (App-level) or per-component to isolate failures.
 * Supports "Try Again" to reset without full page reload.
 */

import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import './ErrorBoundary.css';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Label shown in the error UI for context */
  label?: string;
  /** Whether to show a "Go Home" button (for non-root boundaries) */
  showHome?: boolean;
  /** Custom fallback render (overrides default) */
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[ErrorBoundary${this.props.label ? `: ${this.props.label}` : ''}]`, error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined });
  };

  handleGoHome = () => {
    window.location.hash = '#main-content';
    this.handleReset();
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const error = this.state.error!;

    // Custom fallback
    if (this.props.fallback) {
      return this.props.fallback(error, this.handleReset);
    }

    // Compact mode for per-component boundaries
    const isRoot = !this.props.label;

    if (isRoot) {
      // Full-page error for root boundary
      return (
        <div className="eb-root">
          <div className="eb-root-card">
            <span className="eb-icon eb-icon--large">⚠️</span>
            <h2 className="eb-title">Something went wrong</h2>
            <p className="eb-message">{error.message}</p>
            <div className="eb-actions">
              <button className="eb-btn eb-btn--primary" onClick={this.handleReset}>
                <RefreshCw size={16} />
                Try Again
              </button>
              <button className="eb-btn eb-btn--secondary" onClick={() => window.location.reload()}>
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    // Compact inline error for per-component boundaries
    return (
      <div className="eb-inline">
        <AlertTriangle size={16} className="eb-inline-icon" />
        <div className="eb-inline-content">
          <span className="eb-inline-label">{this.props.label}</span>
          <span className="eb-inline-error">{error.message || 'An error occurred'}</span>
        </div>
        <button className="eb-inline-btn" onClick={this.handleReset} title="Retry">
          <RefreshCw size={14} />
        </button>
        {this.props.showHome && (
          <button className="eb-inline-btn" onClick={this.handleGoHome} title="Go Home">
            <Home size={14} />
          </button>
        )}
      </div>
    );
  }
}

export default ErrorBoundary;
