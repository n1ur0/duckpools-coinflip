#!/usr/bin/env python3
"""Compile coinflip_v2_final.es against the local Ergo node REST API."""
import json, urllib.request, urllib.error, sys, hashlib
from datetime import datetime, timezone

CONTRACT_PATH = "/Users/n1ur0/Documents/git/duckpools-coinflip/smart-contracts/coinflip_v2_final.es"
OUTPUT_PATH = "/Users/n1ur0/Documents/git/duckpools-coinflip/smart-contracts/coinflip_v2_final_compiled.json"
DEPLOYED_PATH = "/Users/n1ur0/Documents/git/duckpools-coinflip/smart-contracts/coinflip_deployed.json"
NODE_URL = "http://127.0.0.1:9052/script/p2sAddress"

with open(CONTRACT_PATH) as f:
    source = f.read()

payload = json.dumps({"source": source, "treeVersion": 1})
print(f"Payload size: {len(payload)} bytes")

req = urllib.request.Request(NODE_URL, data=payload.encode(), headers={"Content-Type": "application/json"})

try:
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read())
    address = result.get("address", "N/A")
    ergo_tree = result.get("ergoTree", "")
    print(f"SUCCESS!")
    print(f"  Address: {address}")
    print(f"  ergoTree length: {len(ergo_tree)} chars")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ergo_tree_hash = hashlib.sha256(ergo_tree.encode()).hexdigest()

    compiled = {
        "contract": "coinflip_v2_final",
        "version": "v2-final-r4r9-compatible",
        "address": address,
        "ergoTree": ergo_tree,
        "ergoTreeHash": ergo_tree_hash,
        "compiledAt": now,
        "network": "testnet",
        "treeVersion": 1,
        "status": "compiled_successfully",
        "nodeVersion": "6.0.3",
        "registerLayout": {
            "R4": "housePubKey (Coll[Byte]) - house compressed PK (33 bytes)",
            "R5": "playerPubKey (Coll[Byte]) - player compressed PK (33 bytes)",
            "R6": "commitmentHash (Coll[Byte]) - blake2b256(secret||choice) (32 bytes)",
            "R7": "playerChoice (Int) - 0=heads, 1=tails",
            "R8": "timeoutHeight (Int) - timeout height for refund (~100 blocks from bet)",
            "R9": "playerSecret (Coll[Byte]) - player secret (8 random bytes)"
        },
        "derivedValues": {
            "rngBlockHeight": "timeoutHeight - 30 (REVEAL_WINDOW constant in contract)",
            "revealWindowBlocks": 30
        },
        "houseEdge": 0.03,
        "refundFee": 0.02,
        "timeoutBlocks": 100,
        "revealWindowBlocks": 30,
        "r10Fix": "R10 not supported in ErgoScript Lithos 6.0.3. Reveal window derived from timeoutHeight - 30 constant."
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(compiled, f, indent=2)
    print(f"  Saved compiled output to {OUTPUT_PATH}")

    # Also update coinflip_deployed.json
    deployed = {
        "contractName": "coinflip_v2_final",
        "network": "testnet",
        "p2sAddress": address,
        "ergoTreeHex": ergo_tree,
        "ergoTreeHash": ergo_tree_hash,
        "registerLayout": compiled["registerLayout"],
        "derivedValues": compiled["derivedValues"],
        "houseEdge": 0.03,
        "refundFee": 0.02,
        "timeoutBlocks": 100,
        "revealWindowBlocks": 30,
        "compiledAt": now,
        "status": "compiled_and_ready",
        "nodeVersion": "6.0.3",
        "note": "R4-R9 only (R10 not supported in ErgoScript 6.0.3). Reveal window derived from timeoutHeight - 30. Core features: commit-reveal RNG, 3% house edge, timeout refund."
    }

    with open(DEPLOYED_PATH, "w") as f:
        json.dump(deployed, f, indent=2)
    print(f"  Updated {DEPLOYED_PATH}")

except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    sys.exit(1)
