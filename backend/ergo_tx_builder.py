"""
DuckPools - Ergo Transaction Builder

Builds real EIP-12 compatible transactions for the coinflip protocol.
Handles serialization of Ergo types (SigmaProp, Coll[Byte], Int registers)
for submission to the Ergo node wallet API.

MAT-394 Phase 3: Backend API fix + wallet integration

Contract: coinflip_v2_final.es
  R4: Coll[Byte]  -- house compressed public key (33 bytes)
  R5: Coll[Byte]  -- player compressed public key (33 bytes)
  R6: Coll[Byte]  -- blake2b256(secret || choice_byte) (32 bytes)
  R7: Int         -- player's choice: 0=heads, 1=tails
  R8: Int         -- timeout block height
  R9: Coll[Byte]  -- player secret (8 random bytes)

Economics (from contract):
  House edge: 3%  -> winPayout = betAmount * 97 / 50
  Refund fee: 2%  -> refundAmount = betAmount - betAmount / 50
"""

import hashlib
import json
import logging
import os
from base64 import b64encode
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("duckpools.ergo_tx")

NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")


def _node_headers(content_type: str = "application/json") -> dict:
    """Build headers for Ergo node API calls."""
    headers = {"Content-Type": content_type}
    if NODE_API_KEY:
        headers["api_key"] = NODE_API_KEY
    return headers


async def _node_post(endpoint: str, payload: dict, timeout: float = 30) -> dict:
    """POST to the Ergo node and return JSON response."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{NODE_URL}{endpoint}",
            headers=_node_headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def _node_get(endpoint: str, timeout: float = 10) -> dict:
    """GET from the Ergo node and return JSON response."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{NODE_URL}{endpoint}",
            headers=_node_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def get_node_height() -> int:
    """Fetch current block height from Ergo node."""
    info = await _node_get("/info")
    height = info.get("fullHeight") or 0
    return int(height)


async def get_block_header_at_height(height: int) -> dict:
    """Fetch block header at a given height for RNG seed."""
    headers_resp = await _node_get(f"/blocks/at/{height}")
    if isinstance(headers_resp, list) and len(headers_resp) > 0:
        header_id = headers_resp[0]
        header = await _node_get(f"/blocks/{header_id}/header")
        return header
    elif isinstance(headers_resp, dict):
        return headers_resp
    raise ValueError(f"Could not get block header at height {height}")


def encode_coll_byte(hex_str: str) -> str:
    """
    Encode a hex string as a Coll[Byte] SValue for Ergo node.

    The node expects: "wrapped value bytes" which for Coll[Byte] is:
      1 byte: element type (ConstantType.CollByte = 004)
      N bytes: the raw byte array
    But for the /wallet endpoints with registers, we can use the simpler
    serialization that the node understands.
    """
    # For node wallet API registers, use the Sigma serialziation format:
    # Coll[Byte] value encoding: first byte is element type (0x04 = SByte),
    # then the raw bytes
    raw_bytes = bytes.fromhex(hex_str)
    # SByte type tag = 0x04
    encoded = bytes([0x04]) + raw_bytes
    return encoded.hex()


def sigma_encode_coll_byte(hex_str: str) -> str:
    """
    Encode as sigma-serialized Constant(Coll[SByte]) for node register values.

    Format: 09 01 <VLQ(len)> <raw_bytes>
      09 = SColl type ID
      01 = SByte element type ID
      VLQ(len) = variable-length quantity encoding of byte array length
      raw_bytes = the actual byte data

    This is the correct format for the /wallet/payment/send registers field.
    """
    raw = bytes.fromhex(hex_str)
    length = len(raw)
    return f"0901{_encode_vlq_unsigned(length)}{raw.hex()}"


def sigma_encode_int(value: int) -> str:
    """
    Encode as sigma-serialized Constant(SInt) for node register values.

    Format: 03 <ZigZag+VLQ(value)>
      03 = SInt type ID
      ZigZag encoding: (n << 1) ^ (n >> 63)
      VLQ encoding: variable-length quantity of unsigned zigzag value

    Used for R7 (playerChoice) and R8 (timeoutHeight).
    """
    # ZigZag encode for signed integers
    if value >= 0:
        zz = value * 2
    else:
        zz = (-value) * 2 - 1
    return f"03{_encode_vlq_unsigned(zz)}"


