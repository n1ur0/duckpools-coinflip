# DuckPools CoinFlip - API Reference

This document provides detailed information about the DuckPools CoinFlip API endpoints.

## Base URL

- Development: `http://localhost:8000`
- Production: `https://api.duckpools.com`

## Authentication

Most endpoints don't require authentication for basic usage. Some endpoints (like bot endpoints) may require API keys.

## Endpoints

### Game Endpoints

#### POST `/place-bet`

Place a new coinflip bet.

**Request:**
```json
{
  "player_address": "string",  // Player's Ergo address
  "amount": "integer",        // Bet amount in nanoERG (1 ERG = 1,000,000,000 nanoERG)
  "choice": "integer",        // 0=heads, 1=tails
  "secret": "string"          // 32-byte random secret (hex encoded)
}
```

**Response:**
```json
{
  "bet_id": "string",         // Unique bet identifier
  "status": "string",         // "pending", "won", "lost", "refunded"
  "amount": "integer",        // Bet amount
  "choice": "integer",        // Player's choice
  "timeout_height": "integer",// Block height for timeout
  "created_at": "string",     // Timestamp
  "updated_at": "string"      // Timestamp
}
```

#### GET `/history/{address}`

Get bet history for a specific address.

**Parameters:**
- `address`: Player's Ergo address

**Response:**
```json
{
  "address": "string",
  "bets": [
    {
      "bet_id": "string",
      "status": "string",
      "amount": "integer",
      "choice": "integer",
      "outcome": "integer",    // 0=heads, 1=tails (null if pending)
      "created_at": "string",
      "updated_at": "string",
      "timeout_height": "integer"
    }
  ]
}
```

#### GET `/player/stats/{address}`

Get player statistics.

**Parameters:**
- `address`: Player's Ergo address

**Response:**
```json
{
  "address": "string",
  "total_bets": "integer",
  "wins": "integer",
  "losses": "integer",
  "refunds": "integer",
  "win_rate": "float",
  "total_won": "integer",
  "total_lost": "integer",
  "net_profit": "integer"
}
```

#### GET `/player/comp/{address}`

Get player compensation.

**Parameters:**
- `address`: Player's Ergo address

**Response:**
```json
{
  "address": "string",
  "compensation": "integer",   // Compensation amount in nanoERG
  "status": "string",         // "pending", "paid", "claimed"
  "created_at": "string",
  "updated_at": "string"
}
```

#### GET `/leaderboard`

Get global leaderboard.

**Response:**
```json
{
  "leaderboard": [
    {
      "address": "string",
      "total_bets": "integer",
      "wins": "integer",
      "losses": "integer",
      "win_rate": "float",
      "total_won": "integer",
      "total_lost": "integer",
      "net_profit": "integer",
      "rank": "integer"
    }
  ]
}
```

### Timeout Management Endpoints

#### GET `/bets/{bet_id}/timeout`

Get timeout information for a specific bet.

**Parameters:**
- `bet_id`: Unique bet identifier

**Response:**
```json
{
  "bet_id": "string",
  "timeout_height": "integer",
  "current_height": "integer",
  "time_remaining": "integer", // Blocks remaining
  "status": "string",         // "active", "expiring", "expired"
  "refund_possible": "boolean"
}
```

#### GET `/bets/expired`

Get list of all expired bets.

**Query Parameters:**
- `limit`: Maximum number of results (default: 100)
- `offset`: Offset for pagination

**Response:**
```json
{
  "expired_bets": [
    {
      "bet_id": "string",
      "player_address": "string",
      "amount": "integer",
      "choice": "integer",
      "timeout_height": "integer",
      "created_at": "string",
      "updated_at": "string"
    }
  ],
  "total": "integer",
  "limit": "integer",
  "offset": "integer"
}
```

#### POST `/bets/{bet_id}/refund-record`

Record a refund transaction.

**Request:**
```json
{
  "tx_id": "string",          // Transaction ID
  "refund_amount": "integer"  // Refund amount in nanoERG
}
```

**Response:**
```json
{
  "status": "string",         // "success", "error"
  "message": "string",
  "bet_id": "string"
}
```

#### GET `/bets/pending-with-timeout`

Get pending bets sorted by urgency (approaching timeout).

**Query Parameters:**
- `limit`: Maximum number of results (default: 50)

**Response:**
```json
{
  "pending_bets": [
    {
      "bet_id": "string",
      "player_address": "string",
      "amount": "integer",
      "choice": "integer",
      "timeout_height": "integer",
      "time_remaining": "integer",
      "created_at": "string"
    }
  ],
  "total": "integer"
}
```

### WebSocket Endpoints

#### GET `/ws`

Establish WebSocket connection for real-time updates.

**Events:**
- `bet_placed`: New bet placed
- `bet_updated`: Bet status changed
- `game_completed`: Game resolved
- `player_joined`: New player joined
- `player_left`: Player left

**Example:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

### Health Check

#### GET `/health`

Check system health.

**Response:**
```json
{
  "status": "string",         // "healthy", "degraded", "unhealthy"
  "timestamp": "string",
  "components": {
    "database": "string",
    "node": "string",
    "backend": "string"
  }
}
```

### Configuration

#### GET `/config`

Get system configuration.

**Response:**
```json
{
  "max_bet": "integer",       // Maximum bet amount in nanoERG
  "fee_percentage": "float",  // House fee percentage
  "timeout_blocks": "integer" // Timeout in blocks
}
```

## Error Handling

### Common Error Responses

```json
{
  "error": "string",
  "message": "string",
  "code": "string"
}
```

### Error Codes

- `INVALID_ADDRESS`: Invalid Ergo address
- `INSUFFICIENT_FUNDS`: Insufficient funds
- `INVALID_CHOICE`: Invalid choice (must be 0 or 1)
- `INVALID_SECRET`: Invalid secret format
- `BET_NOT_FOUND`: Bet not found
- `TIMEOUT_EXPIRED`: Bet timeout expired
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded

## Rate Limiting

- 100 requests per minute per IP
- 1000 requests per hour per API key
- Burst capacity: 200 requests

## Response Format

All successful responses follow this format:
```json
{
  "success": true,
  "data": "any",             // Response data
  "message": "string"        // Optional message
}
```

## Examples

### Python Example

```python
import requests

# Place a bet
response = requests.post(
    "http://localhost:8000/place-bet",
    json={
        "player_address": "9f6Kj8Wz7x9Fj2aT5mB3c1v8x7z9w4e2r",
        "amount": 1000000,  # 1 ERG
        "choice": 0,       # Heads
        "secret": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6"
    }
)

if response.status_code == 200:
    bet_data = response.json()
    print("Bet placed successfully:", bet_data)
else:
    print("Error:", response.json())
```

### JavaScript Example

```javascript
// Place a bet using fetch
async function placeBet() {
  const response = await fetch('http://localhost:8000/place-bet', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      player_address: '9f6Kj8Wz7x9Fj2aT5mB3c1v8x7z9w4e2r',
      amount: 1000000,
      choice: 0,
      secret: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6'
    })
  });

  const data = await response.json();
  if (response.ok) {
    console.log('Bet placed:', data);
  } else {
    console.error('Error:', data);
  }
}

placeBet();
```

--- 
*API endpoints and parameters may change. Always refer to the latest documentation.*