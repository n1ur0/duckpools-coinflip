#!/bin/bash

# Start all DuckPools services using pm2
# This script ensures proper startup order and waits for health checks

set -e

PROJECT_DIR="/Users/n1ur0/Documents/git/duckpools-coinflip"
cd "$PROJECT_DIR" || exit 1

echo "=========================================="
echo "Starting DuckPools Services"
echo "=========================================="
echo ""

# Check if pm2 is installed
if ! npx pm2 list > /dev/null 2>&1; then
  echo "PM2 not available. Installing locally..."
  npm install pm2 --save-dev
fi

# Start all services
echo "Starting all services with pm2..."
npx pm2 start ecosystem.config.js

echo ""
echo "Waiting for services to be healthy..."

# Wait for node to be ready
MAX_WAIT=120
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
  if curl -s http://localhost:9052/info > /dev/null 2>&1; then
    echo "✓ Ergo node is ready!"
    break
  fi
  echo "Waiting for node... ($WAIT_COUNT/${MAX_WAIT}s)"
  sleep 5
  WAIT_COUNT=$((WAIT_COUNT + 5))
done

# Wait for backend to be ready
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Backend API is ready!"
    break
  fi
  echo "Waiting for backend... ($WAIT_COUNT/${MAX_WAIT}s)"
  sleep 3
  WAIT_COUNT=$((WAIT_COUNT + 3))
done

echo ""
echo "=========================================="
echo "Services started successfully!"
echo "=========================================="
echo ""
echo "View logs: npx pm2 logs"
echo "View status: npx pm2 status"
echo "Stop all: npx pm2 stop all"
echo "Restart all: npx pm2 restart all"
echo ""
echo "Run health check: ./scripts/health-check.sh"
echo ""

# Show status
npx pm2 status
