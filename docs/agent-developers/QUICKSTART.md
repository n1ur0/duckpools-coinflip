# DuckPools CoinFlip - Quick Start Guide

This guide helps you get started with the DuckPools CoinFlip system quickly.

## Prerequisites

- Python 3.8+
- Node.js 16+
- Docker and Docker Compose
- Git
- Nautilus wallet extension

## Option 1: Quick Start with Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/duckpools/duckpools-coinflip.git
cd duckpools-coinflip

# Start all services
docker-compose up -d

# Wait for services to start (about 30 seconds)
sleep 30

# Access the application
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - Ergo Node: http://localhost:9052
# - Database: localhost:5432
```

## Option 2: Local Development Setup

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Start backend server
python api_server.py
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Node Setup (Optional)

```bash
# Start Ergo node
docker run -d -p 9052:9052 --name ergo-node ergoplatform/ergo:5.0.11
```

## First Test: Place a Bet

### Using Frontend

1. Open browser to http://localhost:3000
2. Connect Nautilus wallet
3. Enter bet amount and choose heads/tails
4. Generate secret and place bet

### Using API (Python)

```python
import requests

# Place a bet
response = requests.post(
    "http://localhost:8000/place-bet",
    json={
        "player_address": "your_address_here",
        "amount": 1000000,  # 1 ERG in nanoERG
        "choice": 0,  # 0=heads, 1=tails
        "secret": "random_32_byte_secret"
    }
)

print(response.json())
```

## Verify Bet Status

```python
# Check bet history
response = requests.get("http://localhost:8000/history/your_address_here")
print(response.json())

# Check specific bet
bet_id = "your_bet_id"
response = requests.get(f"http://localhost:8000/bets/{bet_id}/timeout")
print(response.json())
```

## Stop Services

```bash
# Stop Docker services
docker-compose down

# Stop local development servers
# - Press Ctrl+C in each terminal
```

## Next Steps

- Read the [Agent Development Guide](AGENT_DEVELOPMENT_GUIDE.md) for detailed instructions
- Explore the [API Reference](API_REFERENCE.md) for all available endpoints
- Check the [Smart Contract Guide](SMART_CONTRACT_DEVELOPMENT.md) for contract development
- Review the [Testing Guide](TESTING_GUIDE.md) for testing procedures

--- 
*For production deployment, refer to the [Deployment Guide](DEPLOYMENT_GUIDE.md).*