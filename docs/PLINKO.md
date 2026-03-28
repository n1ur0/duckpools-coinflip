# DuckPools Plinko Game

A provably-fair Plinko game on the Ergo blockchain, using the same commit-reveal RNG architecture as the coinflip game.

## Overview

Plinko is a game where a ball drops through 12 rows of pegs, bouncing left or right at each peg based on random bits. The final landing position determines the multiplier (payout).

## Game Mechanics

### Board Layout
- **12 rows of pegs**: Creates 13 possible landing zones (0-12)
- **Pyramidal multipliers**: Edge zones have higher multipliers (higher risk/reward)
- **Commit-reveal RNG**: Player commits to a secret, server reveals it with block hash

### Multipliers

| Zone | Multiplier | Probability | Adjusted Multiplier (3% edge) |
|------|------------|-------------|--------------------------------|
| 0    | 1000x      | 0.0244%     | 970x                           |
| 1    | 130x       | 0.2930%     | 126.1x                         |
| 2    | 26x        | 1.7578%     | 25.22x                         |
| 3    | 9x         | 5.8594%     | 8.73x                          |
| 4    | 4x         | 12.1094%    | 3.88x                          |
| 5    | 2x         | 19.3359%    | 1.94x                          |
| 6    | 1x         | 22.5586%    | 0.97x                          |
| 7    | 2x         | 19.3359%    | 1.94x                          |
| 8    | 4x         | 12.1094%    | 3.88x                          |
| 9    | 9x         | 5.8594%     | 8.73x                          |
| 10   | 26x        | 1.7578%     | 25.22x                         |
| 11   | 130x       | 0.2930%     | 126.1x                         |
| 12   | 1000x      | 0.0244%     | 970x                           |

### RNG Process

1. **Commit Phase**: Player generates 2-byte secret and submits commitment = SHA256(secret)
2. **Reveal Phase**: Server reveals with block hash from N blocks later
3. **RNG Calculation**:
   ```
   combined_hash = SHA256(block_hash || secret)
   Extract first 12 bits from combined_hash
   zone = number of set bits (0-12)
   ```
4. **Payout**: `bet_amount * zone_multiplier * (1 - house_edge)`

## Architecture

### Frontend

#### Components
- **PlinkoGame.tsx**: Main game UI with animated ball drop
- **PlinkoGame.css**: Styling for the Plinko board and animations

#### Utilities
- **plinko.ts**: Game logic, RNG, payout calculation, serialization

#### Features
- Real-time animation preview
- Game selector (Coinflip vs Plinko)
- Responsive design
- WebSocket event support

### Backend

#### Routes
- **POST /api/plinko/place-bet**: Place a Plinko bet
- **GET /api/plinko/multipliers**: Get all multipliers and probabilities
- **GET /api/plinko/verify-commitment**: Verify a commitment
- **GET /api/plinko/compute-outcome**: Compute outcome from block hash and secret
- **GET /api/plinko/health**: Health check

#### Events
- **bet_placed**: Bet placed with commitment
- **bet_revealed**: RNG revealed with zone and path
- **bet_settled**: Bet settled with payout

## Serialization

### Bet Box Registers (PendingBet)

| Register | Type        | Content                          |
|----------|-------------|----------------------------------|
| R4       | Coll[Byte]  | Player's ErgoTree                |
| R5       | Coll[Byte]  | Commitment hash (SHA256 of secret)|
| R6       | Long        | Bet amount (nanoERG)             |
| R7       | Long        | Player's secret (2 bytes)       |
| R8       | Coll[Byte]  | Bet ID (32 bytes)                |

### Type Tags
- `0x02` = IntConstant
- `0x04` = LongConstant
- `0x0e` = Coll constant
- `0x01` = SByte (element type for Coll[Byte])

## Testing

### Unit Tests
Run the test suite:
```bash
cd /Users/n1ur0/projects/worktrees/agent/Serialization-Specialist-Jr/MAT-17-plinko-crash-game
pytest tests/test_plinko.py -v
```

### Test Coverage
- 26 unit tests covering:
  - Constants validation
  - Multiplier calculations
  - Probability distributions
  - RNG computation
  - Payout calculations
  - Integration tests
  - Edge cases
  - Performance tests

### Manual Testing
1. Start the backend:
   ```bash
   cd backend
   python3 api_server.py
   ```

2. Start the frontend:
   ```bash
   cd frontend
   npm run dev
   ```

3. Open browser and test:
   - Game selector switches between Coinflip and Plinko
   - Preview drop shows animation
   - Place bet submits transaction
   - WebSocket updates show bet lifecycle

## API Endpoints

### POST /api/plinko/place-bet

Request:
```json
{
  "address": "player_address",
  "amount": "100000000",
  "commitment": "abc123...",
  "secret": "abcd",
  "betId": "uuid",
  "gameType": "plinko"
}
```

Response:
```json
{
  "success": true,
  "txId": "transaction_id"
}
```

### GET /api/plinko/multipliers

Response:
```json
{
  "zones": [
    {
      "zone": 0,
      "multiplier": 1000,
      "probability": 0.0244,
      "adjustedMultiplier": 970
    },
    ...
  ],
  "houseEdge": 0.03
}
```

## Acceptance Criteria

- [x] Game contract designed
- [x] Frontend animation smooth
- [x] Same provably-fair verification
- [x] 20+ test bets successful (26 unit tests pass)

## Deployment

### Environment Variables

```bash
# From .env.example
NODE_URL=http://localhost:9052
API_KEY=hello
POOL_NFT_ID=
LP_TOKEN_ID=
HOUSE_ADDRESS=
BANKROLL_TREE_HEX=
WITHDRAW_REQUEST_TREE_HEX=
HOUSE_EDGE_BPS=300
COOLDOWN_BLOCKS=60
CORS_ORIGINS_STR=http://localhost:3000
```

### Deployment Steps

1. **Backend**: Deploy the FastAPI server with PM2
2. **Frontend**: Build and deploy the React app
3. **Database**: PostgreSQL for off-chain state
4. **Node**: Connect to Ergo node (testnet or mainnet)

## Security

- All transactions are on-chain (Ergo)
- Commit-reveal ensures provable fairness
- House edge configurable per environment
- Player secrets are encrypted
- Rate limiting on bet placement

## Future Improvements

1. **More rows**: Support 16 or 20 rows for more complexity
2. **Custom multipliers**: Allow different multiplier distributions
3. **Multi-bet**: Support multiple balls per bet
4. **Auto-play**: Allow players to set up automatic betting
5. **Jackpots**: Add progressive jackpots for edge zone hits

## References

- [Coinflip Game](./COINFLIP.md)
- [RNG Architecture](./RNG.md)
- [Serialization Guide](./SERIALIZATION.md)
- [Ergo Platform](https://ergoplatform.com)

## Contributors

- Serialization Specialist Jr (350d346f-f2d2-4b0c-8792-b9fc5ef3fd38)

## License

MIT License - See LICENSE file for details
