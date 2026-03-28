# Nautilus EIP-12 Wallet Connection Hook with Session Persistence

This document describes the `useNautilusWallet` hook, which provides a simple interface for connecting to Nautilus wallet with automatic session persistence.

## Overview

The `useNautilusWallet` hook combines:
- EIP-12 wallet connection functionality (Nautilus-specific)
- Automatic session persistence
- Session restoration on component mount
- Session cleanup on disconnect

## Features

- **Automatic Session Persistence**: Saves wallet connection state to localStorage
- **Session Restoration**: Automatically restores sessions when the component mounts
- **Session Cleanup**: Clears sessions when wallet is disconnected
- **Error Handling**: Provides clear error messages and suggestions
- **Type Safety**: Full TypeScript support with comprehensive type definitions

## Installation

The hook is included in the DuckPools frontend. Import it from the wallet module:

```typescript
import { useNautilusWallet } from './src/wallet';
```

## Usage

### Basic Usage

```typescript
import { useNautilusWallet } from './src/wallet';

function MyComponent() {
  const {
    isConnected,
    isConnecting,
    walletAddress,
    balance,
    tokens,
    error,
    connect,
    disconnect,
    hasPersistedSession,
  } = useNautilusWallet();

  return (
    <div>
      {isConnected ? (
        <div>
          <p>Connected: {walletAddress}</p>
          <p>Balance: {balance} ERG</p>
          <button onClick={disconnect}>Disconnect</button>
        </div>
      ) : (
        <button 
          onClick={connect}
          disabled={isConnecting}
        >
          {isConnecting ? 'Connecting...' : 'Connect Nautilus'}
        </button>
      )}
      
      {error && (
        <div className="error">
          {error.message}
          <ul>
            {error.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

### With the NautilusWalletConnect Component

For a complete solution with UI, use the provided `NautilusWalletConnect` component:

```typescript
import { NautilusWalletConnect } from './src/components/NautilusWalletConnect';

function MyApp() {
  const handleConnect = (address: string) => {
    console.log('Wallet connected:', address);
  };

  const handleDisconnect = () => {
    console.log('Wallet disconnected');
  };

  return (
    <NautilusWalletConnect 
      onConnect={handleConnect}
      onDisconnect={handleDisconnect}
    />
  );
}
```

## API Reference

### Return Values

The hook returns an object with the following properties:

#### Connection State
- `isConnected: boolean` - Whether the wallet is currently connected
- `isConnecting: boolean` - Whether a connection attempt is in progress
- `isLocked: boolean` - Whether the wallet is locked (needs user interaction)
- `walletAddress?: string` - The connected wallet address
- `balance?: number` - The wallet balance in ERG
- `network?: 'testnet' | 'mainnet'` - The current network
- `tokens?: Asset[]` - Array of tokens in the wallet
- `error?: WalletError` - Error information if something went wrong
- `ergo: EIP12ContextAPI | null` - The EIP-12 context API object

#### Session State
- `hasPersistedSession: boolean` - Whether a persisted session exists

#### Actions
- `connect(): Promise<void>` - Connect to Nautilus wallet
- `disconnect(): Promise<void>` - Disconnect from wallet and clear session
- `refreshBalance(): Promise<void>` - Refresh the wallet balance
- `getUtxos(): Promise<ErgoBox[]>` - Get wallet UTXOs
- `getCurrentHeight(): Promise<number>` - Get current blockchain height
- `getChangeAddress(): Promise<string | null>` - Get change address
- `signTransaction(tx: UnsignedTransaction): Promise<SignedTransaction | null>` - Sign a transaction
- `submitTransaction(tx: SignedTransaction): Promise<string | null>` - Submit a transaction
- `clearError(): void` - Clear any current error

#### Session Actions
- `clearSession(): void` - Manually clear the persisted session

### Error Handling

The hook provides detailed error information through the `error` property:

```typescript
interface WalletError {
  code: WalletErrorCode;
  message: string;
  suggestions: string[];
}

type WalletErrorCode =
  | 'wallet_not_found'
  | 'wallet_not_responsive'
  | 'preflight_timeout'
  | 'timeout_error'
  | 'user_rejected'
  | 'network_mismatch'
  | 'wallet_error'
  | 'signing_error'
  | 'submission_error'
  | 'invalid_transaction';
```

## Session Persistence

### How It Works

1. **Automatic Save**: When a wallet is successfully connected, the session is automatically saved to localStorage
2. **Automatic Restore**: When the component mounts, the hook checks for a persisted session and restores it if available
3. **Automatic Cleanup**: When the wallet is disconnected, the session is automatically cleared
4. **Session Expiration**: Sessions expire after 24 hours for security

### Session Data

The following data is persisted:
- Connection status
- Wallet address
- Balance
- Network (testnet/mainnet)
- Tokens
- Timestamp and expiration

### Security Considerations

- Sessions expire after 24 hours
- No private keys or sensitive data is stored
- Sessions are cleared when wallet is disconnected
- Graceful degradation when localStorage is unavailable

## Browser Support

The hook requires:
- Modern browser with EIP-12 wallet support
- Nautilus wallet extension installed
- localStorage available

## Testing

The hook includes comprehensive tests covering:
- Connection flow
- Session persistence
- Error handling
- Session cleanup

Run tests with:

```bash
npm test src/wallet/__tests__/useNautilusWallet.test.ts
```

## Examples

See the `NautilusWalletConnect` component for a complete implementation example.

## Troubleshooting

### Common Issues

1. **"Wallet not found" error**
   - Install Nautilus wallet extension
   - Enable the extension in browser settings
   - Refresh the page

2. **"Popup blocked" warning**
   - Allow popups for the application URL
   - Check browser popup settings

3. **"Network mismatch" error**
   - Switch Nautilus wallet to the correct network (testnet/mainnet)
   - Ensure the dApp is configured for the same network

4. **"Session expired"**
   - Reconnect the wallet
   - Sessions expire after 24 hours for security

### Debug Mode

The hook includes debug logging in development mode. Check the browser console for detailed information about:
- Connection attempts
- Session operations
- Error details

## Related Documentation

- [EIP-12 Specification](https://github.com/ergoplatform/eips/blob/master/eip-0012.md)
- [Nautilus Wallet Documentation](https://github.com/nautls/nautilus-wallet)
- [DuckPools Architecture](./docs/ARCHITECTURE.md)