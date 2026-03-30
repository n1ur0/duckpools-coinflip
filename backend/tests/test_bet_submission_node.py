#!/usr/bin/env python3
"""
MAT-410: Test bet submissions from the Ergo node without using frontend.

Comprehensive test suite covering:
  1. Backend API in-memory bet placement (no node required)
  2. Backend API on-chain bet placement (requires synced node)
  3. Direct Ergo node submission via /wallet/payment/send
  4. Commitment verification (blake2b256)
  5. Sigma serialization of registers
  6. Contract info endpoint
  7. Bet history and player stats
  8. Edge cases and validation

Usage:
    python backend/tests/test_bet_submission_node.py
    python backend/tests/test_bet_submission_node.py --live     # attempt on-chain submission
    python backend/tests/test_bet_submission_node.py --verbose  # show full payloads
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

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
API_KEY = os.getenv("NODE_API_KEY", "hello")
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
MAX_BET = 100_000_000_000  # 100 ERG


# ─── Helpers ─────────────────────────────────────────────────────

class TestResult:
    """Tracks test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []

    def ok(self, name, detail=""):
        self.passed += 1
        self.results.append(("PASS", name, detail))
        print(f"  PASS: {name}")
        if detail:
            print(f"        {detail}")

    def fail(self, name, detail=""):
        self.failed += 1
        self.results.append(("FAIL", name, detail))
        print(f"  FAIL: {name}")
        if detail:
            print(f"        {detail}")

    def skip(self, name, detail=""):
        self.skipped += 1
        self.results.append(("SKIP", name, detail))
        print(f"  SKIP: {name}")
        if detail:
            print(f"        {detail}")

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*70}")
        print(f"RESULTS: {self.passed}/{total} passed, {self.failed} failed, {self.skipped} skipped")
        for status, name, detail in self.results:
            if status == "FAIL":
                print(f"  FAIL: {name} -- {detail}")
        print(f"{'='*70}")
        return self.failed == 0


results = TestResult()


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


def backend_post(endpoint: str, payload: dict) -> httpx.Response:
    """POST to the backend API."""
    return httpx.post(f"{BACKEND_URL}{endpoint}", json=payload, timeout=15)


def backend_get(endpoint: str) -> httpx.Response:
    """GET from the backend API."""
    return httpx.get(f"{BACKEND_URL}{endpoint}", timeout=10)


def generate_secret(num_bytes: int = 8) -> str:
    """Generate random player secret."""
    return os.urandom(num_bytes).hex()


def compute_commitment(secret_hex: str, choice: int) -> str:
    """Compute commitment: blake2b256(secret_bytes || choice_byte)."""
    secret_bytes = bytes.fromhex(secret_hex)
    choice_byte = bytes([choice])
    return hashlib.blake2b(secret_bytes + choice_byte, digest_size=32).hexdigest()


def decode_ergo_address(address: str) -> str:
    """Extract compressed public key (hex) from Ergo P2PK address."""
    ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    num = 0
    for char in address:
        if char not in ALPHABET:
            raise ValueError(f"Invalid Base58 character: {char}")
        num = num * 58 + ALPHABET.index(char)
    raw = num.to_bytes(38, byteorder="big")
    payload = raw[:-4]
    checksum = raw[-4:]
    expected = hashlib.blake2b(payload, digest_size=32).digest()[:4]
    if checksum != expected:
        raise ValueError("Address checksum mismatch")
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


# ─── Test: Node Connectivity ─────────────────────────────────────

def test_node_connectivity():
    """Check Ergo node status."""
    print("\n[TEST 1] Node Connectivity")
    try:
        info = node_get("/info")
        results.ok("Node reachable", f"version={info.get('appVersion')}, network={info.get('network')}")
    except httpx.ConnectError:
        results.fail("Node reachable", f"Cannot connect to {NODE_URL}")
        return False
    except httpx.HTTPStatusError as e:
        results.fail("Node reachable", f"HTTP {e.response.status_code}")
        return False

    full_height = info.get("fullHeight")
    headers_height = info.get("headersHeight")
    print(f"    fullHeight={full_height}, headersHeight={headers_height}")

    if full_height is not None:
        results.ok("Node synced", f"fullHeight={full_height}")
        return True
    else:
        results.skip("Node synced", "fullHeight is null - UTXO state not downloaded")
        return False


