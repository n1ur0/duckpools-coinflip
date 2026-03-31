import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock import.meta.env
vi.stubGlobal('import.meta', {
  env: {
    VITE_NETWORK: 'testnet',
    VITE_EXPLORER_URL: 'https://testnet.ergoplatform.com',
    VITE_API_ENDPOINT: '',
    VITE_NODE_URL: 'http://127.0.0.1:9052',
    VITE_CONTRACT_P2S_ADDRESS: '',
    VITE_CONTRACT_ERGO_TREE: '',
    VITE_HOUSE_PUB_KEY: '',
    VITE_HOUSE_ADDRESS: '',
    VITE_GAME_NFT_ID: '',
    DEV: true,
  },
});

// Mock matchMedia for components that use it
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock crypto.randomUUID polyfill (same as main.tsx)
if (typeof crypto !== 'undefined' && typeof crypto.randomUUID !== 'function') {
  (crypto as any).randomUUID = function randomUUID() {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  };
}
