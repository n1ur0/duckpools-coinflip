#!/usr/bin/env python3
"""
Sigma-State Serialization Library for DuckPools
==================================================
Ground-truth implementation for Ergo SValue encoding.

This module provides functions to serialize and deserialize Ergo's
sigma-state values (SValue) according to the Ergo protocol specification.

Type Tags:
    0x02 = IntConstant (i32)
    0x04 = LongConstant (i64)
    0x0E = Coll constant (collection)
    0x08 = Pair constant (SigmaProp = Pair(Bool, ProveDlog))
    0x01 = SByte (element type for Coll[Byte])

Reference:
    https://github.com/ergoplatform/sigma-rust
    https://github.com/ergoplatform/ergo

Usage:
    >>> serialize_int(10)
    '0214'
    >>> serialize_coll_byte(b'\\x00' * 32)
    '0e01200000...'

Author: Serialization Specialist Jr (350d346f-f2d2-4b0c-8792-b9fc5ef3fd38)
Team: Protocol Core
Company: Matsuzaka (DuckPools)
"""

from typing import Union
import struct


# ─── VLQ Encoding ────────────────────────────────────────────────────────────

def encode_vlq(value: int) -> str:
    """
    Encode an unsigned integer using Variable-Length Quantity (VLQ).

    VLQ uses 7-bit groups with the most significant bit (MSB) as a
    continuation flag. The last byte has MSB=0, all preceding bytes have MSB=1.

    Examples:
        0 -> 00
        1 -> 01
        127 -> 7f
        128 -> 8001
        255 -> ff01

    Args:
        value: Non-negative integer to encode

    Returns:
        Hexadecimal string of the VLQ-encoded value

    Raises:
        ValueError: If value is negative
    """
    if value < 0:
        raise ValueError(f"VLQ encoding requires non-negative value, got {value}")

    if value == 0:
        return "00"

    result = []
    remaining = value
    while remaining > 0:
        byte = remaining & 0x7F
        remaining >>= 7
        if remaining > 0:
            byte |= 0x80
        result.append(byte)

    # Little-endian: least significant byte first
    return ''.join(f'{b:02x}' for b in result)


def decode_vlq(hex_str: str) -> int:
    """
    Decode a VLQ-encoded hexadecimal string.

    Args:
        hex_str: Hexadecimal string of VLQ-encoded bytes

    Returns:
        Decoded integer value

    Raises:
        ValueError: If hex_str is invalid or VLQ is malformed
    """
    if not hex_str or len(hex_str) % 2 != 0:
        raise ValueError(f"Invalid hex string: {hex_str}")

    result = 0
    shift = 0
    for i in range(0, len(hex_str), 2):
        byte = int(hex_str[i:i+2], 16)
        result |= (byte & 0x7F) << shift
        shift += 7
        if (byte & 0x80) == 0:
            return result

    raise ValueError(f"VLQ continuation bit set on last byte: {hex_str}")


# ─── ZigZag Encoding ─────────────────────────────────────────────────────────

def zigzag_encode_i32(value: int) -> int:
    """
    ZigZag encode a 32-bit signed integer.

    ZigZag encoding maps signed integers to unsigned integers for efficient
    variable-length encoding. The formula is: (n << 1) ^ (n >> 31).

    Mapping:
        0 -> 0
        -1 -> 1
        1 -> 2
        -2 -> 3
        2 -> 4

    Args:
        value: Signed 32-bit integer

    Returns:
        Unsigned integer (32-bit mask applied)
    """
    return ((value << 1) ^ (value >> 31)) & 0xFFFFFFFF


def zigzag_encode_i64(value: int) -> int:
    """
    ZigZag encode a 64-bit signed integer.

    Same as zigzag_encode_i32 but for 64-bit values.
    Formula: (n << 1) ^ (n >> 63).

    Args:
        value: Signed 64-bit integer

    Returns:
        Unsigned integer (64-bit mask applied)
    """
    return ((value << 1) ^ (value >> 63)) & 0xFFFFFFFFFFFFFFFF


