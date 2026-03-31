"""
DuckPools Off-Chain Bot - Ergo Box Decoder

Decodes PendingBet boxes from the Ergo node UTXO scan API into structured
data matching the coinflip_v2.es register layout.

Register layout (from coinflip_deployed.json):
  R4: Coll[Byte] — house compressed PK (33 bytes)
  R5: Coll[Byte] — player compressed PK (33 bytes)
  R6: Coll[Byte] — commitment hash blake2b256(secret||choice) (32 bytes)
  R7: Int        — player choice (0=heads, 1=tails)
  R8: Int        — timeout height (block number)
  R9: Coll[Byte] — player secret (32 random bytes)

The node API returns boxes with additional registers as SColl/SInt Sigma types.
SColl values have "values" (list of ints) and SInt has "value" (int).

MAT-419: Implement off-chain bot reveal logic
"""

from dataclasses import dataclass
from typing import List, Optional

from logger import get_logger

logger = get_logger(__name__)


@dataclass
class PendingBetBox:
    """Decoded PendingBet box with all register values."""
    box_id: str
    transaction_id: str
    ergo_tree: str
    value: int  # nanoERG
    creation_height: int
    house_pk_bytes: bytes  # R4
    player_pk_bytes: bytes  # R5
    commitment_hash: bytes  # R6
    player_choice: int  # R7: 0=heads, 1=tails
    timeout_height: int  # R8
    player_secret: bytes  # R9
    additional_tokens: list

    @property
    def player_choice_str(self) -> str:
        return "heads" if self.player_choice == 0 else "tails"

    @property
    def value_erg(self) -> float:
        return self.value / 1e9

    def __repr__(self) -> str:
        return (
            f"PendingBetBox(box_id={self.box_id[:16]}..., "
            f"choice={self.player_choice_str}, "
            f"amount={self.value_erg:.6f} ERG, "
            f"timeout_height={self.timeout_height})"
        )


def decode_coll_byte(value: dict) -> bytes:
    """
    Decode an SColl[Byte] value from the Ergo node API response.

    The node returns register values as Sigma types:
      {"type": "SColl", "valueType": "SByte", "values": [104, 101, ...]}

    For constants (compiled-in values), it may return raw hex:
      "0e02..."  (sigma-serialized hex)

    Args:
        value: The register value dict or hex string

    Returns:
        Decoded bytes
    """
    if isinstance(value, str):
        # Raw hex string — sigma-serialized
        # For SColl[Byte] with known length prefix:
        # Skip the first 2 bytes (type tag + collection tag + length encoding)
        # Try to extract raw bytes from sigma serialization
        try:
            raw = bytes.fromhex(value)
            if len(raw) < 4:
                return raw
            # Sigma serialization of Coll[Byte]: 0e <len:VLQ> <bytes>
            if raw[0] == 0x0e:
                # Decode VLQ length
                idx = 1
                length = 0
                shift = 0
                while idx < len(raw):
                    byte = raw[idx]
                    length |= (byte & 0x7F) << shift
                    idx += 1
                    if (byte & 0x80) == 0:
                        break
                    shift += 7
                return raw[idx:idx + length]
            # Fallback: return as-is (might be pre-decoded)
            return raw
        except (ValueError, IndexError):
            return b""

    if isinstance(value, dict):
        if value.get("type") == "SColl":
            values = value.get("values", [])
            return bytes(int(v) for v in values)

    if isinstance(value, list):
        return bytes(int(v) for v in value)

    if isinstance(value, bytes):
        return value

    logger.warning("decode_coll_byte_unexpected", value_type=type(value).__name__)
    return b""


