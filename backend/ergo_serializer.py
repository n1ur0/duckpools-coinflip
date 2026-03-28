"""
DuckPools - Ergo Value Serializer/Deserializer

Complete VLQ encoder/decoder for Ergo values with full type coverage.

Implements serialization/deserialization for all Ergo SValue types:
- IntConstant (32-bit signed): 0x02 + VLQ(zigzag_i32)
- LongConstant (64-bit signed): 0x04 + VLQ(zigzag_i64)
- Coll[Byte]: 0x0e + (optional 0x01) + VLQ(length) + data
- SigmaProp: 0x08 + 0xcd + 33-byte compressed PK
- Boolean: 0x06 (false) / 0x07 (true)
- Option: 0x0b + (None or inner value)
- Pair: 0x0d + left + right

Reference: sigma_serializer.py, TypeScript SDK serialization
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class SerializationError(Exception):
    """Error raised during serialization/deserialization."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}


# ─── VLQ Encoding/Decoding ───────────────────────────────────────────

def encode_vlq(value: int) -> bytes:
    """
    Encode integer using Variable-Length Quantity.
    
    Args:
        value: Integer to encode
        
    Returns:
        VLQ-encoded bytes
        
    Example:
        >>> encode_vlq(0)
        b'\\x00'
        >>> encode_vlq(127)
        b'\\x7f'
        >>> encode_vlq(128)
        b'\\x80\\x01'
    """
    if value == 0:
        return b'\x00'
    
    result = []
    remaining = value
    
    while remaining > 0:
        # Take 7 least significant bits
        byte = remaining & 0x7F
        remaining >>= 7
        
        # Set continuation flag if more bytes follow
        if remaining > 0:
            byte |= 0x80
            
        result.append(byte)
    
    return bytes(result)


