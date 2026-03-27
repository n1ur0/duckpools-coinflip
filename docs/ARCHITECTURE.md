# Architecture Overview

This document describes the architecture of the DuckPools Coinflip system, including data flow, component interactions, and smart contract design.

## System Overview

DuckPools Coinflip is a decentralized betting game built on Ergo blockchain using a commit-reveal scheme for fair randomness. The system consists of three main components:

1. **Frontend** (React + TypeScript) - User interface and wallet integration
2. **Backend** (FastAPI + Python) - API server, contract interaction, off-chain logic
3. **Blockchain Layer** (Ergo Node + Smart Contracts) - On-chain state and game logic

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  React Components:                                        │   │
│  │  - BetForm.tsx       : Main betting UI                   │   │
│  │  - WalletConnector  : Nautilus EIP-12 integration        │   │
│  │  - GameHistory      : Bet history & stats               │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │ FleetSDK (tx building)                     │
│                     │ ergo-lib-wasm (WASM operations)            │
└─────────────────────┼────────────────────────────────────────────┘
                      │ REST API
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Backend Layer                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FastAPI Routes:                                          │   │
│  │  GET  /health           : Health check                   │   │
│  │  GET  /pool/state       : Pool stats & TVL               │   │
│  │  GET  /history/{addr}   : User bet history               │   │
│  │  POST /place-bet        : Place bet (backend wallet)     │   │
│  │  POST /reveal-bet       : Reveal bet                     │   │
│  │  POST /build-reveal-tx  : Build reveal transaction       │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │ Services:                                  │
│                     │ - blockchain.py  : Ergo node interaction  │   │
│                     │ - pool_state.py  : Pool liquidity mgmt     │   │
└─────────────────────┼────────────────────────────────────────────┘
                      │ REST API (api_key auth)
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Blockchain Layer                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Ergo Node:                                               │   │
│  │  - /wallet/*         : Wallet management                   │   │
│  │  - /blockchain/*     : Blockchain queries                  │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────┼───────────────────────────────────────┐   │
│  │  Smart Contracts (ErgoTree):                              │   │
│  │  - PendingBet   : Holds committed bets                    │   │
│  │  - GameState    : Game configuration & house wallet       │   │
│  │  - House        : P2PK wallet for house funds             │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Off-chain Bot (Python)                        │
│  Monitors PendingBet boxes -> Reveals secrets -> Settles bets   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### Frontend (React + TypeScript)

**Location**: `frontend/src/`

#### Key Components

| Component | Purpose | State Management |
|-----------|---------|------------------|
| `BetForm.tsx` | Main betting interface, handles commit-reveal via Nautilus | Local form state, wallet context |
| `WalletConnector.tsx` | EIP-12 connection to Nautilus wallet | WalletContext |
| `GameHistory.tsx` | Display bet history with win/loss stats | API-fetched data |
| `SimpleBetForm.tsx` | Alternative UI using backend wallet (for testing) | API-fetched data |

#### Wallet Integration

The frontend uses **EIP-12** protocol for wallet interaction via Nautilus browser extension:

1. **Connection**: `window.ergoConnector.nautilus.connect()`
2. **Get Address**: `ergo.get_change_address()`
3. **Sign Transaction**: User signs via Nautilus popup
4. **Submit Transaction**: Frontend submits signed tx to node

#### Transaction Building

Frontend uses **FleetSDK** for building Ergo transactions:

```typescript
import { ErgoTxBuilder, OutputBuilder, Token } from '@fleet-sdk/core';

const tx = new ErgoTxBuilder()
  .from(inputs)  // Select UTXOs
  .to(outputBuilder)  // Create outputs
  .payMinFee()
  .build();
```

### Backend (FastAPI + Python)

**Location**: `backend/`

#### API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | Health check (node + wallet) | None |
| GET | `/pool/state` | Pool liquidity, TVL, house edge | None |
| GET | `/scripts` | Pending bet + house ErgoTrees | None |
| GET | `/history/{address}` | Bet history for address | None |
| POST | `/place-bet` | Place bet (backend wallet signs) | api_key |
| POST | `/reveal-bet` | Reveal a bet | api_key |
| POST | `/resolve-bet` | Build and submit settlement | api_key |
| POST | `/build-reveal-tx` | Build reveal transaction | api_key |

#### Services

**`services/blockchain.py`**
- Wraps Ergo node REST API calls
- Handles wallet operations (unlock, balance, boxes)
- Transaction submission and monitoring

**`services/pool_state.py`**
- Manages pool liquidity state
- Calculates house edge and TVL
- Caches pool stats

#### Wallet Modes

The backend supports **two wallet modes**:

1. **Nautilus Mode** (default): Frontend builds and signs via Nautilus
2. **Backend Wallet Mode**: Backend builds, signs, and submits (for testing)

### Blockchain Layer

#### Ergo Node

Ergo Testnet node running with:
- Mining enabled
- REST API on port 9052
- API key authentication: `blake2b256("hello")`

**Key Endpoints**:
```
GET  /info                            # Node info, height
POST /wallet/unlock                   # Unlock wallet
GET  /wallet/balances                 # Wallet balance
GET  /wallet/boxes/unspent            # Unspent boxes
POST /wallet/transaction/send         # Submit transaction
GET  /blockchain/box/unspent/byTokenId  # Query by NFT
```

#### Smart Contracts

**PendingBet Contract**

Purpose: Holds committed bets waiting for reveal.

**Registers**:
- R4: `Coll[Byte]` - Player's ErgoTree (32 bytes)
- R5: `Coll[Byte]` - Commitment hash (32 bytes)
- R6: `Int` - Bet choice (0=heads, 1=tails)
- R7: `Int` - Player's random secret
- R8: `Coll[Byte]` - Bet ID (32 bytes)

**Spending Rules**:
1. Player can spend after timeout (refund)
2. Reveal path (if implemented): Verify commitment matches revealed secret

**GameState Contract**

Purpose: Stores game configuration and house address.

**Registers**:
- R4: `Coll[Byte]` - House ErgoTree
- R5: `Int` - Timeout height (blocks until refund)
- R6: `Int` - House edge percentage (e.g., 3)

**NFT**: The Coinflip NFT is stored in this box and identifies game instances.

### Off-chain Bot

**Location**: `off-chain-bot/main.py`

The bot runs independently and:

1. **Monitors** PendingBet boxes via `/blockchain/box/unspent/byTokenId/{nft_id}`
2. **Reveals** secrets for committed bets
3. **Calculates** RNG: `SHA256(blockHash || secret)`, outcome = `first_byte % 2`
4. **Settles** bets: pays winner (1.94x), collects loser's funds
5. **Repeats** every block

**Key Functions**:

```python
# sigma_serializer.py - Ergo register serialization
def serialize_int(value: int) -> str:
    """Serialize IntConstant: type_tag(0x02) + VLQ(zigzag)"""
    
def serialize_coll_byte(data: bytes) -> str:
    """Serialize Coll[Byte]: type_tag(0x0E) + element_type(0x01) + VLQ(len) + bytes"""
```

## Data Flow

### Bet Placement Flow

```
User (Frontend) → Nautilus → Ergo Node
1. User generates secret + choice
2. Computes commitment = SHA256(secret || choice)
3. Frontend builds tx with FleetSDK
4. Nautilus signs (user approval popup)
5. Submit to node
6. PendingBet box created with commitment in R5
```

### Bet Resolution Flow

```
Bot → Ergo Node → Blockchain
1. Bot scans for PendingBet boxes
2. For each box: build reveal tx with secret
3. Submit reveal transaction
4. On-chain: RNG = SHA256(blockHash || secret)
5. Outcome = first_byte % 2
6. Build settlement tx:
   - If player wins: 1.94x to player, remainder to house
   - If player loses: all to house
7. Submit settlement
```

### Wallet Connection Flow

```
Frontend → Nautilus Extension → Wallet
1. User clicks "Connect Wallet"
2. Frontend calls window.ergoConnector.nautilus.connect()
3. Nautilus popup: "Allow access?"
4. User approves
5. Nautilus returns address + network info
6. Frontend stores in WalletContext
7. Poll balance every 30s
```

## Security Considerations

### Commit-Reveal Scheme

The commit-reveal scheme prevents front-running:

1. **Commit**: Player submits `SHA256(secret || choice)` without revealing choice
2. **Reveal**: Secret revealed AFTER transaction confirmed, so attacker can't change bet based on upcoming block

### RNG Security

Randomness comes from: `SHA256(blockHash || secret)`

- Block hash is unpredictable (from future block)
- Player secret adds entropy
- House cannot manipulate (no secret submission)

### House Edge

Winning bets pay 1.94x instead of 2x:
- 3% edge = 0.06 * bet_amount
- House keeps 0.06 * bet_amount per winning bet

## Register Serialization

Registers sent to `/wallet/transaction/send` MUST be Sigma-state encoded:

**Int**: `02` + VLQ(zigzag_i32)
```
Int(0) = "0200"
Int(1) = "0202"
Int(10) = "0214"
```

**Coll[Byte]**: `0e` + `01` + VLQ(len) + hex
```
32 bytes = "0e0120" + 64 hex chars
```

**Long**: `04` + VLQ(zigzag_i64)
```
Long(0) = "0400"
Long(1) = "0402"
```

Reference: `off-chain-bot/sigma_serializer.py`

## Port Configuration

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Ergo Node | 9052 | HTTP/JSON | REST API |
| Backend API | 8000 | HTTP/JSON | FastAPI |
| Frontend | 3000 | HTTP | Vite dev server |

## Tech Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + TypeScript | UI + Wallet |
| Frontend | FleetSDK | Ergo tx building |
| Frontend | ergo-lib-wasm | WASM crypto ops |
| Backend | Python 3.12+ | API server |
| Backend | FastAPI | Web framework |
| Backend | httpx | Async HTTP |
| Blockchain | Ergo Testnet | On-chain state |
| Blockchain | ErgoTree | Smart contracts |
| Bot | Python | Bet resolution |

## Future Enhancements

- [ ] Bet timeout/refund spending path in PendingBet contract
- [ ] Player-initiated reveal (on-chain commitment+RNG verification)
- [ ] Pool deposit/withdraw UI
- [ ] Multi-wallet EIP-12 support (SAFEW, Minotaur)
- [ ] Babel fee integration

## References

- [EIP-12: Ergo Wallet Communication Standard](https://github.com/ergoplatform/eips/blob/master/eip-0012.md)
- [ErgoScript Reference](https://github.com/ergoplatform/ergoscript)
- [FleetSDK Documentation](https://fleet-sdk.github.io/)
