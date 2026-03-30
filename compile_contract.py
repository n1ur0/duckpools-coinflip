#!/usr/bin/env python3
"""
Compile coinflip_v2_final.es using the Ergo node's /script/p2sAddress endpoint.
Also generates the /contract-info endpoint data the backend needs.
"""

import json
import sys
import requests

NODE_URL = "http://localhost:9052"
CONTRACT_PATH = "smart-contracts/coinflip_v2_final.es"

def compile_contract():
    # Read contract source
    with open(CONTRACT_PATH, "r") as f:
        source = f.read()
    
    print(f"Read contract source: {len(source)} bytes from {CONTRACT_PATH}")
    
    # Compile via node /script/p2sAddress
    # Ergo 6.0+ requires treeVersion in the request body
    print(f"\nCompiling via {NODE_URL}/script/p2sAddress ...")
    resp = requests.post(
        f"{NODE_URL}/script/p2sAddress",
        json={"source": source, "treeVersion": 1},
        timeout=30
    )
    
    if resp.status_code != 200:
        print(f"ERROR: Node returned {resp.status_code}")
        print(f"Response: {resp.text}")
        return None
    
    data = resp.json()
    print(f"Compilation successful!")
    print(f"  P2S Address: {data.get('address', 'N/A')}")
    
    # Also compile to get ergoTree bytes via /script/compile endpoint
    print(f"\nCompiling via {NODE_URL}/script/compile ...")
    resp2 = requests.post(
        f"{NODE_URL}/script/compile",
        json={"source": source, "treeVersion": 1},
        timeout=30
    )
    
    ergo_tree = ""
    if resp2.status_code == 200:
        compile_data = resp2.json()
        # Try to extract ergoTree
        if "ergoTree" in compile_data:
            ergo_tree = compile_data["ergoTree"]
        elif "compiledTree" in compile_data:
            ergo_tree = compile_data["compiledTree"]
        print(f"  Compile response keys: {list(compile_data.keys())}")
        print(f"  ergoTree length: {len(ergo_tree)} chars")
    else:
        print(f"  Compile endpoint returned {resp2.status_code}: {resp2.text[:200]}")
    
    # Build output
    result = {
        "contract": "coinflip_v2_final",
        "version": "v2-final-r4r9-compatible",
        "address": data.get("address", ""),
        "ergoTree": ergo_tree,
        "sourceFile": CONTRACT_PATH,
        "sourceLength": len(source),
        "compiledAt": __import__('datetime').datetime.utcnow().isoformat() + "Z",
        "nodeVersion": "6.0.3",
        "network": "testnet",
        "registerLayout": {
            "R4": "housePubKey (Coll[Byte]) - house compressed PK (33 bytes)",
            "R5": "playerPubKey (Coll[Byte]) - player compressed PK (33 bytes)",
            "R6": "commitmentHash (Coll[Byte]) - blake2b256(secret||choice) (32 bytes)",
            "R7": "playerChoice (Int) - 0=heads, 1=tails",
            "R8": "timeoutHeight (Int) - timeout block height",
            "R9": "playerSecret (Coll[Byte]) - player secret (8 random bytes)"
        },
        "economics": {
            "houseEdge": 0.03,
            "refundFee": 0.02,
            "timeoutBlocks": 100,
            "revealWindowBlocks": 30
        }
    }
    
    # Save compiled output
    output_path = "smart-contracts/coinflip_v2_final_compiled.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved compiled output to {output_path}")
    
    # Also update the deployed.json
    deployed = {
        "contractName": "coinflip_v2_final",
        "network": "testnet",
        "p2sAddress": data.get("address", ""),
        "ergoTreeHex": ergo_tree,
        "ergoTreeHash": __import__('hashlib').sha256(ergo_tree.encode()).hexdigest() if ergo_tree else "",
        "registerLayout": result["registerLayout"],
        "derivedValues": {
            "rngBlockHeight": "timeoutHeight - 30 (REVEAL_WINDOW constant in contract)",
            "revealWindowBlocks": 30
        },
        "houseEdge": 0.03,
        "refundFee": 0.02,
        "timeoutBlocks": 100,
        "revealWindowBlocks": 30,
        "compiledAt": result["compiledAt"],
        "status": "compiled_and_ready",
        "nodeVersion": "6.0.3",
        "note": "R4-R9 only (R10 not supported in ErgoScript 6.0.3). Reveal window derived from timeoutHeight - 30."
    }
    
    deployed_path = "smart-contracts/coinflip_deployed.json"
    with open(deployed_path, "w") as f:
        json.dump(deployed, f, indent=2)
    print(f"Updated {deployed_path}")
    
    return result


if __name__ == "__main__":
    result = compile_contract()
    if result:
        print(f"\n=== COMPILATION SUCCESS ===")
        print(f"Address: {result['address']}")
        print(f"ErgoTree: {result['ergoTree'][:80]}..." if result['ergoTree'] else "ErgoTree: (empty)")
    else:
        print("\n=== COMPILATION FAILED ===")
        sys.exit(1)
