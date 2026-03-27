# DuckPools Process Supervision (PM2)

This directory contains PM2 configuration for managing all DuckPools services with automatic startup, health monitoring, and log rotation.

## Services

| Service | Command | Port | Description |
|---------|---------|------|-------------|
| ergo-node | java -jar ergo.jar | 9052 | Ergo blockchain node |
| backend-api | python api_server.py | 8000 | FastAPI backend |
| off-chain-bot | python main.py | - | Bet resolution bot |
| frontend-dev | npm run dev | 3000 | Vite dev server |

## Quick Start

```bash
# Start all services
./scripts/start-all.sh

# Stop all services
./scripts/stop-all.sh

# Check health of all services
./scripts/health-check.sh
```

## Startup Order

PM2 manages dependencies automatically:
1. **ergo-node** starts first (waits for /info response)
2. **backend-api** starts after node is ready (waits for /health)
3. **off-chain-bot** starts after backend is ready
4. **frontend-dev** starts after backend is ready

## PM2 Commands

```bash
# List all processes
npx pm2 status

# View logs for all services
npx pm2 logs

# View logs for specific service
npx pm2 logs ergo-node
npx pm2 logs backend-api
npx pm2 logs off-chain-bot
npx pm2 logs frontend-dev

# Restart a specific service
npx pm2 restart ergo-node
npx pm2 restart backend-api

# Restart all services
npx pm2 restart all

# Stop all services
npx pm2 stop all

# Delete all services from PM2 list
npx pm2 delete all
```

## Log Rotation

Logs are automatically rotated using pm2-logrotate:
- **Max file size**: 10MB per log file
- **Retention**: 5 days (compressed)
- **Total max size**: ~80-100MB (8 files × 10MB max)
- **Location**: `./logs/`

Log files:
- `ergo-node-error.log` / `ergo-node-out.log`
- `backend-api-error.log` / `backend-api-out.log`
- `off-chain-bot-error.log` / `off-chain-bot-out.log`
- `frontend-dev-error.log` / `frontend-dev-out.log`

## Auto-Restart Behavior

- **Restart on crash**: Yes (autorestart: true)
- **Restart delay**: 5-10 seconds
- **Exponential backoff**: Yes (starts at 100ms, doubles on each crash)
- **Max restarts**: 10 before giving up (pm2 will stop trying)
- **Max memory**: Services restart if exceeding memory limits:
  - ergo-node: 4GB
  - backend-api: 1GB
  - off-chain-bot: 500MB
  - frontend-dev: 2GB

## Health Check Script

The `scripts/health-check.sh` script verifies:
- Ergo Node API responds on `http://localhost:9052/info`
- Backend API responds on `http://localhost:8000/health`
- Frontend responds on `http://localhost:3000`
- PM2 processes are online

Example output:
```
==========================================
DuckPools Service Health Check
==========================================

Checking Ergo Node...
[OK] Ergo Node API is healthy
  Height: 123456

Checking Backend API...
[OK] Backend API is healthy

Checking Frontend...
[OK] Frontend is healthy

Checking PM2 Processes...
[OK] ergo-node process is running (pm2)
[OK] backend-api process is running (pm2)
[OK] off-chain-bot process is running (pm2)
[OK] frontend-dev process is running (pm2)
```

## Troubleshooting

### Service not starting

1. Check logs: `npx pm2 logs <service-name>`
2. Check if port is already in use: `lsof -i :8000` (or other port)
3. Verify environment variables in `.env` files

### High memory usage

If a service hits max_memory_restart, PM2 will automatically restart it. Check logs to identify memory leaks.

### Logs filling disk

Logs are automatically rotated and compressed after 10MB. If disk space is low:
```bash
# Manually clean old logs
rm -f ./logs/*.gz
rm -f ./logs/*-timestamp*.log
```

## System Startup

To start services automatically on system boot (macOS):

```bash
# Generate launchd plist
npx pm2 startup

# Save current processes
npx pm2 save
```

Note: This requires `sudo` access on first run.

## Dependencies

- PM2: `npm install --save-dev pm2`
- pm2-logrotate: Automatically installed and configured

## Files

- `ecosystem.config.js` - PM2 process configuration
- `scripts/start-node.sh` - Wrapper script for Ergo node startup
- `scripts/start-all.sh` - One-command start for all services
- `scripts/stop-all.sh` - One-command stop for all services
- `scripts/health-check.sh` - Health check script
- `logs/` - Log output directory (gitignored)
