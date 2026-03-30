#!/usr/bin/env python3
"""Compile all coinflip contracts against the local Ergo node."""
import json, urllib.request, urllib.error, sys, hashlib
from datetime import datetime, timezone

BASE = "/Users/n1ur0/Documents/git/worktrees/agent/DeFi-Architect-Sr/76e4dc09-commit-reveal-flow/smart-contracts"
NODE_URL = "http://127.0.0.1:9052/script/p2sAddress"

contracts = [
    ("coinflip_v1.es", "coinflip_v1_compiled.json"),
    ("coinflip_v2.es", "coinflip_v2_compiled.json"),
    ("coinflip_v3.es", "coinflip_v3_compiled.json"),
]

for filename, output_name in contracts:
    path = f"{BASE}/{filename}"
    with open(path) as f:
        source = f.read()

    payload = json.dumps({"source": source, "treeVersion": 1})
    req = urllib.request.Request(NODE_URL, data=payload.encode(), headers={"Content-Type": "application/json"})

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        address = result.get("address", "N/A")
        ergo_tree = result.get("ergoTree", "")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ergo_tree_hash = hashlib.sha256(ergo_tree.encode()).hexdigest()

        compiled = {
            "contract": filename.replace('.es', ''),
            "address": address,
            "ergoTree": ergo_tree,
            "ergoTreeHash": ergo_tree_hash,
            "compiledAt": now,
            "network": "testnet",
            "treeVersion": 1,
            "status": "compiled_successfully",
        }

        output_path = f"{BASE}/{output_name}"
        with open(output_path, "w") as f:
            json.dump(compiled, f, indent=2)

        print(f"[OK]   {filename} -> {output_name}")
        print(f"       Address: {address[:40]}...")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[FAIL] {filename}: HTTP {e.code}")
        print(f"       {body[:200]}")
    except Exception as e:
        print(f"[FAIL] {filename}: {e}")
