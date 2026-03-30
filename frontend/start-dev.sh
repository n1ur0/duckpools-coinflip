#!/usr/bin/env bash
# Permanent start script for frontend dev server on port 3000
# Used by Paperclip workspace setupCommand and for manual starts
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[frontend] Starting dev server on port 3000..."
cd "$SCRIPT_DIR"
exec npx vite --port 3000 --host 0.0.0.0
