# DuckPools CoinFlip - Agent Development Guide

## Overview

This guide provides comprehensive instructions for agent developers working with the DuckPools CoinFlip system. The system is built on the Ergo blockchain using a commit-reveal pattern for fair gambling.

## System Architecture

### Core Components

1. **Smart Contracts** (`smart-contracts/` directory)
   - `coinflip_v1.es`: Main coinflip contract with commit-reveal pattern
   - `coinflip_v2.es`, `coinflip_v3.es`: Alternative contract versions
   - `dice_v1.es`, `plinko_v1.es`: Other game contracts
   - All contracts use ErgoScript and follow the commit-reveal pattern

2. **Backend** (`backend/` directory)
   - `api_server.py`: Main FastAPI server
   - `game_routes.py`: Game API endpoints
   - `rng_module.py`: Random number generation module
   - `ws_routes.py`: WebSocket routes for real-time updates

3. **Frontend** (`frontend/` directory)
   - React 18 + TypeScript application
   - Wallet integration via Nautilus (EIP-12)
   - Game UI components

4. **Database**
   - PostgreSQL for off-chain state management
   - Stores bet history, player stats, etc.

## Development Environment Setup

### Prerequisites

- Python 3.8+ (for backend)
- Node.js 16+ (for frontend)
- Docker and Docker Compose (for containerized setup)
- Nautilus wallet extension (for testing)
- Git

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/duckpools/duckpools-coinflip.git
cd duckpools-coinflip/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the backend server
python api_server.py
```

### Frontend Setup

```bash
cd ../frontend
npm install
npm run dev
```

### Docker Setup (Recommended)

```bash
# Start all services
docker-compose up -d

# Access services
# - Backend: http://localhost:8000
# - Frontend: http://localhost:3000
# - Ergo Node: http://localhost:9052
# - PostgreSQL: localhost:5432
```

## Smart Contract Development

### Contract Structure

Each contract follows the commit-reveal pattern:

```ergoscript
# Coinflip contract example
val playerSecret: Int = fromSelf.R9[Int].get  # Player secret (32 bytes)
val playerChoice: Int = fromSelf.R7[Int].get  # Player choice (0=heads, 1=tails)
val commitmentHash: Coll[Byte] = fromSelf.R6[Coll[Byte]].get

# Commitment verification
blake2b256(R9[Secret] ++ R7[Choice]) == R6[CommitmentHash]

# RNG outcome
blake2b256(prevBlockHash ++ R9[Secret])[0] % 2
```

### Contract Registers

| Register | Type | Content |
|----------|------|---------|
| R4 | Coll[Byte] | House compressed public key (33 bytes) |
| R5 | Coll[Byte] | Player compressed public key (33 bytes) |
| R6 | Coll[Byte] | Commitment hash: blake2b256(secret || choice) (32 bytes) |
| R7 | Int | Player choice: 0=heads, 1=tails |
| R8 | Int | Timeout height for refund (currentHeight + 100) |
| R9 | Coll[Byte] | Player secret (32 random bytes) |

### Testing Contracts

```bash
# Deploy contract (example)
./deploy_commit_reveal.sh

# Run tests
ergo-cli test coinflip_commit_reveal_tests.rs
```

## Backend API Reference

### Main Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/place-bet` | POST | Place a new coinflip bet |
| `/history/{address}` | GET | Get bet history for address |
| `/player/stats/{address}` | GET | Get player statistics |
| `/player/comp/{address}` | GET | Get player compensation |
| `/leaderboard` | GET | Get global leaderboard |
| `/bets/{bet_id}/timeout` | GET | Get timeout info for bet |
| `/bets/expired` | GET | List all expired bets |
| `/bets/{bet_id}/refund-record` | POST | Record refund after on-chain tx |

### Example: Place Bet

```python
import requests

response = requests.post(
    "http://localhost:8000/place-bet",
    json={
        "player_address": "your_address_here",
        "amount": 1000000,  # 1 ERG in nanoERG
        "choice": 0,  # 0=heads, 1=tails
        "secret": "random_32_byte_secret"
    }
)
```