def _encode_vlq_unsigned(value: int) -> str:
    """
    VLQ (Variable Length Quantity) encoding for unsigned values.
    Each byte has 7 data bits + 1 continuation bit (MSB = 1 means more bytes).
    """
    if value == 0:
        return "00"

    bytes_list = []
    remaining = value
    while remaining > 0:
        byte = remaining & 0x7F
        remaining >>= 7
        bytes_list.append(byte)

    # Reverse to big-endian
    bytes_list.reverse()

    # Set continuation bits (all bytes except last get MSB=1)
    for i in range(len(bytes_list) - 1):
        bytes_list[i] |= 0x80

    return bytes(bytes_list).hex()


def encode_int_value(value: int) -> str:
    """
    Encode an integer as an Ergo SInt value for node registers.

    Uses VLQ encoding with sign bit.
    """
    return _encode_vlq(value)


def _encode_vlq(value: int) -> str:
    """VLQ (Variable Length Quantity) encoding with sign bit."""
    negative = value < 0
    abs_val = abs(value)

    # Convert to unsigned with sign bit in bit 7 of last byte
    # VLQ: each byte has 7 data bits + 1 continuation bit (MSB)
    if abs_val == 0:
        return "00"

    bytes_list = []
    remaining = abs_val

    while remaining > 0:
        byte = remaining & 0x7F
        remaining >>= 7
        bytes_list.append(byte)

    # Reverse to get big-endian order
    bytes_list.reverse()

    # Set continuation bits
    for i in range(len(bytes_list) - 1):
        bytes_list[i] |= 0x80

    # Set sign bit in last byte
    if negative:
        bytes_list[-1] |= 0x40

    return bytes(bytes_list).hex()


def decode_coll_byte_from_node(serialized_hex: str) -> str:
    """
    Decode a Coll[SByte] value from node's sigma-serialized format.
    Returns the raw hex string of the byte array.

    Node format: 09 (SColl) 01 (SByte element type) <VLQ(len)> <raw_bytes>
    """
    raw = bytes.fromhex(serialized_hex)
    if len(raw) < 3:
        return serialized_hex
    # Check for Coll[SByte] prefix
    if raw[0] == 0x09 and raw[1] == 0x01:
        # Decode VLQ length starting at byte 2
        length = 0
        i = 2
        while i < len(raw):
            byte = raw[i]
            length = (length << 7) | (byte & 0x7F)
            i += 1
            if not (byte & 0x80):
                break
        return raw[i:i + length].hex()
    # Fallback: skip first byte (legacy format)
    return raw[1:].hex()


def decode_int_from_node(serialized_hex: str) -> int:
    """
    Decode an SInt value from node's sigma-serialized format.

    Node format: 03 <zigzag_vlq(value)>
    Zigzag encoding: (n << 1) ^ (n >> 63), then VLQ-encoded.
    """
    raw = bytes.fromhex(serialized_hex)
    if not raw:
        return 0

    # Strip SInt type byte (0x03)
    if raw[0] == 0x03:
        raw = raw[1:]

    # Decode VLQ
    zigzag_val = 0
    for b in raw:
        zigzag_val = (zigzag_val << 7) | (b & 0x7F)

    # Zigzag decode: (n >> 1) ^ -(n & 1)
    return (zigzag_val >> 1) ^ -(zigzag_val & 1)


def compute_win_payout(bet_amount: int) -> int:
    """
    Calculate win payout matching coinflip_v2_final.es exactly.

    On-chain: winPayout = betAmount * 97L / 50L  (1.94x)
    This is integer division in ErgoScript (truncates toward zero).
    """
    return bet_amount * 97 // 50


def compute_refund_amount(bet_amount: int) -> int:
    """
    Calculate refund amount matching coinflip_v2_final.es exactly.

    On-chain: refundAmount = betAmount - betAmount / 50L  (98%)
    """
    return bet_amount - bet_amount // 50