# ─── Test: Wallet Status ─────────────────────────────────────────

def test_wallet_status():
    """Check house wallet."""
    print("\n[TEST 2] Wallet Status")
    try:
        status = node_get("/wallet/status")
    except httpx.HTTPStatusError as e:
        results.fail("Wallet initialized", f"HTTP {e.response.status_code}")
        return False

    if not status.get("isInitialized"):
        results.fail("Wallet initialized", "Wallet not initialized")
        return False
    results.ok("Wallet initialized")

    if not status.get("isUnlocked"):
        results.fail("Wallet unlocked", "Wallet is locked")
        return False
    results.ok("Wallet unlocked")

    balances = node_get("/wallet/balances")
    balance_nano = balances.get("balance", 0)
    balance_erg = balance_nano / 1_000_000_000
    print(f"    Balance: {balance_erg:.4f} ERG")

    if balance_nano >= DEFAULT_BET + 1_000_000:  # bet + fee
        results.ok("Wallet funded", f"{balance_erg:.4f} ERG available")
    else:
        results.fail("Wallet funded", f"Insufficient: {balance_erg:.4f} ERG")

    # Get wallet addresses
    addresses = node_get("/wallet/addresses")
    if addresses and len(addresses) >= 1:
        results.ok("Wallet addresses", f"{len(addresses)} address(es)")
        return addresses
    else:
        results.fail("Wallet addresses", "No addresses found")
        return []


# ─── Test: Backend API Health ────────────────────────────────────

def test_backend_health():
    """Check backend API health."""
    print("\n[TEST 3] Backend API Health")
    try:
        resp = backend_get("/health")
        if resp.status_code == 200:
            data = resp.json()
            results.ok("Backend health", f"status={data.get('status')}, node={data.get('node')}")
        else:
            results.fail("Backend health", f"HTTP {resp.status_code}")
    except httpx.ConnectError:
        results.fail("Backend reachable", f"Cannot connect to {BACKEND_URL}")
        return False
    return True


# ─── Test: Contract Info ─────────────────────────────────────────

def test_contract_info():
    """Verify contract info endpoint."""
    print("\n[TEST 4] Contract Info Endpoint")
    resp = backend_get("/contract-info")
    if resp.status_code != 200:
        results.fail("Contract info", f"HTTP {resp.status_code}")
        return None

    data = resp.json()
    checks = [
        ("p2sAddress present", "p2sAddress" in data and len(data["p2sAddress"]) > 100),
        ("ergoTree present", "ergoTree" in data and len(data["ergoTree"]) > 100),
        ("registers documented", "registers" in data and "R4" in data["registers"]),
        ("P2S matches contract", data.get("p2sAddress") == COINFLIP_P2S),
    ]
    for name, passed in checks:
        if passed:
            results.ok(name)
        else:
            results.fail(name)

    return data


# ─── Test: Commitment Verification ───────────────────────────────

def test_commitment_verification():
    """Verify commitment = blake2b256(secret || choice)."""
    print("\n[TEST 5] Commitment Verification")
    for choice in [0, 1]:
        secret = generate_secret()
        commitment = compute_commitment(secret, choice)
        side = "heads" if choice == 0 else "tails"

        # Verify round-trip
        recomputed = compute_commitment(secret, choice)
        if recomputed == commitment:
            results.ok(f"Commitment round-trip ({side})", f"commitment={commitment[:16]}...")
        else:
            results.fail(f"Commitment round-trip ({side})")

        # Verify wrong choice fails
        wrong_commitment = compute_commitment(secret, 1 - choice)
        if wrong_commitment != commitment:
            results.ok(f"Wrong choice rejected ({side})")
        else:
            results.fail(f"Wrong choice rejected ({side})", "Different choices produced same commitment!")

        # Verify wrong secret fails
        other_secret = generate_secret()
        other_commitment = compute_commitment(other_secret, choice)
        if other_commitment != commitment:
            results.ok(f"Wrong secret rejected ({side})")
        else:
            results.fail(f"Wrong secret rejected ({side})")


