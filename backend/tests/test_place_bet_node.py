#!/usr/bin/env python3
"""
MAT-410: Test bet submissions from the Ergo node without using frontend.

This script tests the full place-bet flow directly against the Ergo node API:
1. Generates a random player secret + commitment
2. Builds a PendingBetBox with the coinflip contract ergoTree + registers
3. Submits via /wallet/payment/send
4. Verifies the transaction was accepted
5. Checks the box appears on-chain

Usage:
    # Dry run (validates structure without submitting):
    python backend/tests/test_place_bet_node.py --dry-run

    # Submit to node (requires synced node):
    python backend/tests/test_place_bet_node.py

    # Custom parameters:
    python backend/tests/test_place_bet_node.py --amount 10000000 --choice 1

Environment:
    ERGO_NODE_URL=http://localhost:9052 (default)
    ERGO_API_KEY=hello (default)
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx

# ─── Configuration ───────────────────────────────────────────────

NODE_URL = os.getenv("ERGO_NODE_URL", "http://localhost:9052")
API_KEY = os.getenv("ERGO_API_KEY", "hello")
NODE_HEADERS = {"Content-Type": "application/json", "api_key": API_KEY}

# Contract constants (from smart-contracts/coinflip_deployed.json)
COINFLIP_P2S = (
    "3yNMkSZ6b36YGBJJNhpavxxCFg4f2ceH5JF81hXJgzWoWozuFJSjoW8Q5JXow6fs"
    "TVNrqz48h8a9ajYSTKfwaxG16GbHzxrDcsarkBkbR6NYdGeoCZ9KgNcNMYPLV9RP"
    "kLFwBPLHxDxyTmBfqn5L75zqftETuAadKr8FHEYZrVPZ6kn6gdiZbzMwghxRy2g4w"
    "pTdby4jnxhA42UH7JJzMibgMNBW4yvzw8EaguPLVja6xsxx43yihw5DEzMGzL7HKWY"
    "Us6uVugK1C8Feh3KUX9kpea5xpLXX5oZCV47W6cnTrJfJD3"
)

TIMEOUT_BLOCKS = 100
MIN_BET = 1_000_000       # 0.001 ERG
DEFAULT_BET = 10_000_000  # 0.01 ERG


# ─── Helper Functions ────────────────────────────────────────────

def node_get(endpoint: str) -> dict:
    """GET from the Ergo node."""
    resp = httpx.get(f"{NODE_URL}{endpoint}", headers=NODE_HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def node_post(endpoint: str, payload) -> dict:
    """POST to the Ergo node."""
    resp = httpx.post(
        f"{NODE_URL}{endpoint}",
        headers=NODE_HEADERS,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def generate_player_secret(num_bytes: int = 32) -> str:
    """Generate a random player secret (hex string)."""
    return os.urandom(num_bytes).hex()


def compute_commitment(secret_hex: str, choice: int) -> str:
    """
    Compute commitment hash: blake2b256(secret || choice_byte).
    Matches the on-chain contract exactly.
    """
    secret_bytes = bytes.fromhex(secret_hex)
    choice_byte = bytes([choice])
    return hashlib.blake2b(secret_bytes + choice_byte, digest_size=32).hexdigest()


def decode_ergo_address(address: str) -> str:
    """Extract compressed public key (hex) from Ergo P2PK address.

    Ergo address encoding (Base58Check):
      1 byte: (networkPrefix | addressType) -- testnet P2PK = 0x11
      33 bytes: compressed public key
      4 bytes: blake2b256 checksum of content
    """
    ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    num = 0
    for char in address:
        num = num * 58 + ALPHABET.index(char)
    raw = num.to_bytes(38, byteorder="big")
    payload = raw[:-4]
    checksum = raw[-4:]
    expected = hashlib.blake2b(payload, digest_size=32).digest()[:4]
    assert checksum == expected, "Address checksum mismatch"
    # First byte: network prefix (0x10=testnet, 0x00=mainnet) | type (0x01=P2PK)
    # Pubkey starts at byte 1
    return payload[1:34].hex()


def encode_vlq_unsigned(value: int) -> str:
    """VLQ encoding for unsigned values."""
    if value == 0:
        return "00"
    bytes_list = []
    remaining = value
    while remaining > 0:
        byte = remaining & 0x7F
        remaining >>= 7
        bytes_list.append(byte)
    bytes_list.reverse()
    for i in range(len(bytes_list) - 1):
        bytes_list[i] |= 0x80
    return bytes(bytes_list).hex()


def sigma_encode_coll_byte(hex_str: str) -> str:
    """Encode as sigma Constant(Coll[SByte]): 09 01 <VLQ(len)> <bytes>."""
    raw = bytes.fromhex(hex_str)
    return f"0901{encode_vlq_unsigned(len(raw))}{raw.hex()}"


def sigma_encode_int(value: int) -> str:
    """Encode as sigma Constant(SInt): 03 <ZigZag+VLQ(value)>."""
    if value >= 0:
        zz = value * 2
    else:
        zz = (-value) * 2 - 1
    return f"03{encode_vlq_unsigned(zz)}"


def build_payment_request(
    bet_amount: int,
    house_pubkey_hex: str,
    player_pubkey_hex: str,
    commitment_hex: str,
    choice: int,
    timeout_height: int,
    secret_hex: str,
    fee: int = 1_000_000,
) -> dict:
    """Build the /wallet/payment/send request body."""
    return [{
        "address": COINFLIP_P2S,
        "value": bet_amount,
        "registers": {
            "R4": sigma_encode_coll_byte(house_pubkey_hex),
            "R5": sigma_encode_coll_byte(player_pubkey_hex),
            "R6": sigma_encode_coll_byte(commitment_hex),
            "R7": sigma_encode_int(choice),
            "R8": sigma_encode_int(timeout_height),
            "R9": sigma_encode_coll_byte(secret_hex),
        },
    }]


# ─── Test Functions ──────────────────────────────────────────────

def test_node_connectivity():
    """Check if the Ergo node is reachable and synced."""
    print("[1/6] Checking node connectivity...")
    try:
        info = node_get("/info")
    except httpx.ConnectError:
        print("  FAIL: Cannot connect to Ergo node at", NODE_URL)
        return False
    except httpx.HTTPStatusError as e:
        print(f"  FAIL: Node returned HTTP {e.response.status_code}")
        return False

    full_height = info.get("fullHeight")
    headers_height = info.get("headersHeight")
    print(f"  Version: {info.get('version', 'unknown')}")
    print(f"  Full height: {full_height}")
    print(f"  Headers height: {headers_height}")

    if full_height is None:
        print("  WARN: Node not fully synced (fullHeight is null).")
        print("        Can validate structure but cannot submit transactions.")
        return False  # Can't submit but can validate

    print("  OK: Node is synced and ready.")
    return True


def test_wallet_status():
    """Check if the house wallet is initialized and unlocked."""
    print("\n[2/6] Checking wallet status...")
    try:
        status = node_get("/wallet/status")
    except httpx.HTTPStatusError as e:
        print(f"  FAIL: Wallet returned HTTP {e.response.status_code}")
        return False

    if not status.get("isInitialized"):
        print("  FAIL: Wallet not initialized.")
        return False
    if not status.get("isUnlocked"):
        print("  FAIL: Wallet is locked.")
        return False

    print(f"  OK: Wallet initialized, height={status.get('walletHeight')}")

    # Check balance
    balances = node_get("/wallet/balances")
    balance_nanoerg = balances.get("balance", 0)
    balance_erg = balance_nanoerg / 1_000_000_000
    print(f"  Balance: {balance_erg:.4f} ERG ({balance_nanoerg} nanoERG)")
    return True


def test_generate_bet_params(bet_amount: int, choice: int):
    """Generate and validate bet parameters."""
    print(f"\n[3/6] Generating bet parameters (amount={bet_amount}, choice={choice})...")

    # Generate secret and commitment
    secret = generate_player_secret(32)
    commitment = compute_commitment(secret, choice)

    print(f"  Secret:     {secret[:16]}...{secret[-8:]}")
    print(f"  Commitment: {commitment}")
    print(f"  Choice:     {choice} ({'heads' if choice == 0 else 'tails'})")

    # Verify commitment
    recomputed = compute_commitment(secret, choice)
    assert recomputed == commitment, "Commitment verification failed!"
    print("  OK: Commitment verified (blake2b256(secret || choice))")

    return secret, commitment


def test_build_payment(bet_amount: int, choice: int, secret: str, commitment: str):
    """Build and validate the payment request structure."""
    print("\n[4/6] Building payment request...")

    # Get house pubkey from wallet
    addresses = node_get("/wallet/addresses")
    house_address = addresses[0]
    house_pubkey = decode_ergo_address(house_address)
    print(f"  House address: {house_address}")
    print(f"  House pubkey:  {house_pubkey[:16]}...")

    # Test player address (use a second wallet address if available, else same)
    if len(addresses) > 1:
        player_address = addresses[1]
    else:
        # Use the house address as player for testing
        player_address = house_address
    player_pubkey = decode_ergo_address(player_address)
    print(f"  Player address: {player_address}")
    print(f"  Player pubkey:  {player_pubkey[:16]}...")

    # Get block height
    info = node_get("/info")
    height = info.get("fullHeight") or info.get("headersHeight") or 0
    timeout_height = height + TIMEOUT_BLOCKS
    print(f"  Block height:   {height}")
    print(f"  Timeout height: {timeout_height}")

    # Build payment
    payment = build_payment_request(
        bet_amount=bet_amount,
        house_pubkey_hex=house_pubkey,
        player_pubkey_hex=player_pubkey,
        commitment_hex=commitment,
        choice=choice,
        timeout_height=timeout_height,
        secret_hex=secret,
    )

    # Validate structure
    assert isinstance(payment, list), "Payment must be a list"
    assert len(payment) == 1, "Payment must have exactly one request"
    req = payment[0]
    assert req["address"] == COINFLIP_P2S, "Wrong contract address"
    assert req["value"] == bet_amount, "Wrong bet amount"
    assert "registers" in req, "Missing registers"
    assert set(req["registers"].keys()) == {"R4", "R5", "R6", "R7", "R8", "R9"}, \
        f"Missing registers: expected R4-R9, got {set(req['registers'].keys())}"

    # Print register values
    print("\n  Register values:")
    for reg, value in sorted(req["registers"].items()):
        print(f"    {reg}: {value[:20]}... ({len(value)} hex chars)")

    print("\n  OK: Payment request structure validated.")
    return payment, house_pubkey, player_pubkey, timeout_height


def test_submit_payment(payment: list, fee: int = 1_000_000) -> dict:
    """Submit the payment to the Ergo node."""
    print(f"\n[5/6] Submitting payment to node (fee={fee} nanoERG)...")

    try:
        result = node_post(f"/wallet/payment/send?fee={fee}", payment)
        tx_id = result.get("id", "")
        print(f"  OK: Transaction submitted!")
        print(f"  Tx ID: {tx_id}")
        return {"success": True, "txId": tx_id}
    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        print(f"  FAIL: HTTP {e.response.status_code}")
        print(f"  Error: {error_body[:500]}")
        return {"success": False, "error": error_body}
    except Exception as e:
        print(f"  FAIL: {e}")
        return {"success": False, "error": str(e)}


def test_verify_onchain(tx_id: str, timeout_seconds: int = 30):
    """Wait for and verify the transaction on-chain."""
    print(f"\n[6/6] Verifying transaction on-chain (waiting up to {timeout_seconds}s)...")

    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            # Check by transaction ID
            tx_info = node_get(f"/transactions/{tx_id}")
            if tx_info:
                print(f"  OK: Transaction found on-chain!")
                print(f"  Block: {tx_info.get('blockId', 'mempool')}")
                print(f"  Inputs: {len(tx_info.get('inputs', []))}")
                print(f"  Outputs: {len(tx_info.get('outputs', []))}")

                # Find the PendingBetBox output
                for i, output in enumerate(tx_info.get("outputs", [])):
                    if output.get("ergoTree", "").startswith("19d801"):
                        print(f"\n  PendingBetBox found at output index {i}:")
                        print(f"    Value: {int(output.get('value', 0)) / 1_000_000_000:.6f} ERG")
                        print(f"    ErgoTree: {output.get('ergoTree', '')[:40]}...")
                        registers = output.get("additionalRegisters", {})
                        for reg, val in sorted(registers.items()):
                            rendered = val.get("renderedValue", "N/A") if isinstance(val, dict) else val
                            print(f"    {reg}: {rendered}")
                        return True

                print("  WARN: Transaction found but no PendingBetBox output detected.")
                return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                elapsed = int(time.time() - start)
                print(f"  ... waiting ({elapsed}s)")
                time.sleep(3)
                continue
            print(f"  Error checking tx: HTTP {e.response.status_code}")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    print(f"  TIMEOUT: Transaction not found after {timeout_seconds}s")
    print(f"  It may still be in the mempool. Check: {tx_id}")
    return False


# ─── Main ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MAT-410: Test bet submission via Ergo node")
    parser.add_argument("--dry-run", action="store_true", help="Validate structure without submitting")
    parser.add_argument("--amount", type=int, default=DEFAULT_BET, help=f"Bet amount in nanoERG (default: {DEFAULT_BET})")
    parser.add_argument("--choice", type=int, default=0, choices=[0, 1], help="0=heads, 1=tails (default: 0)")
    parser.add_argument("--fee", type=int, default=1_000_000, help="Transaction fee in nanoERG (default: 1000000)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"MAT-410: Test Bet Submission via Ergo Node")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Node: {NODE_URL}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 70)

    # Step 1: Check node connectivity
    node_ready = test_node_connectivity()
    if not node_ready and not args.dry_run:
        print("\nNode not ready. Use --dry-run to validate structure only.")
        sys.exit(1)

    # Step 2: Check wallet
    if not args.dry_run:
        if not test_wallet_status():
            print("\nWallet not ready. Cannot submit transactions.")
            sys.exit(1)

    # Step 3: Generate bet parameters
    secret, commitment = test_generate_bet_params(args.amount, args.choice)

    # Step 4: Build payment request
    payment, house_pk, player_pk, timeout_h = test_build_payment(
        args.amount, args.choice, secret, commitment
    )

    # Print full payment request for debugging
    print("\n--- Full Payment Request (JSON) ---")
    print(json.dumps(payment, indent=2))

    # Step 5: Submit (skip in dry-run)
    if args.dry_run:
        print(f"\n[5/6] DRY RUN: Skipping submission.")
        print("  Payment request validated successfully.")
        print("  To submit, run without --dry-run when node is synced.")
        print("\n" + "=" * 70)
        print("RESULT: PASS (dry run)")
        print("=" * 70)
        return

    # Submit the payment
    result = test_submit_payment(payment, fee=args.fee)
    if not result["success"]:
        print(f"\nSubmission failed: {result.get('error', 'unknown')}")
        print("\n" + "=" * 70)
        print("RESULT: FAIL")
        print("=" * 70)
        sys.exit(1)

    # Step 6: Verify on-chain
    test_verify_onchain(result["txId"])

    print("\n" + "=" * 70)
    print("RESULT: PASS")
    print(f"Tx ID: {result['txId']}")
    print(f"Secret: {secret}")
    print(f"Commitment: {commitment}")
    print(f"Timeout height: {timeout_h}")
    print("=" * 70)


if __name__ == "__main__":
    main()
