#!/usr/bin/env bash
# DuckPools Frontend Dev Server Start Script
# Works from any directory — uses absolute paths and exec env -C

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-3000}"
DAEMON=false
NO_HOST=false

# Parse flags
for arg in "$@"; do
  case "$arg" in
    --daemon)  DAEMON=true ;;
    --no-host) NO_HOST=true ;;
  esac
done

# Kill any existing process on the port
EXISTING_PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
  echo "Killing existing process on port $PORT (PID: $EXISTING_PID)"
  kill -9 "$EXISTING_PID" 2>/dev/null || true
  sleep 1
fi

# Build the vite command
VITE_CMD="npx vite --port $PORT"
if [ "$NO_HOST" = false ]; then
  VITE_CMD="$VITE_CMD --host"
fi

if [ "$DAEMON" = true ]; then
  LOG_FILE="$PROJECT_DIR/frontend-dev.log"
  echo "Starting frontend in background on port $PORT — logs: $LOG_FILE"
  exec env -C "$PROJECT_DIR" $VITE_CMD > "$LOG_FILE" 2>&1 &
  echo "PID: $!"
else
  echo "Starting frontend on port $PORT (foreground)"
  exec env -C "$PROJECT_DIR" $VITE_CMD
fi