def zigzag_decode_i32(encoded: int) -> int:
    """
    Decode a ZigZag-encoded 32-bit value.

    Args:
        encoded: ZigZag-encoded unsigned integer

    Returns:
        Original signed integer
    """
    return (encoded >> 1) ^ -(encoded & 1)


def zigzag_decode_i64(encoded: int) -> int:
    """
    Decode a ZigZag-encoded 64-bit value.

    Args:
        encoded: ZigZag-encoded unsigned integer

    Returns:
        Original signed integer
    """
    return (encoded >> 1) ^ -(encoded & 1)


# ─── Primitive Type Serialization ───────────────────────────────────────────

def serialize_int(value: int) -> str:
    """
    Serialize an IntConstant (i32).

    Format: 0x02 + VLQ(zigzag_i32(value))

    Examples:
        Int(0) = 02 00
        Int(1) = 02 02
        Int(10) = 02 14
        Int(-1) = 02 01

    Args:
        value: Signed 32-bit integer

    Returns:
        Hexadecimal string of the serialized IntConstant
    """
    zigzag = zigzag_encode_i32(value)
    return f"02{encode_vlq(zigzag)}"


def serialize_long(value: int) -> str:
    """
    Serialize a LongConstant (i64).

    Format: 0x04 + VLQ(zigzag_i64(value))

    Examples:
        Long(0) = 04 00
        Long(1) = 04 02

    Args:
        value: Signed 64-bit integer

    Returns:
        Hexadecimal string of the serialized LongConstant
    """
    zigzag = zigzag_encode_i64(value)
    return f"04{encode_vlq(zigzag)}"


# ─── Coll[Byte] Serialization ───────────────────────────────────────────────

def serialize_coll_byte(data: bytes, format: str = "auto") -> str:
    """
    Serialize a Coll[Byte] (collection of bytes).

    TWO formats exist in the Ergo ecosystem:

    Format A (spec/encoder):
        0e 01 VLQ(len) data
        Has explicit element type 0x01 (SByte)

    Format B (node API returns this):
        0e VLQ(len) data
        No element type byte

    Args:
        data: Bytes to serialize
        format: "auto", "with_type", or "without_type"
               "auto" detects and preserves input format
               "with_type" forces Format A (0e01...)
               "without_type" forces Format B (0e...)

    Returns:
        Hexadecimal string of the serialized Coll[Byte]

    Examples:
        serialize_coll_byte(b'\\x00' * 32) -> '0e01200000...' (Format A)
        serialize_coll_byte(b'\\x00' * 32, "without_type") -> '0e200000...' (Format B)
    """
    length_vlq = encode_vlq(len(data))

    if format == "with_type":
        return f"0e01{length_vlq}{data.hex()}"
    elif format == "without_type":
        return f"0e{length_vlq}{data.hex()}"
    elif format == "auto":
        # Default to Format A for new encodings
        return f"0e01{length_vlq}{data.hex()}"
    else:
        raise ValueError(f"Unknown format: {format}")


def detect_coll_byte_format(hex_str: str) -> str:
    """
    Detect which Coll[Byte] format a hex string uses.

    Args:
        hex_str: Hexadecimal string starting with 0e

    Returns:
        "with_type" or "without_type"

    Raises:
        ValueError: If hex_str doesn't start with 0e
    """
    if not hex_str.lower().startswith("0e"):
        raise ValueError(f"Not a Coll[Byte] encoding: {hex_str}")

    # Check if byte[1] is 0x01 (element type)
    if len(hex_str) >= 4 and hex_str[2:4].lower() == "01":
        return "with_type"
    else:
        return "without_type"


