# Docker Setup Guide

This guide explains how to run DuckPools Coinflip using Docker Compose.

## Quick Start

```bash
# 1. Navigate to project root
cd duckpools-coinflip

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your configuration
nano .env

# 4. Build and start all services
docker compose build
docker compose up -d

# 5. Access the application
#   Frontend: http://localhost:3000
#   Backend API: http://localhost:8000
#   Health check: curl http://localhost:8000/health
```

## Prerequisites

1. **Docker & Docker Compose**: Install from [docker.com](https://www.docker.com/get-started)
2. **Ergo Testnet Node**: Running natively on host port 9052
3. **Testnet ERG**: For initial liquidity and testing
4. **Nautilus Wallet**: For testing on testnet

## Architecture

The Docker Compose setup includes:

- **backend-api**: FastAPI backend with hot-reload
- **frontend**: React Vite dev server with hot-reload
- **off-chain-bot**: Bot for bet resolution (no port exposure)

**Important**: The Ergo node runs natively on the host machine, not in a container. Services communicate with it via `host.docker.internal`.

## Services

| Service | Port | Description |
|---------|------|-------------|
| backend-api | 8000 | FastAPI backend with hot-reload |
| frontend | 3000 | React Vite dev server |
| off-chain-bot | - | Bot for bet resolution (no port exposure) |

## Accessing Services

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/health

## Environment Configuration

Required environment variables in `.env`:

```bash
# Node configuration (host.docker.internal for Docker containers)
NODE_URL=http://host.docker.internal:9052

# Wallet configuration
HOUSE_ADDRESS=your_testnet_address
WALLET_PASS=your_wallet_password

# Game assets
COINFLIP_NFT_ID=your_deployed_nft_id

# API key (matches ergo.conf apiKeyHash)
API_KEY=hello
```

See `.env.example` for all available configuration options.

## Common Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v

# View logs
docker compose logs -f

# View logs for a specific service
docker compose logs -f backend-api

# Rebuild a service
docker compose build backend-api
docker compose up -d backend-api

# Check service status
docker compose ps
```

## Troubleshooting

### Container cannot reach Ergo node

**Symptom**: Backend API returns connection errors to Ergo node

**Solution**: Ensure Ergo node is running on host:9052 before starting services:

```bash
# Check Ergo node is running
curl http://localhost:9052/info
```

### Frontend cannot connect to backend

**Symptom**: Frontend shows API connection errors

**Solution**: Check `VITE_API_ENDPOINT` in `.env` (should be `http://localhost:8000`)

### Bot cannot sign transactions

**Symptom**: Bot logs show wallet unlock failures

**Solution**: Verify `WALLET_PASS` is correct in `.env`

### Services crash immediately

**Symptom**: Services exit with error code

**Solution**: Check logs:

```bash
docker compose logs backend-api
docker compose logs frontend
docker compose logs off-chain-bot
```

### Hot-reload not working

**Symptom**: Code changes not reflected in containers

**Solution**: Ensure volume mounts are working:

```bash
# Check volumes
docker compose config

# Restart service
docker compose restart backend-api
```

## Development Workflow

1. Make code changes in `backend/`, `frontend/`, or `off-chain-bot/`
2. Changes are automatically reflected (hot-reload)
3. View logs: `docker compose logs -f <service>`
4. To rebuild after major changes: `docker compose build <service>`

## Production Deployment

The Dockerfiles include a `production` target for optimized builds:

```bash
# Build production images
docker compose build --target production

# Start production services
docker compose up -d
```

Production mode:
- Runs with multiple workers (backend)
- Uses optimized static files (frontend)
- Runs as non-root user (security)
