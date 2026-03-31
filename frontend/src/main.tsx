/**
 * Polyfill: crypto.randomUUID()
 *
 * crypto.randomUUID() is only available in secure contexts (HTTPS / localhost).
 * In non-secure contexts (HTTP on a LAN IP, file://, some embedded WebViews),
 * calling it throws "crypto.randomUUID is not a function".
 *
 * This polyfill runs before any other code, so it covers:
 *   - Our own code (generateUUID in utils/crypto.ts)
 *   - Third-party dependencies (Fleet SDK, Nautilus extension bridge)
 *   - The Nautilus wallet extension itself (some versions call it internally)
 *
 * Uses crypto.getRandomValues() which IS available in all modern browsers.
 */
if (typeof crypto !== 'undefined' && typeof crypto.randomUUID !== 'function') {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (crypto as any).randomUUID = function randomUUID() {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant 1
    const hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  };
}

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
