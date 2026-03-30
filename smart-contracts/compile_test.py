#!/usr/bin/env python3
"""Compile coinflip_v2_final.es against the local Ergo node REST API."""
import json, urllib.request, urllib.error, sys

CONTRACT_PATH = "/Users/n1ur0/Documents/git/duckpools-coinflip/smart-contracts/coinflip_v2_final.es"
OUTPUT_PATH = "/Users/n1ur0/Documents/git/duckpools-coinflip/smart-contracts/coinflip_v2_final_compiled.json"
NODE_URL = "http://127.0.0.1:9052/script/p2sAddress"

with open(CONTRACT_PATH) as f:
    source = f.read()

payload = json.dumps({"source": source, "treeVersion": 1})
print(f"Payload size: {len(payload)} bytes")

req = urllib.request.Request(NODE_URL, data=payload.encode(), headers={"Content-Type": "application/json"})

try:
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read())
    print(f"Address: {result.get('address', 'N/A')}")
    print(f"ergoTree length: {len(result.get('ergoTree', ''))}")

    compiled = {
        "contract": "coinflip_v2_final",
        "version": "v2-final-with-reveal-window",
        "address": result.get("address"),
        "ergoTree": result.get("ergoTree"),
        "compiledAt": "2026-03-30T18:35:00Z",
        "network": "testnet",
        "treeVersion": 1,
        "status": "compiled_successfully",
        "registerLayout": {
            "R4": "housePubKey (Coll[Byte]) - house compressed PK (33 bytes)",
            "R5": "playerPubKey (Coll[Byte]) - player compressed PK (33 bytes)",
            "R6": "commitmentHash (Coll[Byte]) - blake2b256(secret||choice) (32 bytes)",
            "R7": "playerChoice (Int) - 0=heads, 1=tails",
            "R8": "timeoutHeight (Int) - timeout height for refund (~100 blocks from bet)",
            "R9": "playerSecret (Coll[Byte]) - player secret (8 random bytes)",
            "R10": "rngBlockHeight (Int) - pre-committed reveal height (~70 blocks from bet)"
        },
        "houseEdge": 0.03,
        "refundFee": 0.02,
        "timeoutBlocks": 100,
        "revealWindowBlocks": 30
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(compiled, f, indent=2)
    print(f"Saved to {OUTPUT_PATH}")

except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    sys.exit(1)