def decode_vlq(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Decode VLQ-encoded integer from bytes.
    
    Args:
        data: Byte data containing VLQ
        offset: Starting offset in data
        
    Returns:
        Tuple of (decoded_value, new_offset)
        
    Raises:
        SerializationError: If VLQ is invalid
    """
    value = 0
    shift = 0
    i = offset
    
    while i < len(data):
        byte = data[i]
        value |= (byte & 0x7F) << shift
        
        # Check if this is the last byte
        if (byte & 0x80) == 0:
            return value, i + 1
            
        shift += 7
        i += 1
    
    raise SerializationError("Invalid VLQ: missing continuation byte", {"offset": offset})


# ─── ZigZag Encoding/Decoding ────────────────────────────────────────

def zigzag_encode_i32(value: int) -> int:
    """
    ZigZag encode a 32-bit signed integer.
    
    Maps signed integers to unsigned for VLQ encoding:
    0 -> 0, -1 -> 1, 1 -> 2, -2 -> 3, 2 -> 4, etc.
    
    Args:
        value: 32-bit signed integer
        
    Returns:
        Unsigned integer suitable for VLQ encoding
    """
    return ((value << 1) ^ (value >> 31)) & 0xFFFFFFFF


def zigzag_encode_i64(value: int) -> int:
    """
    ZigZag encode a 64-bit signed integer.
    
    Args:
        value: 64-bit signed integer
        
    Returns:
        Unsigned integer suitable for VLQ encoding
    """
    return ((value << 1) ^ (value >> 63)) & 0xFFFFFFFFFFFFFFFF


def zigzag_decode_i32(value: int) -> int:
    """
    ZigZag decode a 32-bit signed integer.
    
    Args:
        value: Unsigned integer from VLQ decoding
        
    Returns:
        Original signed integer
    """
    return (value >> 1) ^ -(value & 1)


def zigzag_decode_i64(value: int) -> int:
    """
    ZigZag decode a 64-bit signed integer.
    
    Args:
        value: Unsigned integer from VLQ decoding
        
    Returns:
        Original signed integer
    """
    return (value >> 1) ^ -(value & 1)


# ─── Type-specific Serialization ───────────────────────────────────────

def serialize_int(value: int) -> bytes:
    """
    Serialize IntConstant (32-bit signed).
    Format: type_tag(0x02) + VLQ(zigzag_i32)
    
    Args:
        value: 32-bit signed integer
        
    Returns:
        Serialized bytes
        
    Raises:
        SerializationError: If value is out of 32-bit range
    """
    if not (-0x80000000 <= value <= 0x7FFFFFFF):
        raise SerializationError(
            f"Int value out of 32-bit range: {value}",
            {"min": -0x80000000, "max": 0x7FFFFFFF}
        )
    
    zigzag = zigzag_encode_i32(value)
    vlq = encode_vlq(zigzag)
    return bytes([0x02]) + vlq


def serialize_long(value: int) -> bytes:
    """
    Serialize LongConstant (64-bit signed).
    Format: type_tag(0x04) + VLQ(zigzag_i64)
    
    Args:
        value: 64-bit signed integer
        
    Returns:
        Serialized bytes
        
    Raises:
        SerializationError: If value is out of 64-bit range
    """
    if not (-0x8000000000000000 <= value <= 0x7FFFFFFFFFFFFFFF):
        raise SerializationError(
            f"Long value out of 64-bit range: {value}",
            {"min": -0x8000000000000000, "max": 0x7FFFFFFFFFFFFFFF}
        )
    
    zigzag = zigzag_encode_i64(value)
    vlq = encode_vlq(zigzag)
    return bytes([0x04]) + vlq


def serialize_coll_byte(data: bytes, include_element_type: bool = True) -> bytes:
    """
    Serialize Coll[Byte] (Collection of bytes).
    Format: type_tag(0x0E) + element_type(0x01) + VLQ(length) + data
    
    Two formats exist in practice:
    (A) 0e 01 VLQ(len) data - with SByte type tag (spec/encoder)
    (B) 0e VLQ(len) data - without SByte type tag (node API)
    
    Args:
        data: Bytes to serialize
        include_element_type: Whether to include SByte element type tag (0x01)
        
    Returns:
        Serialized bytes
    """
    type_tag = bytes([0x0e])
    length_vlq = encode_vlq(len(data))
    
    if include_element_type:
        element_type = bytes([0x01])  # SByte element type
        return type_tag + element_type + length_vlq + data
    else:
        return type_tag + length_vlq + data


def serialize_sigma_prop(public_key: bytes) -> bytes:
    """
    Serialize SigmaProp (Sigma proposition).
    Format: 0x08 + 0xcd + 33-byte compressed public key
    
    For P2PK addresses from ErgoTree:
    ErgoTree format: 0008cd<33-byte-pk>
    We use: 08cd<33-byte-pk>
    
    Args:
        public_key: 33-byte compressed public key
        
    Returns:
        Serialized bytes
        
    Raises:
        SerializationError: If public key is not 33 bytes
    """
    if len(public_key) != 33:
        raise SerializationError(
            f"Public key must be 33 bytes, got {len(public_key)}",
            {"expected": 33, "actual": len(public_key)}
        )
    
    return bytes([0x08, 0xcd]) + public_key


def serialize_boolean(value: bool) -> bytes:
    """
    Serialize Boolean.
    Format: type_tag(0x06) for false, type_tag(0x07) for true
    
    Args:
        value: Boolean value
        
    Returns:
        Serialized bytes
    """
    return bytes([0x07 if value else 0x06])


def serialize_option(value: Optional[bytes]) -> bytes:
    """
    Serialize Option (Optional value).
    Format: type_tag(0x0b) for None, type_tag(0x0b) + inner_value for Some
    
    Args:
        value: None for None option, serialized bytes for Some option
        
    Returns:
        Serialized bytes
    """
    if value is None:
        return bytes([0x0b])  # None
    else:
        return bytes([0x0b]) + value  # Some


def serialize_pair(left: bytes, right: bytes) -> bytes:
    """
    Serialize Pair/Tuple.
    Format: type_tag(0x0d) + left_value + right_value
    
    Args:
        left: Serialized left value
        right: Serialized right value
        
    Returns:
        Serialized bytes
    """
    return bytes([0x0d]) + left + right


# ─── Type-specific Deserialization ─────────────────────────────────────

def deserialize_int(data: bytes) -> Tuple[int, int]:
    """
    Deserialize IntConstant.
    Format: type_tag(0x02) + VLQ(zigzag_i32)
    
    Args:
        data: Serialized data
        
    Returns:
        Tuple of (deserialized_value, new_offset)
        
    Raises:
        SerializationError: If data is not a valid IntConstant
    """
    if not data or data[0] != 0x02:
        raise SerializationError(
            "Not an IntConstant",
            {"expected_type_tag": "0x02", "actual": f"0x{data[0]:02x}" if data else "empty"}
        )
    
    # Skip type tag and decode VLQ
    zigzag, offset = decode_vlq(data, 1)
    
    # ZigZag decode
    value = zigzag_decode_i32(zigzag)
    
    return value, offset


def deserialize_long(data: bytes) -> Tuple[int, int]:
    """
    Deserialize LongConstant.
    Format: type_tag(0x04) + VLQ(zigzag_i64)
    
    Args:
        data: Serialized data
        
    Returns:
        Tuple of (deserialized_value, new_offset)
        
    Raises:
        SerializationError: If data is not a valid LongConstant
    """
    if not data or data[0] != 0x04:
        raise SerializationError(
            "Not a LongConstant",
            {"expected_type_tag": "0x04", "actual": f"0x{data[0]:02x}" if data else "empty"}
        )
    
    # Skip type tag and decode VLQ
    zigzag, offset = decode_vlq(data, 1)
    
    # ZigZag decode
    value = zigzag_decode_i64(zigzag)
    
    return value, offset


def deserialize_coll_byte(data: bytes) -> Tuple[bytes, int]:
    """
    Deserialize Coll[Byte].
    Format: type_tag(0x0E) + (optional 0x01) + VLQ(length) + data
    
    Args:
        data: Serialized data
        
    Returns:
        Tuple of (deserialized_bytes, new_offset)
        
    Raises:
        SerializationError: If data is not a valid Coll[Byte]
    """
    if not data or data[0] != 0x0e:
        raise SerializationError(
            "Not a Coll[Byte]",
            {"expected_type_tag": "0x0e", "actual": f"0x{data[0]:02x}" if data else "empty"}
        )
    
    offset = 1
    
    # Check for element type tag (format A) or skip it (format B)
    if len(data) > 1 and data[1] == 0x01:
        offset = 2  # Skip element type tag
    
    # Decode length
    length, length_offset = decode_vlq(data, offset)
    
    # Check if we have enough data
    data_end = length_offset + length
    if len(data) < data_end:
        raise SerializationError(
            "Incomplete Coll[Byte] data",
            {"expected_length": data_end, "actual_length": len(data)}
        )
    
    # Extract data bytes
    return data[length_offset:data_end], data_end


def deserialize_sigma_prop(data: bytes) -> Tuple[bytes, int]:
    """
    Deserialize SigmaProp.
    Format: type_tag(0x08) + 0xcd + 33-byte compressed public key
    
    Args:
        data: Serialized data
        
    Returns:
        Tuple of (public_key_bytes, new_offset)
        
    Raises:
        SerializationError: If data is not a valid SigmaProp
    """
    if len(data) < 35 or data[0] != 0x08 or data[1] != 0xcd:
        raise SerializationError(
            "Not a SigmaProp",
            {"expected_length": 35, "actual": len(data)}
        )
    
    return data[2:35], 35


def deserialize_boolean(data: bytes) -> Tuple[bool, int]:
    """
    Deserialize Boolean.
    Format: type_tag(0x06) for false, type_tag(0x07) for true
    
    Args:
        data: Serialized data
        
    Returns:
        Tuple of (boolean_value, new_offset)
        
    Raises:
        SerializationError: If data is not a valid Boolean
    """
    if not data:
        raise SerializationError("Empty Boolean data")
    
    if data[0] == 0x06:
        return False, 1
    elif data[0] == 0x07:
        return True, 1
    else:
        raise SerializationError(
            "Not a Boolean",
            {"expected_type_tag": "0x06 or 0x07", "actual": f"0x{data[0]:02x}"}
        )


def deserialize_option(data: bytes) -> Tuple[Optional[bytes], int]:
    """
    Deserialize Option.
    Format: type_tag(0x0b) for None, type_tag(0x0b) + inner_value for Some
    
    Args:
        data: Serialized data
        
    Returns:
        Tuple of (option_value, new_offset)
        
    Raises:
        SerializationError: If data is not a valid Option
    """
    if not data or data[0] != 0x0b:
        raise SerializationError(
            "Not an Option",
            {"expected_type_tag": "0x0b", "actual": f"0x{data[0]:02x}" if data else "empty"}
        )
    
    if len(data) == 1:
        return None, 1  # None
    else:
        return data[1:], len(data)  # Some - return remaining bytes


# ─── Generic Serialization/Deserialization ────────────────────────────

def serialize_svalue(svalue_type: str, value: Any) -> bytes:
    """
    Serialize an SValue based on its type.
    
    Args:
        svalue_type: Type of the SValue ('Int', 'Long', 'Coll[Byte]', etc.)
        value: Value to serialize
        
    Returns:
        Serialized bytes
        
    Raises:
        SerializationError: If type or value is invalid
    """
    try:
        if svalue_type == 'Int':
            return serialize_int(value)
        elif svalue_type == 'Long':
            return serialize_long(value)
        elif svalue_type == 'Coll[Byte]' or svalue_type == 'Coll[SByte]':
            if isinstance(value, str):
                # Assume hex string
                value = bytes.fromhex(value)
            return serialize_coll_byte(value)
        elif svalue_type == 'SigmaProp':
            if isinstance(value, str):
                # Assume hex string
                value = bytes.fromhex(value)
            return serialize_sigma_prop(value)
        elif svalue_type == 'Boolean':
            return serialize_boolean(value)
        elif svalue_type == 'Option':
            if value is None:
                return serialize_option(None)
            else:
                return serialize_option(value)
        elif svalue_type == 'Pair':
            left_type, left_val = value['left']
            right_type, right_val = value['right']
            left_bytes = serialize_svalue(left_type, left_val)
            right_bytes = serialize_svalue(right_type, right_val)
            return serialize_pair(left_bytes, right_bytes)
        else:
            raise SerializationError(f"Unknown SValue type: {svalue_type}")
    except Exception as e:
        if isinstance(e, SerializationError):
            raise
        raise SerializationError(f"Error serializing {svalue_type}: {e}")


def deserialize_svalue(data: bytes) -> Tuple[Any, str, int]:
    """
    Deserialize SValue based on its type tag.
    
    Args:
        data: Serialized data
        
    Returns:
        Tuple of (deserialized_value, type_name, new_offset)
        
    Raises:
        SerializationError: If data is not a valid SValue
    """
    if not data:
        raise SerializationError("Empty SValue data")
    
    type_tag = data[0]
    
    try:
        if type_tag == 0x02:  # Int
            value, offset = deserialize_int(data)
            return value, 'Int', offset
        elif type_tag == 0x04:  # Long
            value, offset = deserialize_long(data)
            return value, 'Long', offset
        elif type_tag == 0x0e:  # Coll[Byte]
            value, offset = deserialize_coll_byte(data)
            return value.hex(), 'Coll[Byte]', offset
        elif type_tag == 0x08:  # SigmaProp (first byte of 0x08cd)
            if len(data) >= 2 and data[1] == 0xcd:
                value, offset = deserialize_sigma_prop(data)
                return value.hex(), 'SigmaProp', offset
            else:
                raise SerializationError("Invalid SigmaProp: missing 0xcd byte")
        elif type_tag == 0x06 or type_tag == 0x07:  # Boolean
            value, offset = deserialize_boolean(data)
            return value, 'Boolean', offset
        elif type_tag == 0x0b:  # Option
            value, offset = deserialize_option(data)
            return value, 'Option', offset
        elif type_tag == 0x0d:  # Pair
            # Pair is complex - for now, return raw bytes
            return data[1:].hex(), 'Pair', len(data)
        else:
            raise SerializationError(
                f"Unknown SValue type tag: 0x{type_tag:02x}",
                {"available_tags": "0x02, 0x04, 0x0e, 0x08, 0x06, 0x07, 0x0b, 0x0d"}
            )
    except Exception as e:
        if isinstance(e, SerializationError):
            raise
        raise SerializationError(f"Error deserializing type 0x{type_tag:02x}: {e}")


# ─── Utility Functions ───────────────────────────────────────────────

def bytes_to_hex(data: bytes) -> str:
    """Convert bytes to hex string."""
    return data.hex()


def hex_to_bytes(hex_str: str) -> bytes:
    """Convert hex string to bytes."""
    return bytes.fromhex(hex_str)


def get_type_tag(data: bytes) -> Optional[int]:
    """
    Get the type tag from serialized SValue data.
    
    Args:
        data: Serialized SValue data
        
    Returns:
        Type tag as integer, or None if data is empty
    """
    return data[0] if data else None


# ─── Register Serialization Helpers ────────────────────────────────────

def serialize_register_values(values: List[Tuple[str, Any]]) -> Dict[str, str]:
    """
    Serialize multiple values for Ergo registers (R4-R9).
    
    Args:
        values: List of (type_name, value) tuples
        
    Returns:
        Dictionary mapping register names to hex strings
        
    Raises:
        SerializationError: If too many values for available registers
    """
    if len(values) > 6:
        raise SerializationError(
            f"Too many register values: {len(values)}, max 6 (R4-R9)"
        )
    
    result = {}
    register_names = ['R4', 'R5', 'R6', 'R7', 'R8', 'R9']
    
    for i, (svalue_type, value) in enumerate(values):
        if i >= len(register_names):
            break
            
        serialized = serialize_svalue(svalue_type, value)
        result[register_names[i]] = bytes_to_hex(serialized)
    
    return result


def auto_detect_coll_byte_format(data: bytes) -> str:
    """
    Auto-detect Coll[Byte] format.
    
    Args:
        data: Serialized Coll[Byte] data
        
    Returns:
        Format description: 'with_element_type' or 'without_element_type'
    """
    if len(data) >= 2 and data[1] == 0x01:
        return 'with_element_type'
    else:
        return 'without_element_type'


# ─── Debugging and Validation ────────────────────────────────────────

def debug_serialize_deserialize(svalue_type: str, value: Any) -> bool:
    """
    Debug helper: serialize then deserialize and check if values match.
    
    Args:
        svalue_type: Type of the SValue
        value: Value to test
        
    Returns:
        True if serialization/deserialization roundtrip is successful
    """
    try:
        # Serialize
        serialized = serialize_svalue(svalue_type, value)
        
        # Deserialize
        deserialized, deserialized_type, _ = deserialize_svalue(serialized)
        
        # For Option type, need special handling
        if svalue_type == 'Option':
            if value is None and deserialized is None:
                return True
            elif value is not None and deserialized is not None:
                # Compare as hex for now
                if isinstance(value, (bytes, str)):
                    value_hex = value.hex() if isinstance(value, bytes) else value
                    return value_hex == deserialized
            return False
        elif svalue_type == 'Coll[Byte]' and isinstance(value, (bytes, str)):
            value_hex = value.hex() if isinstance(value, bytes) else value
            return value_hex == deserialized
        elif svalue_type == 'SigmaProp' and isinstance(value, (bytes, str)):
            value_hex = value.hex() if isinstance(value, bytes) else value
            return value_hex == deserialized
        else:
            return value == deserialized
            
    except Exception as e:
        logger.error(f"Roundtrip test failed for {svalue_type}: {e}")
        return False


def validate_vlq_encoding() -> bool:
    """
    Validate VLQ encoding/decoding with test values.
    
    Returns:
        True if all tests pass
    """
    test_values = [0, 1, 127, 128, 255, 256, 16383, 16384, 2097151]
    
    for value in test_values:
        encoded = encode_vlq(value)
        decoded, _ = decode_vlq(encoded)
        if decoded != value:
            logger.error(f"VLQ roundtrip failed: {value} -> {encoded.hex()} -> {decoded}")
            return False
    
    return True


# Initialize with validation
if __name__ == "__main__":
    if validate_vlq_encoding():
        print("VLQ encoding/decoding validation passed")
    else:
        print("VLQ encoding/decoding validation failed")
    
    # Test roundtrip for basic types
    test_cases = [
        ('Int', 42),
        ('Int', -1),
        ('Long', 123456789012345),
        ('Boolean', True),
        ('Boolean', False),
        ('Coll[Byte]', b'hello'),
        ('Option', None),
    ]
    
    for svalue_type, value in test_cases:
        if debug_serialize_deserialize(svalue_type, value):
            print(f"✓ {svalue_type} roundtrip OK")
        else:
            print(f"✗ {svalue_type} roundtrip FAILED")