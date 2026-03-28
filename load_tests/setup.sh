#!/bin/bash

# DuckPools Load Testing Framework - Setup Script

set -e

echo "=========================================="
echo "DuckPools Load Testing Framework Setup"
echo "=========================================="

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check Python version
echo ""
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo "Found Python $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "Error: Python 3.8+ is required"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ Pip upgraded"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Create reports directory
echo ""
echo "Creating reports directory..."
mkdir -p reports
echo "✓ Reports directory created"

# Make run_test.py executable
chmod +x run_test.py
echo "✓ Made run_test.py executable"

echo ""
echo "=========================================="
echo "Setup completed successfully!"
echo "=========================================="
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run a load test:"
echo "  python run_test.py list          # List scenarios"
echo "  python run_test.py smoke         # Run smoke test"
echo "  python run_test.py normal        # Run normal load test"
echo "  python run_test.py stress        # Run stress test"
echo ""
echo "To deactivate the virtual environment:"
echo "  deactivate"
echo ""
