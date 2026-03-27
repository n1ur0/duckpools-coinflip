#!/bin/bash

# Start script for Ergo node
# This script starts the node and waits for it to be healthy

NODE_DIR="/Users/n1ur0/Documents/git/ergo-testnet"
NODE_API="http://localhost:9052"
MAX_WAIT=300  # 5 minutes max wait for startup

cd "$NODE_DIR" || exit 1

# Check if node is already running
if curl -s "$NODE_API/info" > /dev/null 2>&1; then
  echo "Ergo node is already running!"
  # Keep this script running in foreground for PM2
  # Sleep indefinitely to maintain PM2 process
  echo "Monitoring existing node process..."
  # Just sleep - PM2 will restart if this script dies
  sleep infinity
fi

echo "Starting Ergo node..."
java -jar ergo.jar &
NODE_PID=$!

echo "Waiting for node to be ready (PID: $NODE_PID)..."

# Wait for node API to respond
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
  if curl -s "$NODE_API/info" > /dev/null 2>&1; then
    echo "Node is ready!"
    # Keep the script alive and exit on node death
    wait $NODE_PID
    exit $?
  fi

  # Check if process is still running
  if ! kill -0 $NODE_PID 2>/dev/null; then
    echo "Node process died unexpectedly!"
    exit 1
  fi

  sleep 2
  WAIT_COUNT=$((WAIT_COUNT + 2))
done

echo "Timeout waiting for node to be ready!"
exit 1