def compute_rng(block_hash_hex: str, secret_hex: str) -> int:
    """
    Compute RNG outcome matching on-chain contract exactly.

    Delegates to rng_module.compute_rng after hex-decoding inputs.
    Formula: blake2b256(blockId_raw_bytes || playerSecret_raw_bytes)[0] % 2

    Args:
        block_hash_hex: Block ID as 64-char hex string
        secret_hex: Player secret as hex string
    """
    from rng_module import compute_rng as _compute_rng
    return _compute_rng(block_hash_hex, secret_hex)


def verify_commitment(secret_hex: str, choice: int, commitment_hex: str) -> bool:
    """
    Verify that commitment = blake2b256(secret || choice_byte).
    Delegates to rng_module.verify_commit for single source of truth.
    Matches on-chain: blake2b256(playerSecret ++ Coll(choiceByte)) == commitmentHash
    """
    from rng_module import verify_commit as _verify_commit
    return _verify_commit(commitment_hex, secret_hex, choice)


def build_reveal_outputs(
    bet_amount: int,
    player_wins: bool,
    player_address: str,
    house_address: str,
    current_height: int,
) -> List[dict]:
    """
    Build the output for a reveal transaction.

    On-chain contract requires:
      - If playerWins: OUTPUTS(0) goes to player with value >= winPayout
      - If houseWins: OUTPUTS(0) goes to house with value >= betAmount

    Returns a list of output requests for the node wallet API.
    """
    if player_wins:
        payout = compute_win_payout(bet_amount)
        recipient = player_address
    else:
        payout = bet_amount
        recipient = house_address

    return [{
        "address": recipient,
        "value": str(payout),
        "creationHeight": current_height,
    }]


def build_refund_outputs(
    bet_amount: int,
    player_address: str,
    current_height: int,
) -> List[dict]:
    """
    Build the output for a refund transaction.

    On-chain contract requires:
      OUTPUTS(0).value >= refundAmount  (98% of bet)

    Returns a list of output requests for the node wallet API.
    """
    refund = compute_refund_amount(bet_amount)
    return [{
        "address": player_address,
        "value": str(refund),
        "creationHeight": current_height,
    }]


async def build_and_send_reveal_tx(
    bet_box_id: str,
    bet_amount: int,
    player_address: str,
    house_address: str,
    player_wins: bool,
    current_height: int,
    fee: int = 1_000_000,
) -> dict:
    """
    Build and submit a reveal transaction via the Ergo node wallet.

    Uses /wallet/transaction/send with rawInputs to spend the PendingBetBox.
    The house wallet must be unlocked on the node.

    Args:
        bet_box_id: On-chain box ID of the PendingBetBox
        bet_amount: Value of the bet box in nanoERG
        player_address: Player's P2PK address (from R5 register)
        house_address: House's P2PK address (from R4 register)
        player_wins: Whether the player won
        current_height: Current block height
        fee: Transaction fee in nanoERG

    Returns:
        dict with txId, player_wins, payout_amount
    """
    # Build outputs
    outputs = build_reveal_outputs(
        bet_amount, player_wins, player_address, house_address, current_height
    )

    # Build the transaction request
    # Using rawInputs lets us specify exactly which box to spend
    tx_request = {
        "requests": outputs,
        "rawInputs": [bet_box_id],
        "fee": str(fee),
    }

    logger.info(
        "Submitting reveal tx: box=%s amount=%d player_wins=%s",
        bet_box_id, bet_amount, player_wins,
    )

    try:
        result = await _node_post("/wallet/transaction/send", tx_request)
        tx_id = result.get("id", "")

        payout = compute_win_payout(bet_amount) if player_wins else bet_amount

        return {
            "success": True,
            "txId": tx_id,
            "player_wins": player_wins,
            "payout_amount": str(payout),
            "message": f"Reveal tx submitted: {tx_id}",
        }
    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        logger.error(
            "Reveal tx failed: status=%d body=%s", e.response.status_code, error_body
        )
        return {
            "success": False,
            "txId": "",
            "player_wins": player_wins,
            "payout_amount": "0",
            "message": f"Reveal tx failed: {error_body}",
        }
    except Exception as e:
        logger.error("Reveal tx error: %s", e)
        return {
            "success": False,
            "txId": "",
            "player_wins": player_wins,
            "payout_amount": "0",
            "message": f"Reveal tx error: {str(e)}",
        }


