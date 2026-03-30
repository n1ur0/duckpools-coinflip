import { useEffect, useState, useRef, useCallback } from 'react';
import { Wallet, LogOut, Copy, Check, AlertCircle, RefreshCw, ChevronDown, Smartphone, ExternalLink, QrCode } from 'lucide-react';
import { useWallet } from '../contexts/WalletContext';
import { formatErg, formatAddress, copyToClipboard } from '../utils';
import { isMobileDevice, getMobileConnectUrl } from '../wallet/adapters';
import type { WalletInfo } from '../wallet/adapters';
import './WalletConnector.css';

export default function WalletConnector() {
  const {
    isConnected,
    isConnecting,
    isLocked,
    walletAddress,
    balance,
    network,
    tokens,
    error,
    activeWalletKey,
    activeWalletInfo,
    availableWallets,
    knownWallets,
    isDetecting,
    connect,
    disconnect,
    clearError,
    selectWallet,
    refreshAvailable,
  } = useWallet();

  const [errorVisible, setErrorVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showTokens, setShowTokens] = useState(false);
  const [flash, setFlash] = useState(false);
  const [showSelector, setShowSelector] = useState(false);
  const [showErgoPayInput, setShowErgoPayInput] = useState(false);
  const [ergoPayAddress, setErgoPayAddress] = useState('');
  const wasConnecting = useRef(false);
  const selectorRef = useRef<HTMLDivElement>(null);
  const isMobile = isMobileDevice();

  // Close selector on outside click
  useEffect(() => {
    if (!showSelector) return;
    const handler = (e: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setShowSelector(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showSelector]);

  useEffect(() => {
    if (error) {
      setErrorVisible(true);
      const t = setTimeout(() => { setErrorVisible(false); clearError(); }, 5000);
      return () => clearTimeout(t);
    }
    setErrorVisible(false);
    return undefined;
  }, [error, clearError]);

  useEffect(() => {
    if (wasConnecting.current && isConnected && !isConnecting) {
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 800);
      return () => clearTimeout(t);
    }
    if (isConnecting) wasConnecting.current = true;
    return undefined;
  }, [isConnected, isConnecting]);

  const handleCopy = async () => {
    if (!walletAddress) return;
    await copyToClipboard(walletAddress);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSelectWallet = useCallback((key: string) => {
    setShowSelector(false);
    selectWallet(key);
    // Do NOT call connect() here. The useErgoWallet hook's walletKey change
    // effect will handle reconnection. Calling connect() with setTimeout
    // captured a stale connect reference with the old walletKey, causing a
    // race condition where connect() ran with null/old walletKey and silently
    // returned with "No wallet selected" error.
  }, [selectWallet]);

  const handleMobileConnect = useCallback((wallet: WalletInfo) => {
    const url = getMobileConnectUrl(wallet.key, window.location.origin);
    if (url) {
      window.open(url, '_blank');
    }
  }, []);

  const handleErgoPayConnect = useCallback(() => {
    selectWallet('ergopay');
    setShowErgoPayInput(true);
  }, [selectWallet]);

  const handleErgoPaySubmit = useCallback(async () => {
    if (!ergoPayAddress.trim()) return;
    selectWallet('ergopay');
    setShowErgoPayInput(false);
    // The useErgoWallet hook needs the address to connect.
    // We store it in a data attribute on the connect flow.
    // The useErgoWallet connect function checks for ergopay and reads from localStorage.
    try {
      localStorage.setItem('duckpools:ergopay-pending-address', ergoPayAddress.trim());
    } catch {
      // ignore
    }
    // Trigger connect via a small delay to let state propagate
    setTimeout(() => connect(), 100);
  }, [ergoPayAddress, selectWallet, connect]);

  // Auto-select first available wallet if none selected
  useEffect(() => {
    if (!isDetecting && !activeWalletKey && availableWallets.length > 0) {
      selectWallet(availableWallets[0]);
    }
  }, [isDetecting, activeWalletKey, availableWallets, selectWallet]);

  // Re-detect wallets when connect is clicked but no wallet is selected.
  // This handles the case where the initial detection (2-5s timeout) was too short
  // and the extension hadn't injected yet. On retry, we poll for longer.
  const handleConnect = useCallback(async () => {
    // If no wallet is selected but we haven't detected any, try re-detecting
    // with a longer timeout before falling back to the regular connect flow.
    if (!activeWalletKey && availableWallets.length === 0 && !isDetecting) {
      const detected = await refreshAvailable();
      if (detected.length > 0) {
        selectWallet(detected[0]);
        // The walletKey change effect in useErgoWallet will NOT auto-connect.
        // We need to wait for the state to propagate and then call connect.
        // However, returning here means the user needs to click Connect again.
        // Instead, we let the auto-select effect fire and the user clicks again.
        // This is better than a race condition.
        return;
      }
    }
    connect();
  }, [activeWalletKey, availableWallets, isDetecting, refreshAvailable, selectWallet, connect]);

  // ─── Not connected state ──────────────────────────────────────

  if (!isConnected) {
    // If on mobile and no wallets detected, show mobile connect
    if (isMobile && availableWallets.length === 0 && !isDetecting) {
      return (
        <div className="wc-wrapper">
          <div className="wc-mobile-connect">
            <div className="wc-mobile-connect-header">
              <Smartphone size={20} />
              <span>Mobile Wallet</span>
            </div>
            <p className="wc-mobile-connect-desc">
              Open one of these wallets on your device:
            </p>
            <div className="wc-mobile-wallet-list">
              {knownWallets.filter(w => w.mobileScheme).map(wallet => (
                wallet.key === 'ergopay' ? (
                  <button
                    key={wallet.key}
                    className="wc-mobile-wallet-btn"
                    onClick={handleErgoPayConnect}
                    style={{ '--wallet-color': wallet.color } as React.CSSProperties}
                  >
                    <span className="wc-mobile-wallet-icon">{wallet.icon}</span>
                    <span className="wc-mobile-wallet-name">{wallet.name}</span>
                    <QrCode size={14} />
                  </button>
                ) : (
                  <button
                    key={wallet.key}
                    className="wc-mobile-wallet-btn"
                    onClick={() => handleMobileConnect(wallet)}
                    style={{ '--wallet-color': wallet.color } as React.CSSProperties}
                  >
                    <span className="wc-mobile-wallet-icon">{wallet.icon}</span>
                    <span className="wc-mobile-wallet-name">{wallet.name}</span>
                    <ExternalLink size={14} />
                  </button>
                )
              ))}
            </div>
          </div>

          {showErgoPayInput && (
            <div className="wc-ergopay-modal">
              <div className="wc-ergopay-modal-content">
                <div className="wc-ergopay-modal-header">
                  <QrCode size={20} />
                  <span>Connect via ErgoPay</span>
                </div>
                <p className="wc-ergopay-modal-desc">
                  Enter your Ergo address to connect via ErgoPay. Transactions will be signed on your mobile wallet.
                </p>
                <input
                  type="text"
                  className="wc-ergopay-address-input"
                  placeholder="9xxx... (Ergo address)"
                  value={ergoPayAddress}
                  onChange={(e) => setErgoPayAddress(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleErgoPaySubmit(); }}
                  autoFocus
                />
                <div className="wc-ergopay-modal-actions">
                  <button className="wc-ergopay-cancel-btn" onClick={() => setShowErgoPayInput(false)}>
                    Cancel
                  </button>
                  <button
                    className="wc-ergopay-connect-btn"
                    onClick={handleErgoPaySubmit}
                    disabled={!ergoPayAddress.trim()}
                  >
                    Connect
                  </button>
                </div>
              </div>
            </div>
          )}

          {errorVisible && error && (
            <div className="wc-error-toast">
              <p className="wc-error-msg">{error.message}</p>
              {error.suggestions.length > 0 && (
                <ul className="wc-error-list">
                  {error.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      );
    }

    return (
      <div className="wc-wrapper">
        <div className="wc-connect-row">
          <button
            onClick={handleConnect}
            disabled={isConnecting}
            className={`wc-connect-pill${isConnecting ? ' wc-connecting' : ''}`}
            aria-label="Connect Wallet"
          >
            {isConnecting ? (
              <>
                <span className="wc-spinner" />
                <span>Waiting for {activeWalletInfo?.name ?? 'wallet'}...</span>
              </>
            ) : (
              <>
                <Wallet size={18} strokeWidth={2} />
                <span>Connect Wallet</span>
              </>
            )}
          </button>

          {(availableWallets.length > 1 || knownWallets.some(w => w.mobileScheme && !availableWallets.includes(w.key))) && (
            <div className="wc-wallet-selector" ref={selectorRef}>
              <button
                className="wc-selector-toggle"
                onClick={() => setShowSelector(prev => !prev)}
                title="Switch wallet"
              >
                <span className="wc-selector-icon">{activeWalletInfo?.icon ?? '💼'}</span>
                <ChevronDown size={14} className={`wc-chevron${showSelector ? ' wc-chevron-open' : ''}`} />
              </button>

              {showSelector && (
                <div className="wc-selector-dropdown">
                  <div className="wc-selector-header">Select Wallet</div>
                  {availableWallets.map(key => {
                    const info = knownWallets.find(w => w.key === key);
                    if (!info) return null;
                    const isActive = key === activeWalletKey;
                    return (
                      <button
                        key={key}
                        className={`wc-selector-item${isActive ? ' wc-selector-item-active' : ''}`}
                        onClick={() => handleSelectWallet(key)}
                        style={{ '--wallet-color': info.color } as React.CSSProperties}
                      >
                        <span className="wc-selector-wallet-icon">{info.icon}</span>
                        <div className="wc-selector-wallet-info">
                          <span className="wc-selector-wallet-name">{info.name}</span>
                          {isActive && <span className="wc-selector-active-badge">Active</span>}
                        </div>
                      </button>
                    );
                  })}

                  {!isMobile && (
                    <>
                      <div className="wc-selector-divider" />
                      <div className="wc-selector-header">Mobile / URL</div>
                      {knownWallets.filter(w => w.mobileScheme && !availableWallets.includes(w.key)).map(wallet => (
                        <button
                          key={`mobile-${wallet.key}`}
                          className="wc-selector-item wc-selector-item-mobile"
                          onClick={() => {
                            setShowSelector(false);
                            if (wallet.key === 'ergopay') {
                              handleErgoPayConnect();
                            } else {
                              handleMobileConnect(wallet);
                            }
                          }}
                        >
                          <span className="wc-selector-wallet-icon">{wallet.icon}</span>
                          <div className="wc-selector-wallet-info">
                            <span className="wc-selector-wallet-name">{wallet.name}</span>
                            <span className="wc-selector-mobile-label">
                              {wallet.key === 'ergopay' ? 'Enter address' : 'Open on phone'}
                            </span>
                          </div>
                          {wallet.key === 'ergopay' ? <QrCode size={12} className="wc-selector-external" /> : <ExternalLink size={12} className="wc-selector-external" />}
                        </button>
                      ))}
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {errorVisible && error && (
          <div className="wc-error-toast">
            <p className="wc-error-msg">{error.message}</p>
            {error.suggestions.length > 0 && (
              <ul className="wc-error-list">
                {error.suggestions.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            )}
            <button className="wc-retry-btn" onClick={() => { setErrorVisible(false); clearError(); handleConnect(); }}>
              <RefreshCw size={13} />
              <span>Retry Connection</span>
            </button>
          </div>
        )}

        {showErgoPayInput && (
          <div className="wc-ergopay-modal">
            <div className="wc-ergopay-modal-content">
              <div className="wc-ergopay-modal-header">
                <QrCode size={20} />
                <span>Connect via ErgoPay</span>
              </div>
              <p className="wc-ergopay-modal-desc">
                Enter your Ergo address to connect via ErgoPay. Transactions will be signed on your mobile wallet.
              </p>
              <input
                type="text"
                className="wc-ergopay-address-input"
                placeholder="9xxx... (Ergo address)"
                value={ergoPayAddress}
                onChange={(e) => setErgoPayAddress(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleErgoPaySubmit(); }}
                autoFocus
              />
              <div className="wc-ergopay-modal-actions">
                <button className="wc-ergopay-cancel-btn" onClick={() => setShowErgoPayInput(false)}>
                  Cancel
                </button>
                <button
                  className="wc-ergopay-connect-btn"
                  onClick={handleErgoPaySubmit}
                  disabled={!ergoPayAddress.trim()}
                >
                  Connect
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ─── Connected state ──────────────────────────────────────────

  return (
    <div className="wc-wrapper">
      <div className={`wc-connected-pill${flash ? ' wc-success-flash' : ''}`}>
        <span className={`wc-status-dot ${isLocked ? 'wc-status-dot-locked' : 'wc-status-dot-connected'}`} />

        {activeWalletInfo && (
          <span className="wc-wallet-badge" title={`Connected via ${activeWalletInfo.name}`}>
            {activeWalletInfo.icon}
          </span>
        )}

        <div className="wc-address-section">
          <button className="wc-address-copy-btn" onClick={handleCopy} title="Copy address">
            <span className="wc-address-text">{formatAddress(walletAddress || '', 6)}</span>
            {copied ? <Check size={12} className="wc-copy-icon" /> : <Copy size={12} className="wc-copy-icon" />}
          </button>
          {network && <span className={`wc-network-badge wc-network-${network}`}>{network.toUpperCase()}</span>}
        </div>

        <span className={`wc-balance-chip${balance === undefined ? ' wc-balance-loading' : ''}`}>
          {balance === undefined ? '\u00a0\u00a0\u00a0\u00a0\u00a0\u00a0\u00a0\u00a0\u00a0\u00a0' : `${formatErg(balance, 4)} ERG`}
        </span>

        {tokens && tokens.length > 0 && (
          <button className="wc-tokens-indicator" onClick={() => setShowTokens(prev => !prev)} title={`${tokens.length} token(s)`}>
            <span>{tokens.length}</span>
            <span className="wc-token-label">Token{tokens.length > 1 ? 's' : ''}</span>
          </button>
        )}

        {/* Wallet switcher (when connected, this disconnects first) */}
        {(availableWallets.length > 1 || (activeWalletKey === 'ergopay' && availableWallets.length > 0)) && (
          <div className="wc-wallet-selector" ref={selectorRef}>
            <button
              className="wc-selector-toggle wc-selector-toggle-small"
              onClick={() => setShowSelector(prev => !prev)}
              title="Switch wallet"
            >
              <ChevronDown size={14} className={`wc-chevron${showSelector ? ' wc-chevron-open' : ''}`} />
            </button>

            {showSelector && (
              <div className="wc-selector-dropdown">
                <div className="wc-selector-header">Switch Wallet</div>
                {availableWallets.map(key => {
                  const info = knownWallets.find(w => w.key === key);
                  if (!info) return null;
                  const isActive = key === activeWalletKey;
                  return (
                    <button
                      key={key}
                      className={`wc-selector-item${isActive ? ' wc-selector-item-active' : ''}`}
                      onClick={() => {
                        setShowSelector(false);
                        if (!isActive) {
                          disconnect().then(() => {
                            setTimeout(() => selectWallet(key), 200);
                          });
                        }
                      }}
                      style={{ '--wallet-color': info.color } as React.CSSProperties}
                    >
                      <span className="wc-selector-wallet-icon">{info.icon}</span>
                      <div className="wc-selector-wallet-info">
                        <span className="wc-selector-wallet-name">{info.name}</span>
                        {isActive && <span className="wc-selector-active-badge">Connected</span>}
                      </div>
                    </button>
                  );
                })}

                {/* Show ErgoPay option if not in availableWallets */}
                {!availableWallets.includes('ergopay') && (
                  <>
                    <div className="wc-selector-divider" />
                    <button
                      key="ergopay"
                      className={`wc-selector-item${activeWalletKey === 'ergopay' ? ' wc-selector-item-active' : ''}`}
                      onClick={() => {
                        setShowSelector(false);
                        if (activeWalletKey !== 'ergopay') {
                          disconnect().then(() => {
                            handleErgoPayConnect();
                          });
                        }
                      }}
                    >
                      <span className="wc-selector-wallet-icon">📱</span>
                      <div className="wc-selector-wallet-info">
                        <span className="wc-selector-wallet-name">ErgoPay</span>
                        {activeWalletKey === 'ergopay' && <span className="wc-selector-active-badge">Connected</span>}
                      </div>
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        <button className="wc-disconnect-btn" onClick={disconnect} title="Disconnect">
          <LogOut size={15} />
        </button>
      </div>

      {isLocked && (
        <div className="wc-warning-toast">
          <AlertCircle size={16} />
          <div>
            <p>Wallet is locked</p>
            <p>Unlock {activeWalletInfo?.name ?? 'your wallet'} to continue.</p>
          </div>
        </div>
      )}

      {showTokens && tokens && tokens.length > 0 && (
        <div className="wc-tokens-dropdown">
          <div className="wc-tokens-header">Token Balances</div>
          {tokens.map((token, i) => (
            <div key={i} className="wc-token-item">
              <span className="wc-token-id">{token.tokenId.slice(0, 12)}...</span>
              <span className="wc-token-amount">{token.amount.toString()}</span>
            </div>
          ))}
        </div>
      )}

      {errorVisible && error && (
        <div className="wc-error-toast">
          <p className="wc-error-msg">{error.message}</p>
          {error.suggestions.length > 0 && (
            <ul className="wc-error-list">
              {error.suggestions.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
          <button className="wc-retry-btn" onClick={() => { setErrorVisible(false); clearError(); handleConnect(); }}>
            <RefreshCw size={13} />
            <span>Retry</span>
          </button>
        </div>
      )}
    </div>
  );
}
