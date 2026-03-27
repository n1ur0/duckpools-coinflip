# @duckpools/sdk

TypeScript SDK for the DuckPools provably-fair gambling protocol on the Ergo blockchain.

## Features

- **Commit-Reveal RNG** - SHA256-based commitment scheme with provably-fair outcomes
- **Sigma-State Serialization** - Full SValue encoding/decoding (Int, Long, Coll[Byte], SigmaProp)
- **Ergo Node Client** - Complete REST API wrapper for node interaction
- **Bet Manager** - High-level place/reveal/refund bet operations
- **Transaction Builder** - Build Ergo transactions with proper register encoding
- **LP Pool Support** - Bankroll pool management, deposit/withdraw, APY calculations
- **Isomorphic** - Works in both browser (Web Crypto API) and Node.js environments

## Installation

```bash
npm install @duckpools/sdk
```

## Quick Start

```typescript
import { DuckPoolsClient, generateCommit, computeRng } from '@duckpools/sdk';

// Create client
const client = DuckPoolsClient.create({
  url: 'http://localhost:9052',
  apiKey: 'your-api-key',
  network: 'testnet',
  houseAddress: '3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26',
  coinflipNftId: 'your-coinflip-nft-id',
  pendingBetAddress: 'your-pending-bet-address',
});

// Place a bet
const result = await client.placeBet({
  amount: 1_000_000_000n, // 1 ERG in nanoERG
  choice: 0, // heads
  timeoutDelta: 100, // blocks until refund
});
console.log('Bet placed:', result.transactionId);
console.log('Commitment:', result.commitment);

// Reveal a bet
const reveal = await client.revealBet({
  boxId: result.boxId,
  secret: result.secret,
  choice: 0,
});
console.log('Result:', reveal.result); // 'win' or 'lose'
console.log('Payout:', reveal.payout);
```

## Crypto Utilities

```typescript
import { generateSecret, generateCommit, verifyCommit, computeRng } from '@duckpools/sdk';

// Generate commitment
const { secret, commitment } = await generateCommit(undefined, 0);
// secret = "a1b2c3d4e5f6a7b8" (8 random bytes)
// commitment = SHA256(secret || choice)

// Verify commitment
const valid = await verifyCommit(commitment, secret, 0);

// Compute RNG outcome from block hash
const outcome = await computeRng(blockHash, secret);
// outcome = 0 (heads) or 1 (tails)
```

## Serialization

All register values sent to the Ergo node must use Sigma-state type encoding:

```typescript
import { serializeInt, serializeLong, serializeCollByte, serializeSValue } from '@duckpools/sdk';

// Int: type_tag(0x02) + VLQ(zigzag)
serializeInt(10);   // "0214"
serializeInt(0);    // "0200"

// Long: type_tag(0x04) + VLQ(zigzag)
serializeLong(1000000000n); // "0410a5d4e800"

// Coll[Byte]: type_tag(0x0E) + element_type(0x01) + VLQ(length) + data
serializeCollByte('a1b2c3d4'); // "0e0104a1b2c3d4"

// Auto-serialize based on SValue type
serializeSValue({ type: 'Int', value: 42 });
serializeSValue({ type: 'Coll[Byte]', value: 'deadbeef' });
```

## Pool Module

```typescript
import {
  PoolManager,
  HttpPoolClient,
  PoolFormatters,
  calculateAPY,
  calculateDepositShares,
} from '@duckpools/sdk';

// Frontend: HTTP client
const poolClient = new HttpPoolClient('/api');
const state = await poolClient.getPoolState();
console.log('TVL:', PoolFormatters.nanoErgToErg(state.totalValue));

// Backend: Direct node client
const poolManager = new PoolManager({
  nodeClient,
  poolNftId: 'pool-nft-id',
  lpTokenId: 'lp-token-id',
});
const deposit = await poolManager.estimateDeposit(10_000_000_000n);
console.log('Shares:', deposit.shares);
console.log('Price:', deposit.pricePerShare);

// APY calculation
const apy = calculateAPY(300, 1_000_000_000n, 0.1, 100_000_000_000_000n);
console.log('APY:', apy, '%');
```

## Architecture

```
src/
  index.ts                  # Main entry point
  types/index.ts            # All TypeScript types and error classes
  client/
    NodeClient.ts           # Ergo node REST API wrapper
    DuckPoolsClient.ts      # High-level protocol client
  transaction/
    TransactionBuilder.ts   # Transaction construction + wallet format
  bet/
    BetManager.ts           # Place/reveal/refund bet operations
  crypto/index.ts           # SHA256, commitments, RNG computation
  serialization/index.ts    # SValue encoding/decoding (VLQ, ZigZag)
  pool/
    BankrollPool.ts         # Pool contracts, config, math functions
    PoolManager.ts          # On-chain pool state queries
    PoolClient.ts           # HTTP frontend pool client
    types.ts                # Pool-specific type definitions
```

## Commit-Reveal Protocol

1. **Commit**: Player generates 8-byte random secret + choice byte, submits `SHA256(secret || choice)` as commitment
2. **Reveal**: After block confirmation, reveal secret. Contract verifies `SHA256(revealed || choice) == commitment`
3. **RNG**: Outcome = `SHA256(blockHash_as_utf8 || secret_bytes)[0] % 2`
4. **Settlement**: Winner gets `2 * betAmount * (1 - houseEdge)`, loser forfeits

## Requirements

- Node.js >= 18.0.0 or modern browser
- Access to an Ergo node (local or remote)
- TypeScript 5.3+ (for development)

## License

MIT
