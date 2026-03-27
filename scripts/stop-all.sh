#!/bin/bash

# Stop all DuckPools services using pm2

set -e

PROJECT_DIR="/Users/n1ur0/Documents/git/duckpools-coinflip"
cd "$PROJECT_DIR" || exit 1

echo "=========================================="
echo "Stopping DuckPools Services"
echo "=========================================="
echo ""

# Stop all services
npx pm2 stop all

# Optionally delete from pm2 list (uncomment to enable)
# npx pm2 delete all

echo ""
echo "All services stopped!"
echo ""
echo "To restart: ./scripts/start-all.sh"
