#!/bin/bash

# DuckPools E2E Testing Setup Script
# This script sets up the Playwright E2E testing environment

set -e

echo "🚀 Setting up DuckPools E2E testing environment..."

# Navigate to the E2E tests directory
cd "$(dirname "$0")"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18 or higher."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version 18 or higher is required. Current version: $(node -v)"
    exit 1
fi

echo "✅ Node.js $(node -v) is installed"

# Install npm dependencies
echo "📦 Installing npm dependencies..."
npm install

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
npm run install:browsers

# Check if Playwright is installed correctly
if npx playwright --version &> /dev/null; then
    echo "✅ Playwright $(npx playwright --version) is installed"
else
    echo "❌ Playwright installation failed"
    exit 1
fi

# Create a .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
# DuckPools E2E Testing Environment Variables
# These are used for E2E testing only

# Frontend URL
FRONTEND_URL=http://localhost:3000

# Backend API URL
BACKEND_URL=http://localhost:8000

# Wallet addresses for testing
TEST_WALLET_ADDRESS=3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26

# API keys for testing
API_KEY=***

# Test amounts (in ERG)
MIN_BET_AMOUNT=0.1
MAX_BET_AMOUNT=1000

# Timeouts (in milliseconds)
ELEMENT_TIMEOUT=10000
NAVIGATION_TIMEOUT=30000
TEST_TIMEOUT=60000
EOF
    echo "✅ .env file created"
else
    echo "ℹ️  .env file already exists"
fi

# Create test results directory
mkdir -p test-results
mkdir -m 755 test-results/screenshots
mkdir -m 755 test-results/videos
mkdir -m 755 test-results/traces

echo "✅ Test results directories created"

# Run a quick smoke test to verify setup
echo "🧪 Running smoke test to verify setup..."
npm run test -- --grep "should load the main page successfully" --reporter=list

if [ $? -eq 0 ]; then
    echo "✅ E2E testing environment is ready!"
    echo ""
    echo "📚 Next steps:"
    echo "   - Run all tests: npm test"
    echo "   - Run tests in headed mode: npm run test:headed"
    echo "   - Run tests in debug mode: npm run test:debug"
    echo "   - Run tests with UI mode: npm run test:ui"
    echo "   - View test reports: npm run report:show"
else
    echo "❌ Smoke test failed. Please check the setup."
    exit 1
fi

echo ""
echo "🎯 Happy testing!"