### RNG Module

The RNG module uses block hashes for fairness:

```python
from rng_module import generate_outcome

# Generate outcome using block hash and player secret
outcome = generate_outcome(block_hash, player_secret)
# outcome: 0=heads, 1=tails
```

## WebSocket Integration

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connected to WebSocket server');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

### Events

- `bet_placed`: New bet placed
- `bet_updated`: Bet status changed
- `game_completed`: Game resolved
- `player_joined`: New player joined
- `player_left`: Player left

## Testing Procedures

### Unit Tests

```bash
# Run backend tests
cd backend
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_game_routes.py
```

### E2E Tests

```bash
# Run frontend E2E tests
cd frontend
npm run test:e2e
```

### Contract Tests

```bash
# Run ErgoScript tests
ergo-cli test coinflip_commit_reveal_tests.rs
```

## Best Practices

### Security Considerations

1. **Never expose secrets**: Player secrets should never be logged or exposed
2. **Validate inputs**: Always validate API inputs
3. **Use secure RNG**: Rely on blockchain block hashes for randomness
4. **Timeout protection**: Implement proper timeout mechanisms
5. **NFT preservation**: Ensure game NFTs are preserved during refunds

### Code Quality

1. **Follow PEP 8**: Python code style guidelines
2. **Type annotations**: Use TypeScript for frontend code
3. **Comprehensive testing**: Write tests for all critical paths
4. **Documentation**: Document complex logic and APIs
5. **Error handling**: Implement proper error handling

### Performance

1. **Database optimization**: Use proper indexes for frequent queries
2. **Rate limiting**: Implement rate limiting for API endpoints
3. **Caching**: Use caching for frequently accessed data
4. **Async operations**: Use async/await for I/O operations

## Deployment

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NODE_URL` | Ergo node endpoint | `http://127.0.0.1:9052` |
| `VITE_NODE_URL` | Node URL for frontend | `http://localhost:9052` |
| `NODE_API_KEY` | API key for node | `hello` |
| `BOT_API_KEY` | API key for bot endpoints | (empty) |

### Production Deployment

```bash
# Build frontend
cd frontend
npm run build

# Run backend with production settings
cd ../backend
python api_server.py --prod
```

### Docker Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Common Issues

1. **Contract compilation fails**: Check contract syntax and register layout
2. **Backend connection errors**: Verify node URL and API key
3. **Frontend wallet connection issues**: Ensure Nautilus extension is installed
4. **Database connection problems**: Check PostgreSQL credentials
5. **RNG fairness concerns**: Verify block hash usage and secret handling

### Debugging Tips

1. **Enable debug logging**: Set `LOG_LEVEL=DEBUG` in environment
2. **Check server logs**: View `backend/server.log`
3. **Test with testnet**: Use testnet for development
4. **Review security audits**: Refer to SECURITY_AUDIT_PREPARATION.md

## Contributing

### Branching Strategy

- `main`: Production-ready code
- `develop`: Development branch
- `feature/<feature-name>`: New feature branches
- `hotfix/<issue-number>`: Critical bug fixes

### Pull Request Process

1. Create feature branch from `develop`
2. Implement changes with tests
3. Submit PR to `develop` branch
4. Address review comments
5. Merge after approval

### Code Review Checklist

- [ ] Tests pass
- [ ] Documentation updated
- [ ] Security considerations addressed
- [ ] Performance impact assessed
- [ ] Backward compatibility maintained

## Support

For questions or issues:
- Check existing documentation
- Search issue tracker
- Contact the development team
- Review SECURITY_AUDIT_PREPARATION.md for security guidelines

## Further Reading

- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture details
- [IMPLEMENTATION_NOTES_MAT268.md](../IMPLEMENTATION_NOTES_MAT268.md) - Implementation notes
- [SECURITY_AUDIT_PREPARATION.md](smart-contracts/SECURITY_AUDIT_PREPARATION.md) - Security audit preparation
- [RATE_LIMITING.md](backend/RATE_LIMITING.md) - Rate limiting configuration

--- 
*This documentation is continuously updated. Check the repository for the latest version.*