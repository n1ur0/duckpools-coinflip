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
    Decode a Coll[Byte] value from node's serialized format.
    Returns the raw hex string of the byte array.
    """
    raw = bytes.fromhex(serialized_hex)
    if len(raw) < 2:
        return serialized_hex
    # First byte is the type tag (0x04 = SByte for Coll[Byte] elements)
    # Rest is the raw byte array
    return raw[1:].hex()


def decode_int_from_node(serialized_hex: str) -> int:
    """
    Decode an integer from node's VLQ serialized format.
    """
    raw = bytes.fromhex(serialized_hex)
    if not raw:
        return 0

    # Check sign bit in last byte
    last = raw[-1]
    negative = bool(last & 0x40)

    # Extract value bytes (mask out sign bit in last, continuation bits in others)
    value = 0
    for b in raw:
        value = (value << 7) | (b & 0x7F)

    if negative:
        value = -value

    return value


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
    secret_bytes = bytes.fromhex(secret_hex)
    return _compute_rng(block_hash_hex, secret_bytes)


def verify_commitment(secret_hex: str, choice: int, commitment_hex: str) -> bool:
    """
    Verify that commitment = blake2b256(secret || choice_byte).
    Delegates to rng_module.verify_commit for single source of truth.
    Matches on-chain: blake2b256(playerSecret ++ Coll(choiceByte)) == commitmentHash
    """
    from rng_module import verify_commit as _verify_commit
    secret_bytes = bytes.fromhex(secret_hex)
    return _verify_commit(commitment_hex, secret_bytes, choice)


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
