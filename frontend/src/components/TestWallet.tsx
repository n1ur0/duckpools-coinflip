import { useState, useCallback } from 'react';
import { useWallet } from '../contexts/WalletContext';
import './TestWallet.css';

export default function TestWallet() {
  const {
    isConnected,
    isConnecting,
    isLocked,
    walletAddress,
    balance,
    network,
    tokens,
    error,
    connect,
    disconnect,
    getUtxos,
    getCurrentHeight,
    getChangeAddress,
  } = useWallet();

  const [rawResponse, setRawResponse] = useState<string>('');
  const [testLoading, setTestLoading] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const runTest = useCallback(
    async (name: string, fn: () => Promise<unknown>) => {
      setTestLoading(name);
      setTestError(null);
      setRawResponse('');

      try {
        const result = await fn();
        setRawResponse(
          typeof result === 'string'
            ? result
            : JSON.stringify(result, null, 2)
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setTestError(`${name}: ${msg}`);
        setRawResponse(msg);
      } finally {
        setTestLoading(null);
      }
    },
    []
  );

  const stateItems = [
    { key: 'Connected', value: isConnected, type: 'bool' as const },
    { key: 'Connecting', value: isConnecting, type: 'bool' as const },
    { key: 'Locked', value: isLocked, type: 'bool' as const },
    { key: 'Address', value: walletAddress || '—', type: 'text' as const },
    {
      key: 'Balance',
      value: balance !== undefined ? `${balance} nanoERG` : '—',
      type: 'text' as const,
    },
    { key: 'Network', value: network || '—', type: 'text' as const },
    { key: 'Tokens', value: tokens?.length ?? 0, type: 'text' as const },
    { key: 'Error', value: error?.message || 'none', type: 'text' as const },
  ];

  return (
    <div className="tw-container">
      <h3 className="tw-title">Test Wallet (Dev)</h3>

      {/* ── State Grid ────────────────────────────────────────────── */}
      <div className="tw-state-grid">
        {stateItems.map((item) => (
          <div key={item.key} className="tw-state-item">
            <div className="tw-state-key">{item.key}</div>
            <div
              className={`tw-state-val${
                item.type === 'bool'
                  ? item.value
                    ? ' tw-state-val--true'
                    : ' tw-state-val--false'
                  : ''
              }`}
            >
              {item.type === 'bool'
                ? String(item.value)
                : String(item.value)}
            </div>
          </div>
        ))}
      </div>

      {/* ── Action Buttons ────────────────────────────────────────── */}
      <div className="tw-actions">
        <button
          className="tw-btn"
          onClick={() => runTest('connect', connect)}
          disabled={isConnecting || isConnected}
        >
          {testLoading === 'connect' && <span className="tw-spinner" />}
          Connect
        </button>
        <button
          className="tw-btn"
          onClick={() => runTest('disconnect', disconnect)}
          disabled={!isConnected}
        >
          {testLoading === 'disconnect' && <span className="tw-spinner" />}
          Disconnect
        </button>
        <button
          className="tw-btn"
          onClick={() => runTest('getUtxos', () => getUtxos().then((u) => u.map((box) => ({ boxId: box.boxId, value: box.value }))))}
          disabled={!isConnected}
        >
          {testLoading === 'getUtxos' && <span className="tw-spinner" />}
          getUtxos
        </button>
        <button
          className="tw-btn"
          onClick={() => runTest('getCurrentHeight', () => getCurrentHeight().then(String))}
          disabled={!isConnected}
        >
          {testLoading === 'getCurrentHeight' && (
            <span className="tw-spinner" />
          )}
          getHeight
        </button>
        <button
          className="tw-btn"
          onClick={() =>
            runTest('getChangeAddress', () =>
              getChangeAddress().then((addr) => addr || 'null')
            )
          }
          disabled={!isConnected}
        >
          {testLoading === 'getChangeAddress' && (
            <span className="tw-spinner" />
          )}
          getChangeAddress
        </button>
      </div>

      {/* ── Error Display ─────────────────────────────────────────── */}
      {testError && <div className="tw-error">{testError}</div>}

      {/* ── Raw Response ──────────────────────────────────────────── */}
      {rawResponse && (
        <div className="tw-response">
          <div className="tw-response-label">Response</div>
          {rawResponse}
        </div>
      )}
    </div>
  );
}
