# Docker Setup Guide

This guide explains how to run DuckPools Coinflip using Docker Compose.

## Quick Start

### Using the Management Script (Recommended)

```bash
# 1. Navigate to project root
cd duckpools-coinflip

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your configuration
nano .env

# 4. Start development environment using the management script
./docker-manage.sh dev up

# 5. Access the application
#   Frontend: http://localhost:3000
#   Backend API: http://localhost:8000
#   Health check: curl http://localhost:8000/health
```

### Using Docker Compose Directly

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

### Development Enhancements

The project includes `docker-compose.override.yml` which provides development-specific optimizations:

- **Enhanced Hot-Reload**: Better file watching with optimized volume mounts
- **Debug Support**: Built-in debug ports for VS Code debugging
- **Resource Management**: Memory and CPU limits for development
- **Enhanced Logging**: DEBUG level logging and development-specific configurations
- **Redis Service**: Optional Redis for development caching/session storage
- **Optimized Builds**: `.dockerignore` files for faster builds

### Debug Ports

The development environment includes these debug ports:
- **Backend**: Port 5678 (Python debugpy)
- **Frontend**: Port 9229 (Node.js debugger)
- **Bot**: Port 5679 (Python debugpy)

### Docker Build Optimization

Each service includes a `.dockerignore` file to:
- Exclude unnecessary files from Docker builds
- Reduce image size
- Speed up build times
- Prevent sensitive files from being included in images

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

### Using the Management Script

```bash
# Start development environment
./docker-manage.sh dev up

# Stop development environment
./docker-manage.sh dev down

# View all logs
./docker-manage.sh dev logs

# View specific service logs
./docker-manage.sh dev logs backend

# Rebuild development images
./docker-manage.sh dev build

# Start production environment
./docker-manage.sh prod up

# Stop production environment
./docker-manage.sh prod down

# Clean all Docker resources
./docker-manage.sh clean all

# Check status of all containers
./docker-manage.sh status
```

### Using Docker Compose Directly

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

### Port conflicts

**Symptom**: "Port is already allocated" error when starting services

**Solution**: Check what's using the ports:

```bash
# Check what's using port 3000
lsof -i :3000

# Check what's using port 8000
lsof -i :8000

# Kill the process if needed
kill -9 <PID>
```

### Memory issues

**Symptom**: Containers crash with "out of memory" errors

**Solution**: Increase Docker memory allocation:

1. Open Docker Desktop settings
2. Go to "Resources" > "Advanced"
3. Increase memory allocation (at least 4GB recommended)
4. Click "Apply & Restart"

### Network connectivity issues

**Symptom**: Services cannot communicate with each other

**Solution**: Check network configuration:

```bash
# List networks
docker network ls

# Inspect duckpools network
docker network inspect duckpools-coinflip_duckpools-network

# Test connectivity between containers
docker exec -it duckpools-backend-dev ping duckpools-frontend-dev
```

### Build errors

**Symptom**: Docker build fails with various errors

**Solution**: Try these steps:

```bash
# Clean build cache
docker builder prune

# Remove all unused images
docker image prune

# Try building again
docker compose build
```

### Performance issues in production

**Symptom**: Slow response times in production

**Solution**: Check resource usage and optimize:

```bash
# Monitor container resource usage
docker stats

# Check container logs for errors
docker-compose -f docker-compose.prod.yml logs

# Consider increasing resources or scaling services
docker-compose -f docker-compose.prod.yml up -d --scale backend=3
```

## Development Workflow

1. Make code changes in `backend/`, `frontend/`, or `off-chain-bot/`
2. Changes are automatically reflected (hot-reload)
3. View logs: `docker compose logs -f <service>`
4. To rebuild after major changes: `docker compose build <service>`

## Debugging in Development

### VS Code Debug Configuration

The Docker setup includes debug ports for VS Code debugging:

#### Backend Debugging
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Remote Debug (Backend)",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}/backend",
          "remoteRoot": "/app"
        }
      ]
    }
  ]
}
```

#### Frontend Debugging
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "JavaScript: Remote Debug (Frontend)",
      "type": "node",
      "request": "attach",
      "port": 9229,
      "localRoot": "${workspaceFolder}/frontend",
      "remoteRoot": "/app"
    }
  ]
}
```

### Bot Debugging
Similar to backend debugging, use port 5679 for the off-chain bot.

### Development Tips

1. **Hot-Reload Issues**: If hot-reload isn't working, try:
   ```bash
   docker compose restart <service>
   # Or check if volume mounts are working:
   docker compose config
   ```

2. **Debug Port Conflicts**: Ensure ports 5678, 5679, and 9229 are not in use:
   ```bash
   lsof -i :5678
   lsof -i :5679
   lsof -i :9229
   ```

3. **Development Performance**: The `docker-compose.override.yml` includes resource limits to prevent your development machine from becoming unresponsive.

4. **Redis for Development**: A Redis container is included for development caching. You can access it at `redis://localhost:6379`.

## Production Deployment

### Using the Management Script (Recommended)

```bash
# 1. Create production environment file
cp .env.example .env.prod

# 2. Edit .env.prod with production settings
nano .env.prod

# 3. Build and start production environment
./docker-manage.sh prod up

# 4. View production logs
./docker-manage.sh prod logs
```

### Using Docker Compose Directly

The project includes a separate `docker-compose.prod.yml` file for production deployment:

```bash
# 1. Create production environment file
cp .env.example .env.prod

# 2. Edit .env.prod with production settings
nano .env.prod

# 3. Build production images
docker-compose -f docker-compose.prod.yml build

# 4. Start production services
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 5. View production logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Production Environment Differences

Production mode:
- **Backend**: Runs with multiple workers, INFO log level, no hot-reload
- **Frontend**: Served by nginx with optimized static files, no hot-reload
- **Off-chain Bot**: Runs with INFO log level, no hot-reload
- **Security**: All services run as non-root users
- **Performance**: Optimized builds with smaller image sizes
- **Reliability**: Automatic restart on failure, longer health check intervals

### Production Requirements

1. **Domain Name**: You'll need a domain name for your production deployment
2. **SSL Certificate**: Recommended for HTTPS (can be obtained via Let's Encrypt)
3. **Reverse Proxy**: Consider using nginx or Apache as a reverse proxy
4. **Database**: Production database (PostgreSQL recommended)
5. **Ergo Node**: Production Ergo node (not testnet)

### Environment Variables for Production

```bash
# Required production variables in .env.prod
NODE_ENV=production
LOG_LEVEL=INFO
FRONTEND_URL=https://your-domain.com
VITE_API_ENDPOINT=https://your-domain.com/api
VITE_ERGO_NODE_URL=https://your-ergo-node.com
ERGO_API_KEY=your-production-api-key
HOUSE_ADDRESS=your-production-house-address
WALLET_PASS=your-production-wallet-password
COINFLIP_NFT_ID=your-production-nft-id
```

### Scaling Services

To scale services for production:

```bash
# Scale backend to 3 instances
docker-compose -f docker-compose.prod.yml up -d --scale backend=3

# Scale backend with restart
docker-compose -f docker-compose.prod.yml up -d --force-recreate --scale backend=3
```
