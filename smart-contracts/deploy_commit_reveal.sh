#!/bin/bash

# Deploy Commit-Reveal Contract to Ergo Devnet
# Usage: ./deploy_commit_reveal.sh

set -e

# Configuration
NETWORK="devnet"
CONTRACT_FILE="coinflip_commit_reveal.es"
CONTRACT_NAME="coinflip_commit_reveal"
DEPLOYMENT_SCRIPT="../deploy_contract.py"

# Check if contract file exists
if [ ! -f "$CONTRACT_FILE" ]; then
    echo "Error: Contract file $CONTRACT_FILE not found"
    exit 1
fi

# Check if deployment script exists
if [ ! -f "$DEPLOYMENT_SCRIPT" ]; then
    echo "Error: Deployment script $DEPLOYMENT_SCRIPT not found"
    exit 1
fi

echo "Deploying $CONTRACT_NAME contract to $NETWORK..."
echo "Contract file: $CONTRACT_FILE"

# Deploy the contract
python3 $DEPLOYMENT_SCRIPT \
    --network $NETWORK \
    --contract $CONTRACT_FILE \
    --name $CONTRACT_NAME \
    --confirmations 10

echo "Deployment completed successfully!"

# Display contract information
echo ""
echo "Contract deployed to:"
echo "  Network: $NETWORK"
echo "  Contract: $CONTRACT_NAME"
echo "  File: $CONTRACT_FILE"

# Verify deployment
echo ""
echo "Verifying contract on explorer..."
echo "https://devnet.ergoexplorer.com/address/$(python3 $DEPLOYMENT_SCRIPT --network $NETWORK --contract $CONTRACT_FILE --get-address)"