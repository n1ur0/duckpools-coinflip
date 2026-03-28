// Network and API utilities

const API_BASE = process.env.VITE_API_ENDPOINT || '';

export function buildApiUrl(endpoint: string): string {
  if (process.env.NODE_ENV === 'development') return `/api${endpoint}`;
  return `${API_BASE}${endpoint}`;
}

export function getNodeUrl(): string {
  return process.env.VITE_NODE_URL || 'https://api-testnet.ergoplatform.com';
}

export function getExpectedNetworkType(): 'testnet' | 'mainnet' {
  return (process.env.VITE_NETWORK as 'testnet' | 'mainnet') || 'testnet';
}

/**
 * Detect network type from an Ergo address prefix.
 *
 * IMPORTANT: On testnet, addressPrefix=16, so P2PK addresses start with '3W'
 * and P2S addresses start with '2'. Do NOT flag 3W as mainnet.
 *
 * Mainnet: P2PK='3', P2S='9h'
 * Testnet: P2PK='3W', P2S='2'
 */
export function getNetworkFromAddress(address: string): 'testnet' | 'mainnet' | undefined {
  if (!address || address.length < 2) return undefined;

  const prefix = address.substring(0, 2);

  // Testnet detection (more specific first)
  if (prefix === '3W' || prefix === '2-') return 'testnet';

  // Mainnet detection
  if (prefix === '3' || prefix === '9h' || prefix === '9i' || prefix === '9j' || prefix === '9k' || prefix === '9a' || prefix === '9b' || prefix === '9c' || prefix === '9d' || prefix === '9e' || prefix === '9f' || prefix === '9g') return 'mainnet';

  return undefined;
}