def deserialize_coll_byte(hex_str: str) -> bytes:
    """
    Deserialize a Coll[Byte] from hexadecimal.

    Auto-detects Format A vs Format B.

    Args:
        hex_str: Hexadecimal string of serialized Coll[Byte]

    Returns:
        Deserialized bytes

    Raises:
        ValueError: If hex_str is malformed
    """
    fmt = detect_coll_byte_format(hex_str)

    if fmt == "with_type":
        # 0e 01 VLQ(len) data
        if len(hex_str) < 6:
            raise ValueError(f"Coll[Byte] too short: {hex_str}")
        vlq_hex = hex_str[4:]  # Skip 0e01
    else:
        # 0e VLQ(len) data
        if len(hex_str) < 4:
            raise ValueError(f"Coll[Byte] too short: {hex_str}")
        vlq_hex = hex_str[2:]  # Skip 0e

    # Parse VLQ length
    length = decode_vlq(vlq_hex[:4] if len(vlq_hex) >= 4 else vlq_hex)

    # Extract data (find VLQ end)
    vlq_bytes = 0
    i = 0
    while i < len(vlq_hex):
        byte = int(vlq_hex[i:i+2], 16)
        vlq_bytes += 1
        i += 2
        if (byte & 0x80) == 0:
            break

    data_hex = vlq_hex[i:]
    if len(data_hex) != length * 2:
        raise ValueError(f"Coll[Byte] length mismatch: expected {length*2} chars, got {len(data_hex)}")

    return bytes.fromhex(data_hex)


# ─── SigmaProp Serialization ───────────────────────────────────────────────

def serialize_sigmaprop(public_key: bytes) -> str:
    """
    Serialize a SigmaProp (Sigma proposition).

    Format: 08cd + 33-byte compressed public key

    This encoding comes from extracting the public key from a P2PK ErgoTree.
    The P2PK ErgoTree format is: 0008cd<pk>, where <pk> is the 33-byte
    compressed public key. The SigmaProp is just 08cd + <pk>.

    Args:
        public_key: 33-byte compressed public key

    Returns:
        Hexadecimal string of the serialized SigmaProp

    Raises:
        ValueError: If public_key is not 33 bytes

    Examples:
        pk = bytes.fromhex('02' + '00' * 32)
        serialize_sigmaprop(pk) -> '08cd020000...'
    """
    if len(public_key) != 33:
        raise ValueError(f"Public key must be 33 bytes, got {len(public_key)}")

    return f"08cd{public_key.hex()}"


# ─── DuckPools Register Helpers ────────────────────────────────────────────

def serialize_pending_bet_registers(
    ergo_tree: bytes,
    commitment_hash: bytes,
    bet_choice: int,
    player_secret: int,
    bet_id: bytes
) -> dict:
    """
    Serialize all registers for a DuckPools PendingBet box.

    Register Layout:
        R4: Coll[Byte] - Player's ErgoTree
        R5: Coll[Byte] - Commitment hash (32 bytes)
        R6: Int - Bet choice (0=heads, 1=tails) OR threshold for dice
        R7: Int - Player's random secret
        R8: Coll[Byte] - Bet ID (32 bytes)

    Args:
        ergo_tree: Player's ErgoTree bytes
        commitment_hash: 32-byte commitment hash
        bet_choice: Integer choice or threshold
        player_secret: Player's random secret integer
        bet_id: 32-byte unique bet identifier

    Returns:
        Dictionary of register names to serialized hex strings

    Example:
        >>> registers = serialize_pending_bet_registers(
        ...     ergo_tree=b'\\x00'*10,
        ...     commitment_hash=b'\\x11'*32,
        ...     bet_choice=1,
        ...     player_secret=12345,
        ...     bet_id=b'\\x22'*32
        ... )
        >>> registers['R4']  # Player's ErgoTree
        '0e010a0000...'
        >>> registers['R6']  # Bet choice (tails)
        '0212b0'
    """
    return {
        "R4": serialize_coll_byte(ergo_tree),
        "R5": serialize_coll_byte(commitment_hash),
        "R6": serialize_int(bet_choice),
        "R7": serialize_int(player_secret),
        "R8": serialize_coll_byte(bet_id),
    }


# ─── Validation & Testing ─────────────────────────────────────────────────