def decode_int(value: dict) -> int:
    """
    Decode an SInt value from the Ergo node API response.

    The node returns: {"type": "SInt", "value": 42}
    Or for compiled constants: "0408..." (hex-encoded signed VLQ)

    Args:
        value: The register value dict, int, or hex string

    Returns:
        Decoded integer
    """
    if isinstance(value, int):
        return value

    if isinstance(value, dict):
        if value.get("type") == "SInt":
            return int(value.get("value", 0))

    if isinstance(value, str):
        try:
            # Hex-encoded sigma SInt: 04 <signed VLQ>
            raw = bytes.fromhex(value)
            if len(raw) >= 2 and raw[0] == 0x04:
                # Decode signed VLQ
                idx = 1
                result = 0
                shift = 0
                negative = False
                while idx < len(raw):
                    byte = raw[idx]
                    idx += 1
                    if shift == 0 and byte == 0x40:
                        # Negative sign byte in Ergo's VLQ
                        negative = True
                        continue
                    result |= (byte & 0x7F) << shift
                    shift += 7
                    if (byte & 0x80) == 0:
                        break
                return -result if negative else result
            # Fallback: try direct int parse
            return int(value, 16)
        except (ValueError, IndexError):
            return 0

    logger.warning("decode_int_unexpected", value_type=type(value).__name__)
    return 0


def decode_pending_bet_box(box: dict) -> Optional[PendingBetBox]:
    """
    Decode a raw Ergo node API box response into a PendingBetBox.

    Args:
        box: Raw box dict from /utxo/withUnspentBoxes or /utxo/byErgoTree

    Returns:
        PendingBetBox if decoding succeeds, None otherwise
    """
    try:
        box_id = box.get("boxId", "")
        tx_id = box.get("transactionId", "")
        ergo_tree = box.get("ergoTree", "")
        value = int(box.get("value", 0))
        creation_height = int(box.get("creationHeight", 0))
        additional_tokens = box.get("additionalTokens", [])

        # Decode registers R4-R9
        registers = box.get("additionalRegisters", {})

        r4_raw = registers.get("R4", {})
        r5_raw = registers.get("R5", {})
        r6_raw = registers.get("R6", {})
        r7_raw = registers.get("R7", {})
        r8_raw = registers.get("R8", {})
        r9_raw = registers.get("R9", {})

        house_pk_bytes = decode_coll_byte(r4_raw)
        player_pk_bytes = decode_coll_byte(r5_raw)
        commitment_hash = decode_coll_byte(r6_raw)
        player_choice = decode_int(r7_raw)
        timeout_height = decode_int(r8_raw)
        player_secret = decode_coll_byte(r9_raw)

        # Validate decoded values
        if len(house_pk_bytes) != 33:
            logger.warning(
                "invalid_house_pk_length",
                box_id=box_id,
                length=len(house_pk_bytes),
            )

        if len(player_pk_bytes) != 33:
            logger.warning(
                "invalid_player_pk_length",
                box_id=box_id,
                length=len(player_pk_bytes),
            )

        if len(commitment_hash) != 32:
            logger.warning(
                "invalid_commitment_hash_length",
                box_id=box_id,
                length=len(commitment_hash),
            )

        if player_choice not in (0, 1):
            logger.warning(
                "invalid_player_choice",
                box_id=box_id,
                choice=player_choice,
            )

        if timeout_height <= 0:
            logger.warning(
                "invalid_timeout_height",
                box_id=box_id,
                timeout=timeout_height,
            )

        decoded = PendingBetBox(
            box_id=box_id,
            transaction_id=tx_id,
            ergo_tree=ergo_tree,
            value=value,
            creation_height=creation_height,
            house_pk_bytes=house_pk_bytes,
            player_pk_bytes=player_pk_bytes,
            commitment_hash=commitment_hash,
            player_choice=player_choice,
            timeout_height=timeout_height,
            player_secret=player_secret,
            additional_tokens=additional_tokens,
        )

        logger.debug("box_decoded", box=repr(decoded))
        return decoded

    except Exception as e:
        logger.error("box_decode_error", error=str(e), exc_info=True)
        return None


def decode_pending_bet_boxes(raw_boxes: List[dict]) -> List[PendingBetBox]:
    """
    Decode a list of raw box dicts into PendingBetBox objects.

    Args:
        raw_boxes: List of raw box dicts from node API

    Returns:
        List of successfully decoded PendingBetBox objects
    """
    decoded = []
    failed = 0

    for box in raw_boxes:
        result = decode_pending_bet_box(box)
        if result:
            decoded.append(result)
        else:
            failed += 1

    if failed > 0:
        logger.warning(
            "box_decode_failures",
            total=len(raw_boxes),
            failed=failed,
            succeeded=len(decoded),
        )

    return decoded
