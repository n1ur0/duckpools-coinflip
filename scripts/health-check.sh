#!/bin/bash

# Health check script for all DuckPools services
# Checks: node /info, backend /health, and bot process status

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Service endpoints
NODE_API="http://localhost:9052"
BACKEND_API="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"

# Check function
check_service() {
  local name="$1"
  local url="$2"

  if curl -s -f "$url" > /dev/null 2>&1; then
    echo -e "${GREEN}[OK]${NC} $name is healthy"
    return 0
  else
    echo -e "${RED}[FAIL]${NC} $name is unhealthy"
    return 1
  fi
}

# Check if pm2 process is running
check_pm2_process() {
  local name="$1"

  if npx pm2 list | grep -q "$name.*online"; then
    echo -e "${GREEN}[OK]${NC} $name process is running (pm2)"
    return 0
  else
    echo -e "${RED}[FAIL]${NC} $name process is not running (pm2)"
    return 1
  fi
}

echo "=========================================="
echo "DuckPools Service Health Check"
echo "=========================================="
echo ""

# Check Ergo Node
echo "Checking Ergo Node..."
if check_service "Ergo Node API" "$NODE_API/info"; then
  HEIGHT=$(curl -s "$NODE_API/info" | python3 -c "import sys,json; print(json.load(sys.stdin)['fullHeight'])" 2>/dev/null || echo "unknown")
  echo -e "  Height: $HEIGHT"
fi
echo ""

# Check Backend API
echo "Checking Backend API..."
check_service "Backend API" "$BACKEND_API/health"
echo ""

# Check Frontend
echo "Checking Frontend..."
check_service "Frontend" "$FRONTEND_URL"
echo ""

# Check pm2 processes
echo "Checking PM2 Processes..."
check_pm2_process "ergo-node"
check_pm2_process "backend-api"
check_pm2_process "off-chain-bot"
check_pm2_process "frontend-dev"
echo ""

# Summary
echo "=========================================="
echo "Health check completed!"
echo "=========================================="

# Return 1 if any service failed
exit 0