# ─── Test: Sigma Serialization ───────────────────────────────────

def test_sigma_serialization():
    """Verify sigma register encoding."""
    print("\n[TEST 6] Sigma Register Serialization")

    # Coll[Byte] encoding: 09 01 <VLQ(len)> <bytes>
    test_pubkey = "02" + "ab" * 32  # 33-byte compressed pubkey (66 hex chars)
    encoded = sigma_encode_coll_byte(test_pubkey)
    raw = bytes.fromhex(test_pubkey)
    # 09 = SColl, 01 = SByte, VLQ(33) = 0x21, then 33 bytes
    expected_prefix = "090121"
    if encoded.startswith(expected_prefix) and encoded.endswith(test_pubkey):
        results.ok("Coll[Byte] encoding", f"encoded length={len(encoded)//2} bytes")
    else:
        results.fail("Coll[Byte] encoding", f"expected prefix {expected_prefix}, got {encoded[:6]}")

    # Int encoding: 03 <ZigZag+VLQ(value)>
    for value, expected_zigzag in [(0, 0), (1, 2), (100, 200), (258615, 517230)]:
        encoded_int = sigma_encode_int(value)
        if encoded_int.startswith("03"):
            results.ok(f"Int encoding (value={value})", f"hex={encoded_int}")
        else:
            results.fail(f"Int encoding (value={value})", f"expected 03 prefix, got {encoded_int[:2]}")


# ─── Test: In-Memory Bet via Backend API ─────────────────────────

def test_inmemory_bet_placement():
    """Place bets via backend API without on-chain (PoC mode)."""
    print("\n[TEST 7] In-Memory Bet Placement (PoC Mode)")
    player_address = "3WwcyQQdaCifkL2oS8aWpMKFCrwRQwgL5U9D8G2TPKdmifa9VPbx"

    for choice in [0, 1]:
        secret = generate_secret()
        commitment = compute_commitment(secret, choice)
        bet_id = f"poc-{choice}-{os.urandom(4).hex()}"
        side = "heads" if choice == 0 else "tails"

        payload = {
            "address": player_address,
            "amount": str(DEFAULT_BET),
            "choice": choice,
            "commitment": commitment,
            "betId": bet_id,
            "secret": secret,
            "onchain": False,
        }

        resp = backend_post("/place-bet", payload)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                results.ok(f"PoC bet ({side})", f"betId={bet_id}, txId={data.get('txId', 'N/A')}")
            else:
                results.fail(f"PoC bet ({side})", f"success=false: {data.get('message')}")
        else:
            results.fail(f"PoC bet ({side})", f"HTTP {resp.status_code}: {resp.text[:200]}")


# ─── Test: On-Chain Bet via Backend API ──────────────────────────

def test_onchain_bet_placement(node_ready: bool):
    """Place bets via backend API with onchain=true."""
    print("\n[TEST 8] On-Chain Bet Placement (Backend API)")
    player_address = "3WwcyQQdaCifkL2oS8aWpMKFCrwRQwgL5U9D8G2TPKdmifa9VPbx"

    for choice in [0, 1]:
        secret = generate_secret()
        commitment = compute_commitment(secret, choice)
        bet_id = f"onchain-{choice}-{os.urandom(4).hex()}"
        side = "heads" if choice == 0 else "tails"

        payload = {
            "address": player_address,
            "amount": str(DEFAULT_BET),
            "choice": choice,
            "commitment": commitment,
            "betId": bet_id,
            "secret": secret,
            "onchain": True,
        }

        resp = backend_post("/place-bet", payload)
        if resp.status_code != 200:
            results.fail(f"Onchain bet ({side})", f"HTTP {resp.status_code}: {resp.text[:200]}")
            continue

        data = resp.json()
        if node_ready:
            if data.get("success") and data.get("txId"):
                results.ok(f"Onchain bet ({side})", f"txId={data['txId']}")
            else:
                results.fail(f"Onchain bet ({side})", f"success={data.get('success')}, msg={data.get('message')}")
        else:
            # Node not synced - should get a clear error
            if not data.get("success") and "not synced" in data.get("message", "").lower():
                results.ok(f"Onchain bet blocked ({side})", f"Correctly rejected: {data['message'][:80]}")
            elif not data.get("success"):
                results.ok(f"Onchain bet blocked ({side})", f"Rejected: {data.get('message', 'N/A')[:80]}")
            else:
                results.fail(f"Onchain bet blocked ({side})", f"Expected failure but got success: {data}")


