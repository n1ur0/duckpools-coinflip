#!/usr/bin/env python3
"""Compile coinflip_v1.es against the local Ergo node REST API."""
import json, urllib.request, urllib.error, sys, hashlib
from datetime import datetime, timezone

CONTRACT_PATH = "/Users/n1ur0/Documents/git/worktrees/agent/DeFi-Architect-Sr/76e4dc09-commit-reveal-flow/smart-contracts/coinflip_v1.es"
OUTPUT_PATH = "/Users/n1ur0/Documents/git/worktrees/agent/DeFi-Architect-Sr/76e4dc09-commit-reveal-flow/smart-contracts/coinflip_v1_compiled.json"
NODE_URL = "http://127.0.0.1:9052/script/p2sAddress"

with open(CONTRACT_PATH) as f:
    source = f.read()

payload = json.dumps({"source": source, "treeVersion": 1})
print(f"Source size: {len(source)} chars")
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
        "contract": "coinflip_v1",
        "version": "v1-MAT-393",
        "address": address,
        "ergoTree": ergo_tree,
        "ergoTreeHash": ergo_tree_hash,
        "compiledAt": now,
        "network": "testnet",
        "treeVersion": 1,
        "status": "compiled_successfully",
        "nodeVersion": "ergo-6.0.3",
        "registerLayout": {
            "R4": "housePubKey (Coll[Byte]) - house compressed PK (33 bytes)",
            "R5": "playerPubKey (Coll[Byte]) - player compressed PK (33 bytes)",
            "R6": "commitmentHash (Coll[Byte]) - blake2b256(secret||choice) (32 bytes)",
            "R7": "playerChoice (Int) - 0=heads, 1=tails",
            "R8": "timeoutHeight (Int) - timeout height for refund",
            "R9": "playerSecret (Coll[Byte]) - player secret (8 random bytes)",
            "R10": "rngBlockHeight (Int) - pre-committed reveal height"
        },
        "tokenLayout": {
            "Token0": "Game NFT (amount=1) - preserved in OUTPUTS(1) for both reveal and refund"
        },
        "houseEdge": 0.03,
        "refundFee": 0.02,
        "changes": [
            "REGENERATED from scratch (MAT-393)",
            "Fixed: fromSelf -> SELF",
            "Fixed: sig.verify(pk) -> SigmaProp equality (proveDlog + propBytes)",
            "Fixed: corrupted player...ytes",
            "Added: NFT preservation in both reveal and refund paths",
            "Added: reveal window (R10 rngBlockHeight)",
            "Added: enforced payout amounts (1.94x win, 0.98x refund)"
        ]
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(compiled, f, indent=2)
    print(f"  Saved compiled output to {OUTPUT_PATH}")

except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    sys.exit(1)
