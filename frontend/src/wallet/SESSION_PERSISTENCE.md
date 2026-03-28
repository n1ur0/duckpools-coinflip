# Wallet Session Persistence

This document describes the enhanced wallet session persistence feature in DuckPools, which provides seamless wallet connection experiences across page reloads.

## Overview

The wallet session persistence system automatically saves wallet connection state to localStorage when a user connects their wallet, and restores it on subsequent page loads. This eliminates the need for users to manually reconnect their wallets every time they visit the dApp.

## Features

### 1. Automatic Session Saving
- When a user successfully connects their wallet, the connection state is automatically saved
- Includes wallet address, balance, network, and token information
- Sessions are stored with expiration time (24 hours by default)

### 2. Session Restoration
- On page load, the system checks for a saved session
- If found, it immediately displays the persisted state for better UX
- Then validates the session with the wallet to ensure it's still active

### 3. Session Expiration
- Sessions automatically expire after 24 hours for security
- Expired sessions are automatically cleaned up
- Users are prompted to reconnect when sessions expire

### 4. Error Handling
- Gracefully handles localStorage unavailability
- Clears persisted sessions on connection errors
- Handles expired sessions gracefully

## Implementation Details

### Files
- `src/wallet/useWalletSessionPersistence.ts` - Core session persistence hook
- `src/wallet/useErgoWallet.ts` - Enhanced wallet connection hook with session support
- `src/wallet/__tests__/useWalletSessionPersistence.test.ts` - Unit tests
- `src/wallet/__tests__/useErgoWallet-integration.test.ts` - Integration tests

### Data Structure
Sessions are stored in localStorage with the following structure:

```typescript
interface PersistedWalletSession {
  isConnected: boolean;
  walletAddress?: string;
  balance?: number;
  network?: 'testnet' | 'mainnet';
  tokens?: Asset[];
  walletKey: string;
  timestamp: number;
  expiresAt: number;
}
```

### Storage Format
- Sessions are stored as JSON in localStorage
- Multiple wallet sessions can be stored simultaneously
- Key format: `duckpools-wallet-session-list`

## Usage

### For Developers
The session persistence is automatically integrated into the existing wallet system. No additional code is required to use it:

```typescript
import { useWallet } from '../contexts/WalletContext';

function MyComponent() {
  const { isConnected, walletAddress, balance, connect, disconnect } = useWallet();
  
  // Session persistence works automatically behind the scenes
  return (
    <div>
      {isConnected ? (
        <div>
          <p>Connected: {walletAddress}</p>
          <p>Balance: {balance}</p>
          <button onClick={disconnect}>Disconnect</button>
        </div>
      ) : (
        <button onClick={connect}>Connect Wallet</button>
      )}
    </div>
  );
}
```

### Advanced Usage
If you need to interact with the session persistence directly:

```typescript
import { useWalletSessionPersistence } from '../wallet/useWalletSessionPersistence';

function MyAdvancedComponent() {
  const { saveSession, restoreSession, clearSession, hasSession } = useWalletSessionPersistence();
  
  // Check if a session exists for a wallet
  const hasNautilusSession = hasSession('nautilus');
  
  // Manually restore a session
  const session = restoreSession('nautilus');
  
  // Manually clear a session
  const clearSession = () => clearSession('nautilus');
}
```

## Testing

### Unit Tests
The session persistence hook includes comprehensive unit tests covering:
- Session saving and restoration
- Session expiration
- Error handling
- Multiple wallet sessions

Run tests with:
```bash
npm test src/wallet/__tests__/useWalletSessionPersistence.test.ts
```

### Integration Tests
The wallet connection hook has integration tests verifying:
- Session restoration on mount
- Session saving on connection
- Session clearing on disconnect
- Error scenarios

Run tests with:
```bash
npm test src/wallet/__tests__/useErgoWallet-integration.test.ts
```

## Security Considerations

1. **Session Duration**: Sessions expire after 24 hours to reduce security risks
2. **Local Storage Only**: Sessions are stored only in the browser's localStorage
3. **Validation**: Sessions are validated with the wallet before use
4. **Clearing**: Sessions are cleared on disconnect or error

## Browser Compatibility

The session persistence feature uses localStorage, which is supported in all modern browsers. However, it includes fallback behavior for when localStorage is unavailable (e.g., in private browsing mode).

## Future Enhancements

Potential future improvements:
1. **Customizable session duration**: Allow apps to configure session expiration
2. **Encrypted storage**: Encrypt session data for additional security
3. **Multi-device sync**: Sync sessions across devices using remote storage
4. **Session events**: Emit events when sessions are saved/restored/expired