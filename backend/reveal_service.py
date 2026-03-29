"""
DuckPools - Reveal Transaction Builder

Builds unsigned EIP-12 reveal transactions for the coinflip contract.
The house (off-chain bot) calls this service to construct transactions
that spend commit boxes and pay winners.

Port of the frontend buildRevealTx() from coinflipService.ts to Python.

EIP-12 transaction format: https://github.com/ergoplatform/eips/blob/master/eip-0012.md

MAT-355: Implement reveal flow
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from vlq_serializer import VLQSerializer

logger = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────────────

NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")

# Contract constants (must match coinflip_v2.es compiled 2026-03-28)
COINFLIP_ERGO_TREE = os.getenv(
    "COINFLIP_ERGO_TREE",
    "19d8010c04000200020104000404040005c20105640400040004000564d805d601cdeee4c6a7040ed602e4c6a7090ed603e4c6a70704d604cdeee4c6a7050ed605c1a7eb02ea02ea027201d193cbb3720283010295937203730073017302e4c6a7060ed195939e7eb2cbb3db6902db6503fe72027303000473047203d801d606b2a5730500ed93c27206d0720492c172069d9c720573067307d801d606b2a5730800ed93c27206d0720192c172067205ea02ea02ea02d192a3e4c6a708047204d193c2b2a5730900d07204d192c1b2a5730a009972059d7205730b",
)

HOUSE_ADDRESS = os.getenv("HOUSE_ADDRESS", "")

# Ergo network constants
BASE_FEE = 1_000_000  # 0.001 ERG minimum fee


# ─── Data Classes ───────────────────────────────────────────────────


@dataclass
class CommitBoxData:
    """Represents a commit box fetched from the Ergo node."""

    box_id: str
    value: int  # nanoERG
    creation_height: int
    transaction_id: str
    index: int
    ergo_tree: str
    tokens: List[Dict[str, Any]] = field(default_factory=list)
    additional_registers: Dict[str, str] = field(default_factory=dict)

    # Decoded register values
    house_pub_key: bytes = b""
    player_pub_key: bytes = b""
    commitment_hash: bytes = b""
    player_choice: int = 0
    timeout_height: int = 0
    player_secret: bytes = b""


@dataclass
class RevealResult:
    """Result of building a reveal transaction."""

    unsigned_tx: Dict[str, Any]
    player_wins: bool
    payout_amount: int  # nanoERG
    block_hash: str
    player_address: str
    bet_amount: int  # nanoERG
    player_choice: int
    rng_hash: str


# ─── Ergo Node API Client ───────────────────────────────────────────


def _node_headers() -> Dict[str, str]:
    """Build headers for Ergo node API requests."""
    headers = {"Content-Type": "application/json"}
    if NODE_API_KEY:
        headers["api_key"] = NODE_API_KEY
    return headers


async def fetch_node_info() -> Dict[str, Any]:
    """Fetch current node info (height, etc)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{NODE_URL}/info", headers=_node_headers())
        resp.raise_for_status()
        return resp.json()


async def fetch_block_header_id(height: int) -> str:
    """Fetch the block header ID at a given height."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{NODE_URL}/blocks/at/{height}", headers=_node_headers())
        resp.raise_for_status()
        header_ids: List[str] = resp.json()
        if not header_ids:
            raise ValueError(f"No block header found at height {height}")
        return header_ids[0]


async def fetch_box_by_id(box_id: str) -> Dict[str, Any]:
    """Fetch a box by its ID from the Ergo node."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{NODE_URL}/utxo/byBoxId/{box_id}", headers=_node_headers())
        resp.raise_for_status()
        return resp.json()