async def build_unsigned_reveal_tx(
    bet_box_id: str,
    bet_amount: int,
    player_address: str,
    house_address: str,
    player_wins: bool,
    current_height: int,
) -> str:
    """
    Build an unsigned EIP-12 reveal transaction for external signing.

    Returns base64-encoded unsigned transaction JSON.

    The reveal spending path in coinflip_v2_final.es requires:
      - houseProp (house must sign)
      - commitmentOk (verified on-chain from registers)
      - HEIGHT in [rngBlockHeight, timeoutHeight]
      - OUTPUTS(0) to winner with correct amount
    """
    outputs = build_reveal_outputs(
        bet_amount, player_wins, player_address, house_address, current_height
    )

    unsigned_tx = {
        "inputs": [{
            "boxId": bet_box_id,
            "spendingProof": {
                "proofBytes": "",
                "extension": {},
            },
        }],
        "dataInputs": [],
        "outputs": outputs,
    }

    return b64encode(json.dumps(unsigned_tx).encode()).decode()


async def build_and_send_refund_tx(
    bet_box_id: str,
    bet_amount: int,
    player_address: str,
    current_height: int,
    fee: int = 1_000_000,
) -> dict:
    """
    Build and submit a refund transaction via the Ergo node wallet.

    Uses /wallet/transaction/send with rawInputs.
    Player can sign via their wallet (Nautilus) if not using house wallet.

    Args:
        bet_box_id: On-chain box ID of the PendingBetBox
        bet_amount: Value of the bet box in nanoERG
        player_address: Player's P2PK address
        current_height: Current block height
        fee: Transaction fee in nanoERG

    Returns:
        dict with txId, refund_amount
    """
    outputs = build_refund_outputs(bet_amount, player_address, current_height)

    tx_request = {
        "requests": outputs,
        "rawInputs": [bet_box_id],
        "fee": str(fee),
    }

    logger.info(
        "Submitting refund tx: box=%s amount=%d player=%s",
        bet_box_id, bet_amount, player_address,
    )

    try:
        result = await _node_post("/wallet/transaction/send", tx_request)
        tx_id = result.get("id", "")
        refund = compute_refund_amount(bet_amount)

        return {
            "success": True,
            "txId": tx_id,
            "refund_amount": str(refund),
            "refund_fee": str(bet_amount - refund),
            "message": f"Refund tx submitted: {tx_id}",
        }
    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        logger.error(
            "Refund tx failed: status=%d body=%s", e.response.status_code, error_body
        )
        return {
            "success": False,
            "txId": "",
            "refund_amount": "0",
            "message": f"Refund tx failed: {error_body}",
        }
    except Exception as e:
        logger.error("Refund tx error: %s", e)
        return {
            "success": False,
            "txId": "",
            "refund_amount": "0",
            "message": f"Refund tx error: {str(e)}",
        }


