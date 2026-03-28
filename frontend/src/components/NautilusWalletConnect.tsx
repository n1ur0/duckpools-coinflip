/**
 * NautilusWalletConnect Component
 *
 * A button component that demonstrates how to use the useNautilusWallet hook
 * to connect to Nautilus wallet with session persistence.
 *
 * Features:
 * - Connect/disconnect button
 * - Shows connection status
 * - Displays wallet address when connected
 * - Shows persisted session status
 */

import React from 'react';
import { useNautilusWallet } from '../wallet';
import './NautilusWalletConnect.css';

interface NautilusWalletConnectProps {
  className?: string;
  onConnect?: (address: string) => void;
  onDisconnect?: () => void;
}

export function NautilusWalletConnect({ 
  className = '', 
  onConnect,
  onDisconnect 
}: NautilusWalletConnectProps) {
  const {
    isConnected,
    isConnecting,
    isLocked,
    walletAddress,
    hasPersistedSession,
    error,
    connect,
    disconnect,
    clearSession,
  } = useNautilusWallet();

  const handleConnect = async () => {
    try {
      await connect();
      if (walletAddress && onConnect) {
        onConnect(walletAddress);
      }
    } catch (err) {
      console.error('Failed to connect to Nautilus wallet:', err);
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnect();
      if (onDisconnect) {
        onDisconnect();
      }
    } catch (err) {
      console.error('Failed to disconnect from Nautilus wallet:', err);
    }
  };

  const handleClearSession = () => {
    clearSession();
  };

  const getButtonText = () => {
    if (isConnecting) return 'Connecting...';
    if (isLocked) return 'Unlock Wallet';
    if (isConnected) return 'Disconnect';
    if (hasPersistedSession) return 'Restore Session';
    return 'Connect Nautilus';
  };

  const getStatusText = () => {
    if (error) return `Error: ${error.message}`;
    if (isConnected) return `Connected: ${walletAddress?.slice(0, 6)}...${walletAddress?.slice(-4)}`;
    if (hasPersistedSession) return 'Session available';
    if (isConnecting) return 'Connecting...';
    return 'Not connected';
  };

  return (
    <div className={`nautilus-wallet-connect ${className}`}>
      <div className="wallet-status">
        <span className="status-text">{getStatusText()}</span>
        {hasPersistedSession && (
          <span className="session-indicator" title="Persisted session available">
            💾
          </span>
        )}
      </div>
      
      <div className="wallet-actions">
        <button
          className={`wallet-button ${isConnected ? 'connected' : 'disconnected'}`}
          onClick={isConnected ? handleDisconnect : handleConnect}
          disabled={isConnecting}
        >
          {getButtonText()}
        </button>
        
        {hasPersistedSession && !isConnected && (
          <button
            className="clear-session-button"
            onClick={handleClearSession}
            title="Clear persisted session"
          >
            Clear Session
          </button>
        )}
      </div>
      
      {error && (
        <div className="wallet-error">
          <div className="error-message">{error.message}</div>
          {error.suggestions.length > 0 && (
            <ul className="error-suggestions">
              {error.suggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      
      <div className="wallet-info">
        <small>
          Using Nautilus EIP-12 wallet connection with session persistence.
          {hasPersistedSession && ' Session will be restored automatically.'}
        </small>
      </div>
    </div>
  );
}