#!/bin/bash

# Test script to verify PM2 ecosystem configuration

set -e

PROJECT_DIR="/Users/n1ur0/Documents/git/duckpools-coinflip"
cd "$PROJECT_DIR" || exit 1

echo "=========================================="
echo "Testing PM2 Configuration"
echo "=========================================="
echo ""

# Check if ecosystem.config.js exists
if [ ! -f "ecosystem.config.js" ]; then
  echo "[FAIL] ecosystem.config.js not found"
  exit 1
fi
echo "[OK] ecosystem.config.js exists"

# Validate config by loading it with Node.js
echo ""
echo "Validating ecosystem config..."
if node -e "require('./ecosystem.config.js')" 2>/dev/null; then
  echo "[OK] ecosystem.config.js is valid JavaScript"
else
  echo "[FAIL] ecosystem.config.js is invalid"
  exit 1
fi

# Check if all scripts exist
echo ""
echo "Checking script files..."
SCRIPTS=(
  "scripts/start-node.sh"
  "scripts/start-all.sh"
  "scripts/stop-all.sh"
  "scripts/health-check.sh"
)

for script in "${SCRIPTS[@]}"; do
  if [ -f "$script" ]; then
    echo "[OK] $script exists"
    chmod +x "$script"
  else
    echo "[FAIL] $script not found"
    exit 1
  fi
done

# Check if logs directory exists
echo ""
echo "Checking logs directory..."
if [ -d "logs" ]; then
  echo "[OK] logs directory exists"
else
  echo "[FAIL] logs directory not found"
  exit 1
fi

# Check pm2-logrotate module
echo ""
echo "Checking pm2-logrotate module..."
if npx pm2 list | grep -q "pm2-logrotate.*online"; then
  echo "[OK] pm2-logrotate is installed and running"
else
  echo "[WARN] pm2-logrotate may not be installed"
fi

# Display logrotate config
echo ""
echo "Log rotation configuration:"
npx pm2 conf pm2-logrotate | grep -E "max_size|retain|compress"

echo ""
echo "=========================================="
echo "All checks passed! Configuration is ready."
echo "=========================================="
echo ""
echo "To start services: ./scripts/start-all.sh"
echo "To stop services: ./scripts/stop-all.sh"
echo "To check health: ./scripts/health-check.sh"
