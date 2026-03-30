#!/usr/bin/env python3
"""Compile ErgoScript contract via local Ergo node API."""
import json
import sys
import requests

NODE_URL = "http://localhost:9052"

def compile_contract(source_path: str):
    with open(source_path, "r") as f:
        source = f.read()
    
    payload = {"source": source, "treeVersion": 1}
    resp = requests.post(f"{NODE_URL}/script/p2sAddress", json=payload, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        return {"status": "compiled", "address": data, "source": source_path}
    else:
        return {"status": "error", "code": resp.status_code, "detail": resp.text}

def compile_ergotree(source_path: str):
    with open(source_path, "r") as f:
        source = f.read()
    
    payload = {"source": source}
    resp = requests.post(f"{NODE_URL}/script/compile", json=payload, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        return {"status": "compiled", "ergoTree": data, "source": source_path}
    else:
        return {"status": "error", "code": resp.status_code, "detail": resp.text}

if __name__ == "__main__":
    contracts = [
        "smart-contracts/coinflip_v2_final.es",
        "smart-contracts/coinflip_v3.es",
        "smart-contracts/coinflip_commit_reveal.es",
    ]
    
    for c in contracts:
        print(f"\n=== Compiling {c} ===")
        result = compile_contract(c)
        if result["status"] == "compiled":
            print(f"  P2S Address: {result['address']}")
        else:
            print(f"  ERROR: {result}")
        
        result2 = compile_ergotree(c)
        if result2["status"] == "compiled":
            print(f"  ErgoTree: {result2['ergoTree'][:100]}...")
        else:
            print(f"  ErgoTree ERROR: {result2}")
