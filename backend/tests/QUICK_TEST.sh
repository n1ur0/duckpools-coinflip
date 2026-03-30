#!/bin/bash
# MAT-410: Quick curl-based bet submission test (no frontend, no Python)
#
# Usage:
#   bash backend/tests/QUICK_TEST.sh              # in-memory bet
#   bash backend/tests/QUICK_TEST.sh --onchain    # on-chain bet (needs synced node)
#
# Generates a random secret + commitment and submits via curl.

set -e

BACKEND="${BACKEND_URL:-http://localhost:8000}"
ONCHAIN="${1:-}"
PLAYER_ADDR="3WwcyQQdaCifkL2oS8aWpMKFCrwRQwgL5U9D8G2TPKdmifa9VPbx"

# Generate 8-byte random secret and commitment using Python
read SECRET COMMITMENT CHOICE <<< $(python3 -c "
import hashlib, os
s = os.urandom(8).hex()
c = 0
h = hashlib.blake2b(bytes.fromhex(s) + bytes([c]), digest_size=32).hexdigest()
print(s, h, c)
")

BET_ID="curl-test-$(date +%s)-$RANDOM"
AMOUNT="10000000"  # 0.01 ERG

echo "=== MAT-410: Quick Bet Submission Test ==="
echo "Backend:  $BACKEND"
echo "Player:   $PLAYER_ADDR"
echo "Amount:   $AMOUNT nanoERG (0.01 ERG)"
echo "Choice:   $CHOICE (heads)"
echo "Secret:   $SECRET"
echo "Commit:   $COMMITMENT"
echo "Bet ID:   $BET_ID"
echo "On-chain: ${ONCHAIN:---off}"
echo ""

if [ "$ONCHAIN" = "--onchain" ]; then
  ONCHAIN_FLAG="true"
else
  ONCHAIN_FLAG="false"
fi

echo "--- Submitting ---"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BACKEND/place-bet" \
  -H "Content-Type: application/json" \
  -d "{
    \"address\": \"$PLAYER_ADDR\",
    \"amount\": \"$AMOUNT\",
    \"choice\": $CHOICE,
    \"commitment\": \"$COMMITMENT\",
    \"betId\": \"$BET_ID\",
    \"secret\": \"$SECRET\",
    \"onchain\": $ONCHAIN_FLAG
  }")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | sed 's/HTTP_CODE://')
BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")

echo "HTTP: $HTTP_CODE"
echo "Response: $BODY" | python3 -m json.tool 2>/dev/null || echo "Response: $BODY"

# Verify response
SUCCESS=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',''))" 2>/dev/null)
if [ "$SUCCESS" = "True" ]; then
  echo ""
  echo "=== RESULT: PASS ==="
else
  echo ""
  echo "=== RESULT: FAIL ==="
  exit 1
fi