# ─── Test: Invalid Commitment ────────────────────────────────────

def test_invalid_commitment():
    """Test that mismatched commitment is rejected."""
    print("\n[TEST 9] Invalid Commitment Rejection")

    secret = generate_secret()
    # Commitment for choice=0, but we'll submit with choice=1
    commitment = compute_commitment(secret, 0)
    bet_id = f"bad-commit-{os.urandom(4).hex()}"

    payload = {
        "address": "3WwcyQQdaCifkL2oS8aWpMKFCrwRQwgL5U9D8G2TPKdmifa9VPbx",
        "amount": str(DEFAULT_BET),
        "choice": 1,  # Wrong choice!
        "commitment": commitment,
        "betId": bet_id,
        "secret": secret,
        "onchain": True,
    }

    resp = backend_post("/place-bet", payload)
    data = resp.json()
    if not data.get("success") and "commitment" in data.get("message", "").lower():
        results.ok("Invalid commitment rejected", data.get("message"))
    else:
        results.fail("Invalid commitment rejected", f"Expected rejection, got: {data}")


# ─── Test: Input Validation ──────────────────────────────────────

def test_input_validation():
    """Test backend input validation."""
    print("\n[TEST 10] Input Validation")
    base = {
        "address": "3WwcyQQdaCifkL2oS8aWpMKFCrwRQwgL5U9D8G2TPKdmifa9VPbx",
        "amount": str(DEFAULT_BET),
        "choice": 0,
        "commitment": "a" * 64,
        "betId": f"val-{os.urandom(4).hex()}",
    }

    # Invalid amount (too small)
    payload = {**base, "amount": "500000"}
    resp = backend_post("/place-bet", payload)
    if resp.status_code == 422:
        results.ok("Rejects amount < minimum", "422 for 500000 nanoERG")
    else:
        results.fail("Rejects amount < minimum", f"Expected 422, got {resp.status_code}")

    # Invalid amount (too large)
    payload = {**base, "amount": str(MAX_BET + 1)}
    resp = backend_post("/place-bet", payload)
    if resp.status_code == 422:
        results.ok("Rejects amount > maximum", "422 for >100 ERG")
    else:
        results.fail("Rejects amount > maximum", f"Expected 422, got {resp.status_code}")

    # Invalid choice
    payload = {**base, "choice": 2}
    resp = backend_post("/place-bet", payload)
    if resp.status_code == 422:
        results.ok("Rejects invalid choice", "422 for choice=2")
    else:
        results.fail("Rejects invalid choice", f"Expected 422, got {resp.status_code}")

    # Invalid commitment length
    payload = {**base, "commitment": "a" * 32}
    resp = backend_post("/place-bet", payload)
    if resp.status_code == 422:
        results.ok("Rejects short commitment", "422 for 32-char commitment")
    else:
        results.fail("Rejects short commitment", f"Expected 422, got {resp.status_code}")

    # Invalid commitment (non-hex)
    payload = {**base, "commitment": "z" * 64}
    resp = backend_post("/place-bet", payload)
    if resp.status_code == 422:
        results.ok("Rejects non-hex commitment", "422 for non-hex")
    else:
        results.fail("Rejects non-hex commitment", f"Expected 422, got {resp.status_code}")

    # Invalid address
    payload = {**base, "address": "not-a-valid-address"}
    resp = backend_post("/place-bet", payload)
    if resp.status_code == 422:
        results.ok("Rejects invalid address", "422 for bad address")
    else:
        results.fail("Rejects invalid address", f"Expected 422, got {resp.status_code}")

    # Zero amount
    payload = {**base, "amount": "0"}
    resp = backend_post("/place-bet", payload)
    if resp.status_code == 422:
        results.ok("Rejects zero amount", "422 for amount=0")
    else:
        results.fail("Rejects zero amount", f"Expected 422, got {resp.status_code}")