async def fetch_unspent_boxes_by_tree(ergo_tree: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch unspent boxes locked by the given ergo tree."""
    encoded_tree = httpx.URL(ergo_tree)
    # Need to encode the tree for URL parameter
    import urllib.parse
    encoded = urllib.parse.quote(ergo_tree, safe="")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{NODE_URL}/utxo/boxes/unspent/{encoded}",
            params={"limit": limit, "orderBy": "creationHeight", "order": "desc"},
            headers=_node_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_wallet_unspent_boxes() -> List[Dict[str, Any]]:
    """Fetch unspent boxes from the node wallet."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{NODE_URL}/wallet/boxes/unspent",
            params={"minConfirmations": 0, "minInclusionHeight": 0},
            headers=_node_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def sign_and_broadcast_tx(unsigned_tx: Dict[str, Any]) -> Dict[str, Any]:
    """Sign an unsigned EIP-12 transaction with the node wallet and broadcast it."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Sign the transaction
        sign_resp = await client.post(
            f"{NODE_URL}/wallet/transaction/sign",
            json={"unsignedTx": unsigned_tx},
            headers=_node_headers(),
        )
        sign_resp.raise_for_status()
        signed_tx = sign_resp.json()

        # Broadcast the signed transaction
        send_resp = await client.post(
            f"{NODE_URL}/transactions",
            json=signed_tx,
            headers=_node_headers(),
        )
        send_resp.raise_for_status()
        return {"txId": send_resp.json(), "signedTx": signed_tx}


# ─── Register Decoding ──────────────────────────────────────────────


def decode_commit_box(raw_box: Dict[str, Any]) -> CommitBoxData:
    """Decode a raw box JSON from the node into a CommitBoxData with decoded registers."""
    box = CommitBoxData(
        box_id=raw_box["boxId"],
        value=int(raw_box["value"]),
        creation_height=raw_box["creationHeight"],
        transaction_id=raw_box["transactionId"],
        index=raw_box.get("index", raw_box.get("spentBy", {}).get("transactionId", "")),
        ergo_tree=raw_box.get("ergoTree", raw_box.get("address", "")),
        tokens=[
            {"tokenId": t["tokenId"], "amount": int(t["amount"])}
            for t in raw_box.get("assets", [])
        ],
        additional_registers=raw_box.get("additionalRegisters", {}),
    )

    registers = raw_box.get("additionalRegisters", {})
    if not registers:
        raise ValueError("Box has no additional registers — not a commit box")

    try:
        box.house_pub_key = VLQSerializer.deserialize_coll_byte(registers.get("R4", ""))
        box.player_pub_key = VLQSerializer.deserialize_coll_byte(registers.get("R5", ""))
        box.commitment_hash = VLQSerializer.deserialize_coll_byte(registers.get("R6", ""))
        box.player_choice = VLQSerializer.deserialize_int(registers.get("R7", ""))
        box.timeout_height = VLQSerializer.deserialize_int(registers.get("R8", ""))
        box.player_secret = VLQSerializer.deserialize_coll_byte(registers.get("R9", ""))
    except Exception as e:
        raise ValueError(f"Failed to decode commit box registers: {e}") from e

    return box


# ─── RNG Calculation ────────────────────────────────────────────────


def compute_rng(prev_block_hash: str, player_secret: bytes) -> int:
    """
    Compute the coinflip RNG result.

    Matches coinflip_v2.es:
      val blockSeed  = CONTEXT.preHeader.parentId
      val rngHash    = blake2b256(blockSeed ++ playerSecret)
      val flipResult = rngHash(0) % 2

    Args:
        prev_block_hash: Hex-encoded block header ID (32 bytes)
        player_secret: Raw player secret bytes from R9

    Returns:
        0 (heads) or 1 (tails)
    """
    block_bytes = bytes.fromhex(prev_block_hash)
    rng_input = block_bytes + player_secret
    rng_hash = hashlib.blake2b(rng_input, digest_size=32).digest()
    return rng_hash[0] % 2


# ─── EIP-12 Transaction Builder ────────────────────────────────────


def _build_box_input(
    box: CommitBoxData,
    extension: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build an EIP-12 input from a commit box.

    For the reveal, the commit box is spent by the contract script.
    We need to provide the box with its registers as context for the
    contract execution.
    """
    input_entry: Dict[str, Any] = {
        "boxId": box.box_id,
        "spendingProof": {
            "proofBytes": "",
            "extension": extension or {},
        },
    }
    return input_entry


def _build_data_input(box_id: str) -> Dict[str, Any]:
    """Build a data input reference (read-only box access)."""
    return {"boxId": box_id}


def _build_eip12_output(
    value: int,
    address: str,
    tokens: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Build an EIP-12 output box.

    Args:
        value: Box value in nanoERG
        address: Recipient P2PK/P2S address (Base58)
        tokens: Optional list of {tokenId, amount} dicts
    """
    output: Dict[str, Any] = {
        "value": str(value),
        "ergoTree": _address_to_ergo_tree(address),
        "assets": tokens or [],
        "additionalRegisters": {},
        "creationHeight": 0,  # Will be set by the builder
    }
    return output


def _address_to_ergo_tree(address: str) -> str:
    """
    Convert a Base58 P2PK address to its ergoTree hex.

    For P2PK addresses (prefix '3'), the ergoTree is:
      0008cd{33-byte-pk}

    We use the node's /addressToErgoTree endpoint or do it locally.
    """
    # Try to decode Base58 P2PK address
    try:
        # Ergo Base58 alphabet
        ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        decoded = 0
        for char in address:
            idx = ALPHABET.index(char)
            decoded = decoded * 58 + idx

        # Convert to bytes (big-endian)
        byte_length = (decoded.bit_length() + 7) // 8
        raw = decoded.to_bytes(byte_length, "big")

        # P2PK address: version byte (0x00) + 33-byte PK + 2-byte checksum
        # Ergo P2PK: content = pk_bytes, version = 0x00
        # After decoding, remove version and checksum
        if len(raw) >= 36:
            # version(1) + pubkey(33) + checksum(2) = 36
            pk_bytes = raw[1:34]
            return "0008cd" + pk_bytes.hex()
        elif len(raw) >= 34:
            # Some encodings include the version byte differently
            pk_bytes = raw[1:34]
            return "0008cd" + pk_bytes.hex()
    except Exception:
        pass

    # Fallback: return the address as-is and let the node handle it
    # This will be validated when the tx is submitted
    return ""


async def build_reveal_tx(
    box_id: str,
    house_change_address: Optional[str] = None,
) -> RevealResult:
    """
    Build an unsigned EIP-12 reveal transaction.

    This is the backend equivalent of the frontend's buildRevealTx().
    The off-chain bot calls this to construct the reveal transaction,
    then signs it with the house wallet and broadcasts it.

    Steps:
    1. Fetch the commit box from the node
    2. Decode registers (R4-R9)
    3. Fetch the previous block header for RNG seed
    4. Compute blake2b256(prevBlockHash ++ playerSecret)[0] % 2
    5. Determine outcome and payout amount
    6. Build unsigned EIP-12 transaction JSON

    Args:
        box_id: The commit box ID to reveal
        house_change_address: Address for house change outputs (defaults to HOUSE_ADDRESS)

    Returns:
        RevealResult with the unsigned tx and outcome details

    Raises:
        ValueError: If box is not a valid commit box
        httpx.HTTPError: If node API calls fail
    """
    if not HOUSE_ADDRESS:
        raise ValueError("HOUSE_ADDRESS environment variable is required")

    change_address = house_change_address or HOUSE_ADDRESS

    # 1. Fetch the commit box with full register data
    raw_box = await fetch_box_by_id(box_id)
    box = decode_commit_box(raw_box)

    logger.info(
        "reveal_decoded_box",
        box_id=box.box_id,
        value=box.value,
        player_choice=box.player_choice,
        timeout_height=box.timeout_height,
        secret_len=len(box.player_secret),
    )

    # 2. Fetch current height and previous block header for RNG
    node_info = await fetch_node_info()
    current_height = node_info.get("fullHeight", 0)
    if current_height == 0:
        raise ValueError("Node returned height 0 — is the node synced?")

    prev_block_hash = await fetch_block_header_id(current_height - 1)

    # 3. Compute RNG
    flip_result = compute_rng(prev_block_hash, box.player_secret)
    player_wins = flip_result == box.player_choice

    # 4. Calculate payout (matching coinflip_v2.es)
    bet_amount = box.value
    # winPayout = betAmount * 97 / 50 (1.94x)
    win_payout = (bet_amount * 97) // 50

    if player_wins:
        payout_amount = win_payout
        # Derive player address from their public key (R5)
        player_address = _pubkey_to_address(box.player_pub_key)
        output_address = player_address
    else:
        payout_amount = bet_amount
        output_address = HOUSE_ADDRESS

    rng_input = bytes.fromhex(prev_block_hash) + box.player_secret
    rng_hash_hex = hashlib.blake2b(rng_input, digest_size=32).hexdigest()

    logger.info(
        "reveal_outcome",
        box_id=box.box_id,
        flip_result=flip_result,
        player_choice=box.player_choice,
        player_wins=player_wins,
        payout_amount=payout_amount,
        rng_hash=rng_hash_hex[:16] + "...",
    )

    # 5. Fetch house wallet boxes for fee payment
    try:
        wallet_boxes = await fetch_wallet_unspent_boxes()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise ValueError(
                "Node wallet is locked or API key missing. "
                "Unlock wallet with: curl -X POST <NODE_URL>/wallet/unlock -d '{\"pass\":\"<pass>\"}'"
            ) from e
        raise

    if not wallet_boxes:
        raise ValueError("House wallet has no unspent boxes to pay the reveal transaction fee")

    # Select a wallet box for the fee
    fee_box = None
    fee_box_value = 0
    for wb in wallet_boxes:
        if int(wb["value"]) >= BASE_FEE:
            fee_box = wb
            fee_box_value = int(wb["value"])
            break

    if not fee_box:
        raise ValueError("No house wallet box with enough ERG to pay the fee")

    # 6. Build the unsigned EIP-12 transaction
    # Inputs: [commit_box, house_fee_box]
    inputs = [
        _build_box_input(box),
        _build_box_input(
            CommitBoxData(
                box_id=fee_box["boxId"],
                value=fee_box_value,
                creation_height=fee_box.get("creationHeight", current_height),
                transaction_id=fee_box.get("transactionId", ""),
                index=0,
                ergo_tree=fee_box.get("ergoTree", ""),
            )
        ),
    ]

    # Data inputs: [commit_box] — needed for contract to read registers
    data_inputs = [_build_data_input(box.box_id)]

    # Build payout output
    payout_tokens = []
    for t in box.tokens:
        payout_tokens.append({"tokenId": t["tokenId"], "amount": str(t["amount"])})

    outputs = [_build_eip12_output(payout_amount, output_address, payout_tokens)]

    # Build change output (house gets back fee_box_value - fee - any dust)
    fee = BASE_FEE
    change_value = fee_box_value - fee
    if change_value > 0:
        outputs.append(_build_eip12_output(change_value, change_address))

    unsigned_tx = {
        "inputs": inputs,
        "dataInputs": data_inputs,
        "outputs": outputs,
    }

    return RevealResult(
        unsigned_tx=unsigned_tx,
        player_wins=player_wins,
        payout_amount=payout_amount,
        block_hash=prev_block_hash,
        player_address=output_address if player_wins else "",
        bet_amount=bet_amount,
        player_choice=box.player_choice,
        rng_hash=rng_hash_hex,
    )


def _pubkey_to_address(pub_key: bytes) -> str:
    """
    Convert a 33-byte compressed public key to an Ergo P2PK address (Base58).

    P2PK address encoding:
    1. Prepend version byte 0x00
    2. Append 2-byte checksum (first 2 bytes of blake2b256 of version+pk)
    3. Base58 encode the result
    """
    if len(pub_key) != 33:
        raise ValueError(f"Expected 33-byte public key, got {len(pub_key)} bytes")

    # Version byte + public key
    payload = b"\x00" + pub_key

    # Checksum: first 2 bytes of blake2b256(payload)
    checksum = hashlib.blake2b(payload, digest_size=32).digest()[:2]

    # Full bytes: version + pk + checksum
    full = payload + checksum

    # Base58 encode
    return _base58_encode(full)


def _base58_encode(data: bytes) -> str:
    """Encode bytes to Base58 (Ergo alphabet)."""
    ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

    # Count leading zero bytes
    leading_zeros = 0
    for byte in data:
        if byte == 0:
            leading_zeros += 1
        else:
            break

    # Convert to integer
    num = int.from_bytes(data, "big")

    # Encode
    result = []
    while num > 0:
        num, remainder = divmod(num, 58)
        result.append(ALPHABET[remainder])

    # Add leading '1's for each leading zero byte
    result.extend(["1"] * leading_zeros)

    return "".join(reversed(result))


# ─── Pending Bet Discovery ──────────────────────────────────────────


async def get_pending_bets() -> List[CommitBoxData]:
    """
    Fetch all unspent boxes at the coinflip contract and decode them as commit boxes.

    Returns:
        List of decoded CommitBoxData for boxes that haven't been revealed yet.
    """
    boxes_raw = await fetch_unspent_boxes_by_tree(COINFLIP_ERGO_TREE)

    pending = []
    for item in boxes_raw:
        # The API returns {items: [...]} or a direct list
        items = item if isinstance(item, dict) else item
        box_list = items.get("items", [items]) if isinstance(items, dict) else [items]

    # Handle both response formats
    if isinstance(boxes_raw, dict) and "items" in boxes_raw:
        box_list = boxes_raw["items"]
    else:
        box_list = boxes_raw

    for raw_box in box_list:
        try:
            box = decode_commit_box(raw_box)
            pending.append(box)
        except (ValueError, KeyError) as e:
            logger.warning("skip_invalid_box", box_id=raw_box.get("boxId", "?"), error=str(e))
            continue

    return pending