async def fetch_unspent_box(box_id: str) -> Optional[dict]:
    """Fetch an unspent box by ID from the Ergo node."""
    try:
        return await _node_get(f"/blockchain/box/{box_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise


async def fetch_wallet_balances() -> dict:
    """Fetch house wallet balances from the Ergo node."""
    return await _node_get("/wallet/balances")


# ─── Place Bet (PendingBetBox Creation) ──────────────────────────
# MAT-410: Test bet submissions from the ergo node without frontend.
#
# Creates a PendingBetBox on-chain via /wallet/payment/send.
# The box contains the coinflip contract (ergoTree) with registers:
#   R4: housePubKey (Coll[Byte])
#   R5: playerPubKey (Coll[Byte])
#   R6: commitmentHash (Coll[Byte]) = blake2b256(secret || choice_byte)
#   R7: playerChoice (Int) = 0 or 1
#   R8: timeoutHeight (Int) = currentHeight + TIMEOUT_BLOCKS
#   R9: playerSecret (Coll[Byte])

# P2S address of the compiled coinflip contract (from coinflip_deployed.json)
COINFLIP_P2S = (
    "3yNMkSZ6b36YGBJJNhpavxxCFg4f2ceH5JF81hXJgzWoWozuFJSjoW8Q5JXow6fs"
    "TVNrqz48h8a9ajYSTKfwaxG16GbHzxrDcsarkBkbR6NYdGeoCZ9KgNcNMYPLV9RP"
    "kLFwBPLHxDxyTmBfqn5L75zqftETuAadKr8FHEYZrVPZ6kn6gdiZbzMwghxRy2g4w"
    "pTdby4jnxhA42UH7JJzMibgMNBW4yvzw8EaguPLVja6xsxx43yihw5DEzMGzL7HKWY"
    "Us6uVugK1C8Feh3KUX9kpea5xpLXX5oZCV47W6cnTrJfJD3"
)

TIMEOUT_BLOCKS = 100  # Refund available after 100 blocks


def build_place_bet_registers(
    house_pubkey_hex: str,
    player_pubkey_hex: str,
    commitment_hex: str,
    choice: int,
    timeout_height: int,
    secret_hex: str,
) -> dict:
    """
    Build the register map for a PendingBetBox.

    All values are sigma-serialized Constant hex strings for the
    /wallet/payment/send registers field.

    Args:
        house_pubkey_hex: 33-byte compressed public key (66 hex chars)
        player_pubkey_hex: 33-byte compressed public key (66 hex chars)
        commitment_hex: 32-byte blake2b256 hash (64 hex chars)
        choice: 0 (heads) or 1 (tails)
        timeout_height: Block height for refund availability
        secret_hex: Player's random secret bytes (variable length)

    Returns:
        dict mapping register names to sigma-serialized hex values
    """
    return {
        "R4": sigma_encode_coll_byte(house_pubkey_hex),
        "R5": sigma_encode_coll_byte(player_pubkey_hex),
        "R6": sigma_encode_coll_byte(commitment_hex),
        "R7": sigma_encode_int(choice),
        "R8": sigma_encode_int(timeout_height),
        "R9": sigma_encode_coll_byte(secret_hex),
    }


def build_place_bet_payment(
    bet_amount: int,
    house_pubkey_hex: str,
    player_pubkey_hex: str,
    commitment_hex: str,
    choice: int,
    timeout_height: int,
    secret_hex: str,
    fee: int = 1_000_000,
) -> list:
    """
    Build the payment request array for /wallet/payment/send.

    The Ergo node payment endpoint accepts an array of PaymentRequest
    objects. Each request creates one output box.

    Returns:
        list of PaymentRequest dicts for the node API
    """
    registers = build_place_bet_registers(
        house_pubkey_hex, player_pubkey_hex, commitment_hex,
        choice, timeout_height, secret_hex,
    )

    return [{
        "address": COINFLIP_P2S,
        "value": bet_amount,
        "registers": registers,
    }]


async def place_bet_onchain(
    bet_amount: int,
    house_pubkey_hex: str,
    player_pubkey_hex: str,
    commitment_hex: str,
    choice: int,
    secret_hex: str,
    timeout_blocks: int = TIMEOUT_BLOCKS,
    fee: int = 1_000_000,
) -> dict:
    """
    Place a bet on-chain by creating a PendingBetBox via the Ergo node.

    Uses /wallet/payment/send (NOT /wallet/transaction/send) because the
    transaction endpoint silently drops outputs with custom ergoTree +
    additionalRegisters (MAT-27 bug).

    The payment endpoint correctly handles registers and creates the
    PendingBetBox with the coinflip contract ergoTree.

    Args:
        bet_amount: Bet amount in nanoERG (min 1,000,000 = 0.001 ERG)
        house_pubkey_hex: House's 33-byte compressed public key (66 hex chars)
        player_pubkey_hex: Player's 33-byte compressed public key (66 hex chars)
        commitment_hex: blake2b256(secret || choice_byte) (64 hex chars)
        choice: Player's choice: 0=heads, 1=tails
        secret_hex: Player's random secret bytes (hex string)
        timeout_blocks: Blocks until refund is available (default 100)
        fee: Transaction fee in nanoERG (default 0.001 ERG)

    Returns:
        dict with success, txId, message (or error details)
    """
    # Get current block height for timeout calculation
    height = await get_node_height()
    if height == 0:
        return {
            "success": False,
            "txId": "",
            "message": "Node not synced (fullHeight is null). Cannot determine block height for timeout.",
        }

    timeout_height = height + timeout_blocks

    # Build payment request
    payments = build_place_bet_payment(
        bet_amount=bet_amount,
        house_pubkey_hex=house_pubkey_hex,
        player_pubkey_hex=player_pubkey_hex,
        commitment_hex=commitment_hex,
        choice=choice,
        timeout_height=timeout_height,
        secret_hex=secret_hex,
        fee=fee,
    )

    logger.info(
        "Submitting place-bet tx: amount=%d choice=%d timeout=%d house=%s... player=%s...",
        bet_amount, choice, timeout_height,
        house_pubkey_hex[:8], player_pubkey_hex[:8],
    )

    try:
        result = await _node_post(
            f"/wallet/payment/send?fee={fee}",
            payments,
            timeout=30,
        )
        tx_id = result.get("id", "")

        return {
            "success": True,
            "txId": tx_id,
            "timeoutHeight": timeout_height,
            "message": f"Bet placed on-chain. Tx: {tx_id}. Timeout at height {timeout_height}.",
        }
    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        logger.error("Place-bet tx failed: status=%d body=%s", e.response.status_code, error_body)
        return {
            "success": False,
            "txId": "",
            "message": f"Place-bet failed (HTTP {e.response.status_code}): {error_body}",
        }
    except Exception as e:
        logger.error("Place-bet tx error: %s", e)
        return {
            "success": False,
            "txId": "",
            "message": f"Place-bet error: {str(e)}",
        }


def decode_ergo_address_to_pubkey(address: str) -> str:
    """
    Extract compressed public key from an Ergo P2PK address.

    Ergo P2PK address encoding (Base58Check):
      1 byte: type (0x01 for P2PK)
      33 bytes: compressed public key
      4 bytes: checksum

    Args:
        address: Base58Check-encoded Ergo P2PK address

    Returns:
        66-char hex string of the compressed public key

    Raises:
        ValueError: If address is not a valid P2PK address or decoding fails
    """
    import hashlib

    # Base58 alphabet
    ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

    # Decode Base58
    num = 0
    for char in address:
        if char not in ALPHABET:
            raise ValueError(f"Invalid Base58 character: {char}")
        num = num * 58 + ALPHABET.index(char)

    # Convert to bytes (5 bytes: type + 33 pubkey + 4 checksum)
    raw = num.to_bytes(38, byteorder="big")

    # Verify checksum (last 4 bytes) - blake2b256 (32-byte digest, take first 4)
    payload = raw[:-4]
    checksum = raw[-4:]
    expected = hashlib.blake2b(payload, digest_size=32).digest()[:4]
    if checksum != expected:
        raise ValueError(f"Address checksum mismatch (expected {expected.hex()}, got {checksum.hex()})")

    # Verify P2PK type
    # First byte: networkPrefix (0x10=testnet, 0x00=mainnet) | addressType (0x01=P2PK)
    addr_type = payload[0]
    if (addr_type & 0x0F) != 0x01:
        raise ValueError(f"Address type is {addr_type:#x}, expected P2PK (0x01 or 0x11)")

    # Extract 33-byte compressed public key
    pubkey = payload[1:34]
    return pubkey.hex()


async def get_house_wallet_pubkey() -> str:
    """
    Get the house wallet's first address public key.

    Returns the compressed public key (hex) of the first wallet address.
    Falls back to a test key if the wallet is unavailable.
    """
    try:
        addresses = await _node_get("/wallet/addresses")
        if addresses and len(addresses) > 0:
            return decode_ergo_address_to_pubkey(addresses[0])
    except Exception as e:
        logger.warning("Could not get house wallet pubkey: %s", e)

    # Fallback test pubkey (for development only)
    return "02" + "00" * 32