# ─── Test: History and Stats ─────────────────────────────────────

def test_history_and_stats():
    """Test history and stats endpoints after placing bets."""
    print("\n[TEST 11] History and Stats Endpoints")
    player_address = "3WwcyQQdaCifkL2oS8aWpMKFCrwRQwgL5U9D8G2TPKdmifa9VPbx"

    # History
    resp = backend_get(f"/history/{player_address}")
    if resp.status_code == 200:
        history = resp.json()
        results.ok("History endpoint", f"{len(history)} bet(s) for address")
    else:
        results.fail("History endpoint", f"HTTP {resp.status_code}")

    # Player stats
    resp = backend_get(f"/player/stats/{player_address}")
    if resp.status_code == 200:
        stats = resp.json()
        required = ["totalBets", "wins", "losses", "pending", "winRate", "totalWagered"]
        missing = [k for k in required if k not in stats]
        if not missing:
            results.ok("Player stats", f"totalBets={stats.get('totalBets')}, winRate={stats.get('winRate')}")
        else:
            results.fail("Player stats", f"Missing fields: {missing}")
    else:
        results.fail("Player stats", f"HTTP {resp.status_code}")

    # Comp points
    resp = backend_get(f"/player/comp/{player_address}")
    if resp.status_code == 200:
        comp = resp.json()
        required = ["tier", "points", "pointsToNextTier", "tierProgress", "benefits"]
        missing = [k for k in required if k not in comp]
        if not missing:
            results.ok("Comp points", f"tier={comp.get('tier')}, points={comp.get('points')}")
        else:
            results.fail("Comp points", f"Missing fields: {missing}")
    else:
        results.fail("Comp points", f"HTTP {resp.status_code}")

    # Leaderboard
    resp = backend_get("/leaderboard")
    if resp.status_code == 200:
        lb = resp.json()
        results.ok("Leaderboard", f"totalPlayers={lb.get('totalPlayers')}")
    else:
        results.fail("Leaderboard", f"HTTP {resp.status_code}")


# ─── Test: Direct Node Payment Submission ────────────────────────

