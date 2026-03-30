#!/usr/bin/env python3
"""
Unified contract compiler for DuckPools coinflip.

Compiles all Phase 2 contracts against the local Ergo node REST API.
Generates P2S addresses and saves compiled artifacts.

Usage:
    python3 scripts/compile_all_contracts.py
    python3 scripts/compile_all_contracts.py --node http://127.0.0.1:19052

Contracts compiled:
    - coinflip_v2_final.es  (canonical, with reveal window)
    - coinflip_commit_reveal.es (simplified, no reveal window)

Excluded:
    - coinflip_v1.es (legacy, incompatible with Ergo 6.0.x)
"""

import json
import sys
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Configuration
DEFAULT_NODE_URL = "http://127.0.0.1:19052"
BASE_DIR = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = BASE_DIR / "smart-contracts"
TREE_VERSION = 1

CONTRACTS = {
    "coinflip_v2_final": {
        "source": CONTRACTS_DIR / "coinflip_v2_final.es",
        "output": CONTRACTS_DIR / "coinflip_v2_final_compiled.json",
        "deployed": CONTRACTS_DIR / "coinflip_deployed.json",
        "description": "Canonical contract with reveal window (R4-R9)",
        "register_layout": {
            "R4": "housePubKey (Coll[Byte]) - house compressed PK (33 bytes)",
            "R5": "playerPubKey (Coll[Byte]) - player compressed PK (33 bytes)",
            "R6": "commitmentHash (Coll[Byte]) - blake2b256(secret||choice) (32 bytes)",
            "R7": "playerChoice (Int) - 0=heads, 1=tails",
            "R8": "timeoutHeight (Int) - timeout block height for refund",
            "R9": "playerSecret (Coll[Byte]) - player secret (8 random bytes)",
        },
        "economics": {
            "houseEdge": 0.03,
            "refundFee": 0.02,
            "timeoutBlocks": 100,
            "revealWindowBlocks": 30,
        },
    },
    "coinflip_commit_reveal": {
        "source": CONTRACTS_DIR / "coinflip_commit_reveal.es",
        "output": CONTRACTS_DIR / "coinflip_commit_reveal_compiled.json",
        "deployed": None,
        "description": "Simplified commit-reveal (no reveal window)",
        "register_layout": {
            "R4": "housePubKey (Coll[Byte]) - house compressed PK (33 bytes)",
            "R5": "playerPubKey (Coll[Byte]) - player compressed PK (33 bytes)",
            "R6": "commitmentHash (Coll[Byte]) - blake2b256(secret||choice) (32 bytes)",
            "R7": "playerChoice (Int) - 0=heads, 1=tails",
            "R8": "timeoutHeight (Int) - timeout block height for refund",
            "R9": "playerSecret (Coll[Byte]) - player secret (32 bytes)",
        },
        "economics": {
            "houseEdge": 0.03,
            "refundFee": 0.02,
        },
    },
}


def compile_contract(source_path: Path, node_url: str) -> dict:
    """Compile a contract via the Ergo node /script/p2sAddress endpoint."""
    with open(source_path) as f:
        source = f.read()

    payload = json.dumps({"source": source, "treeVersion": TREE_VERSION}).encode()
    req = urllib.request.Request(
        f"{node_url}/script/p2sAddress",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return {
            "status": "compiled",
            "address": data.get("address", ""),
            "ergoTree": data.get("ergoTree", ""),
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"status": "compile_error", "http_code": e.code, "error": body}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def save_compiled_artifact(contract_name: str, result: dict, config: dict):
    """Save compilation result to JSON artifact file."""
    if result["status"] != "compiled":
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ergo_tree = result.get("ergoTree", "")
    ergo_tree_hash = hashlib.sha256(ergo_tree.encode()).hexdigest() if ergo_tree else ""

    artifact = {
        "contract": contract_name,
        "address": result["address"],
        "ergoTree": ergo_tree,
        "ergoTreeHash": ergo_tree_hash,
        "compiledAt": now,
        "nodeVersion": "6.0.3",
        "network": "testnet",
        "treeVersion": TREE_VERSION,
        "status": "compiled_successfully",
        "description": config.get("description", ""),
        "registerLayout": config.get("register_layout", {}),
        "economics": config.get("economics", {}),
    }

    output_path = config["output"]
    with open(output_path, "w") as f:
        json.dump(artifact, f, indent=2)

    print(f"  Saved: {output_path}")

    # Also update deployed.json for the canonical contract
    if config.get("deployed"):
        deployed = {
            "contractName": contract_name,
            "network": "testnet",
            "p2sAddress": result["address"],
            "ergoTreeHex": ergo_tree,
            "ergoTreeHash": ergo_tree_hash,
            "registerLayout": config.get("register_layout", {}),
            "houseEdge": config.get("economics", {}).get("houseEdge", 0.03),
            "refundFee": config.get("economics", {}).get("refundFee", 0.02),
            "timeoutBlocks": config.get("economics", {}).get("timeoutBlocks", 100),
            "revealWindowBlocks": config.get("economics", {}).get("revealWindowBlocks", 30),
            "compiledAt": now,
            "status": "compiled_and_ready",
            "nodeVersion": "6.0.3",
        }
        with open(config["deployed"], "w") as f:
            json.dump(deployed, f, indent=2)
        print(f"  Updated: {config['deployed']}")


def main():
    node_url = DEFAULT_NODE_URL
    for arg in sys.argv[1:]:
        if arg == "--node" and len(sys.argv) > sys.argv.index(arg) + 1:
            node_url = sys.argv[sys.argv.index(arg) + 1]

    # Check node connectivity
    try:
        urllib.request.urlopen(f"{node_url}/info", timeout=5)
    except Exception:
        print(f"ERROR: Cannot reach Ergo node at {node_url}")
        sys.exit(1)

    print(f"DuckPools Contract Compiler")
    print(f"Node: {node_url}")
    print(f"Base: {BASE_DIR}")
    print()

    results = {}
    for name, config in CONTRACTS.items():
        print(f"{'='*60}")
        print(f"Contract: {name}")
        print(f"  File: {config['source'].name}")
        print(f"  Desc: {config.get('description', '')}")

        if not config["source"].exists():
            print(f"  ERROR: Source file not found")
            results[name] = {"status": "missing"}
            continue

        result = compile_contract(config["source"], node_url)
        results[name] = result

        if result["status"] == "compiled":
            print(f"  COMPILED OK")
            print(f"  Address: {result['address'][:60]}...")
            print(f"  ergoTree: {len(result.get('ergoTree', ''))} chars")
            save_compiled_artifact(name, result, config)
        else:
            print(f"  FAILED: {result.get('error', '')[:200]}")

    print(f"\n{'='*60}")
    print("SUMMARY")
    all_ok = True
    for name, r in results.items():
        status = r["status"]
        ok = status == "compiled"
        print(f"  {name}: {'PASS' if ok else 'FAIL'} ({status})")
        if not ok:
            all_ok = False

    if all_ok:
        print("\nAll contracts compiled successfully.")
    else:
        print("\nSome contracts failed to compile.")
        sys.exit(1)


if __name__ == "__main__":
    main()