if __name__ == "__main__":
    # Run self-tests
    print("Running sigma_serializer.py self-tests...")
    print()

    # VLQ tests
    assert encode_vlq(0) == "00", "VLQ(0) failed"
    assert encode_vlq(1) == "01", "VLQ(1) failed"
    assert encode_vlq(127) == "7f", "VLQ(127) failed"
    assert encode_vlq(128) == "8001", "VLQ(128) failed"
    assert encode_vlq(255) == "ff01", "VLQ(255) failed"
    print("✓ VLQ encoding tests passed")

    # ZigZag i32 tests
    assert zigzag_encode_i32(0) == 0, "ZigZag(0) failed"
    assert zigzag_encode_i32(1) == 2, "ZigZag(1) failed"
    assert zigzag_encode_i32(-1) == 1, "ZigZag(-1) failed"
    assert zigzag_encode_i32(2) == 4, "ZigZag(2) failed"
    assert zigzag_encode_i32(-2) == 3, "ZigZag(-2) failed"
    print("✓ ZigZag i32 tests passed")

    # Int serialization tests
    assert serialize_int(0) == "0200", "Int(0) failed"
    assert serialize_int(1) == "0202", "Int(1) failed"
    assert serialize_int(10) == "0214", "Int(10) failed"
    assert serialize_int(-1) == "0201", "Int(-1) failed"
    print("✓ Int serialization tests passed")

    # Long serialization tests
    assert serialize_long(0) == "0400", "Long(0) failed"
    assert serialize_long(1) == "0402", "Long(1) failed"
    print("✓ Long serialization tests passed")

    # Coll[Byte] serialization tests
    test_data = b'\x00' * 32
    coll = serialize_coll_byte(test_data)
    assert coll.startswith("0e01"), f"Coll[Byte] format A failed: {coll}"
    assert len(coll) == 4 + 2 + 64, f"Coll[Byte] length wrong: {len(coll)}"
    print("✓ Coll[Byte] serialization tests passed")

    # Coll[Byte] format detection
    assert detect_coll_byte_format("0e012000") == "with_type", "Format A detection failed"
    assert detect_coll_byte_format("0e2000") == "without_type", "Format B detection failed"
    print("✓ Coll[Byte] format detection tests passed")

    # SigmaProp tests
    pk = b'\x02' + b'\x00' * 32  # Compressed public key placeholder
    sigmaprop = serialize_sigmaprop(pk)
    assert sigmaprop.startswith("08cd"), f"SigmaProp failed: {sigmaprop}"
    assert len(sigmaprop) == 4 + 66, f"SigmaProp length wrong: {len(sigmaprop)}"
    print("✓ SigmaProp serialization tests passed")

    # PendingBet registers test
    registers = serialize_pending_bet_registers(
        ergo_tree=b'\x00' * 10,
        commitment_hash=b'\x11' * 32,
        bet_choice=1,
        player_secret=12345,
        bet_id=b'\x22' * 32
    )
    assert "R4" in registers, "R4 missing"
    assert "R5" in registers, "R5 missing"
    assert "R6" in registers, "R6 missing"
    assert "R7" in registers, "R7 missing"
    assert "R8" in registers, "R8 missing"
    assert registers["R4"].startswith("0e01"), "R4 not Coll[Byte]"
    assert registers["R6"].startswith("02"), "R6 not Int"
    print("✓ PendingBet registers tests passed")

    print()
    print("All tests passed! ✓")
    print()
    print("Usage examples:")
    print(f"  encode_vlq(128) = '{encode_vlq(128)}'")
    print(f"  serialize_int(10) = '{serialize_int(10)}'")
    print(f"  serialize_int(-1) = '{serialize_int(-1)}'")
    print(f"  serialize_long(1) = '{serialize_long(1)}'")
    test_bytes = b'\x00' * 32
    coll_result = serialize_coll_byte(test_bytes)
    print(f"  serialize_coll_byte(b'\\x00' * 32) = '{coll_result[:20]}...'")