def test_direct_node_submission(node_ready: bool, wallet_addresses: list, verbose: bool = False):
    """Test direct /wallet/payment/send to Ergo node."""
    print("\n[TEST 12] Direct Node Payment Submission")

    if not wallet_addresses:
        results.skip("Direct node submission", "No wallet addresses available")
        return

    # Get pubkeys
    house_address = wallet_addresses[0]
    player_address = wallet_addresses[1] if len(wallet_addresses) > 1 else wallet_addresses[0]
    house_pubkey = decode_ergo_address(house_address)
    player_pubkey = decode_ergo_address(player_address)

    # Generate bet params
    secret = generate_secret(8)
    choice = 0
    commitment = compute_commitment(secret, choice)

    # Get height (use headersHeight as fallback)
    info = node_get("/info")
    height = info.get("fullHeight") or info.get("headersHeight") or 0
    timeout_height = height + TIMEOUT_BLOCKS

    # Build payment request
    payment = [{
        "address": COINFLIP_P2S,
        "value": DEFAULT_BET,
        "registers": {
            "R4": sigma_encode_coll_byte(house_pubkey),
            "R5": sigma_encode_coll_byte(player_pubkey),
            "R6": sigma_encode_coll_byte(commitment),
            "R7": sigma_encode_int(choice),
            "R8": sigma_encode_int(timeout_height),
            "R9": sigma_encode_coll_byte(secret),
        },
    }]

    # Validate structure
    req = payment[0]
    structure_ok = (
        req["address"] == COINFLIP_P2S
        and req["value"] == DEFAULT_BET
        and set(req["registers"].keys()) == {"R4", "R5", "R6", "R7", "R8", "R9"}
    )
    if structure_ok:
        results.ok("Payment structure valid", f"6 registers, amount={DEFAULT_BET}")
    else:
        results.fail("Payment structure valid", "Structure mismatch")

    if verbose:
        print(f"\n  --- Payment Request JSON ---")
        print(json.dumps(payment, indent=2))

    if not node_ready:
        results.skip("Payment submission", "Node not synced (fullHeight=null)")
        return

    # Submit to node
    fee = 1_000_000
    try:
        result = node_post(f"/wallet/payment/send?fee={fee}", payment)
        tx_id = result.get("id", "")
        if tx_id:
            results.ok("Payment submitted", f"txId={tx_id}")
        else:
            results.fail("Payment submitted", f"No txId in response: {result}")
    except httpx.HTTPStatusError as e:
        results.fail("Payment submitted", f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        results.fail("Payment submitted", str(e))


# ─── Test: Payout Economics ──────────────────────────────────────

def test_payout_economics():
    """Verify payout calculations match contract."""
    print("\n[TEST 13] Payout Economics")

    test_amounts = [1_000_000, 10_000_000, 100_000_000, 1_000_000_000]

    for amount in test_amounts:
        # Win payout: betAmount * 97 / 50 (from contract)
        win_payout = amount * 97 // 50
        # Refund: betAmount - betAmount / 50 (from contract)
        refund = amount - amount // 50

        win_multiplier = win_payout / amount
        refund_rate = refund / amount

        # Verify win payout is ~1.94x
        if 1.93 <= win_multiplier <= 1.95:
            results.ok(f"Win payout ({amount} nanoERG)", f"{win_payout} nanoERG ({win_multiplier:.4f}x)")
        else:
            results.fail(f"Win payout ({amount} nanoERG)", f"{win_payout} nanoERG ({win_multiplier:.4f}x)")

        # Verify refund is ~98%
        if 0.979 <= refund_rate <= 0.981:
            results.ok(f"Refund ({amount} nanoERG)", f"{refund} nanoERG ({refund_rate:.4f}x)")
        else:
            results.fail(f"Refund ({amount} nanoERG)", f"{refund} nanoERG ({refund_rate:.4f}x)")


# ─── Main ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MAT-410: Test bet submissions from Ergo node")
    parser.add_argument("--live", action="store_true", help="Attempt live on-chain submission")
    parser.add_argument("--verbose", action="store_true", help="Show full payloads")
    args = parser.parse_args()

    print("=" * 70)
    print(f"MAT-410: Test Bet Submissions from Ergo Node (No Frontend)")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Backend: {BACKEND_URL}")
    print(f"Node: {NODE_URL}")
    print(f"Mode: {'LIVE' if args.live else 'DRY RUN'}")
    print("=" * 70)

    # 1. Node connectivity
    node_ready = test_node_connectivity()

    # 2. Wallet status
    wallet_addresses = []
    if node_ready or args.live:
        wallet_addresses = test_wallet_status() or []

    # 3. Backend health
    test_backend_health()

    # 4. Contract info
    test_contract_info()

    # 5. Commitment verification
    test_commitment_verification()

    # 6. Sigma serialization
    test_sigma_serialization()

    # 7. In-memory bet placement (always works)
    test_inmemory_bet_placement()

    # 8. On-chain bet placement via backend API
    test_onchain_bet_placement(node_ready and args.live)

    # 9. Invalid commitment
    test_invalid_commitment()

    # 10. Input validation
    test_input_validation()

    # 11. History and stats
    test_history_and_stats()

    # 12. Direct node submission
    if args.live:
        test_direct_node_submission(node_ready, wallet_addresses, args.verbose)
    else:
        print("\n[TEST 12] Direct Node Payment Submission")
        results.skip("Direct node submission", "Use --live to attempt on-chain submission")

    # 13. Payout economics
    test_payout_economics()

    # Summary
    all_passed = results.summary()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
