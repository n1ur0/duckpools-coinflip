"""
DuckPools - VLQ Serializer for Ergo Values

Implementation of VLQ (Variable-Length Quantity) encoder/decoder for Ergo register values
with full type coverage including Int, Long, Coll[Byte], and SigmaProp.

MAT-XXX: VLQ encoder/decoder for Ergo values with full type coverage
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


class ErgoType(str, Enum):
    """Ergo value types for serialization."""
    INT = "int"
    LONG = "long"
    COLL_BYTE = "coll_byte"
    SIGMA_PROP = "sigma_prop"


@dataclass
class SerializedValue:
    """Container for serialized Ergo value with metadata."""
    value: str  # Hex-encoded serialized value
    type: ErgoType
    raw_value: Any


class VLQError(Exception):
    """Error raised during VLQ encoding/decoding."""
    pass


class VLQSerializer:
    """
    VLQ (Variable-Length Quantity) serializer for Ergo register values.
    
    Supports:
    - Int: `02` + VLQ(zigzag_i32)
    - Long: `04` + VLQ(zigzag_i64)
    - Coll[Byte]: `0e` + `01` + VLQ(len) + hex
    - SigmaProp: `08cd`+33-byte compressed PK
    """
    
    # Type tags for Ergo values
    INT_TAG = "02"
    LONG_TAG = "04"
    COLL_BYTE_TAG = "0e"
    SIGMA_PROP_TAG = "08cd"
    
    # Coll[Byte] element type tag
    COLL_BYTE_ELEM_TAG = "01"
    
    @classmethod
    def _zigzag_encode_32(cls, value: int) -> int:
        """Zigzag encode a 32-bit signed integer."""
        return (value << 1) ^ (value >> 31)
    
    @classmethod
    def _zigzag_decode_32(cls, value: int) -> int:
        """Zigzag decode a 32-bit signed integer."""
        return (value >> 1) ^ -(value & 1)
    
    @classmethod
    def _zigzag_encode_64(cls, value: int) -> int:
        """Zigzag encode a 64-bit signed integer."""
        return (value << 1) ^ (value >> 63)
    
    @classmethod
    def _zigzag_decode_64(cls, value: int) -> int:
        """Zigzag decode a 64-bit signed integer."""
        return (value >> 1) ^ -(value & 1)
    
    @classmethod
    def _encode_vlq(cls, value: int) -> str:
        """
        Encode an integer using VLQ (Variable-Length Quantity).
        
        Args:
            value: The integer to encode
            
        Returns:
            Hex-encoded VLQ string
        """
        if value == 0:
            return "00"
        
        hex_digits = []
        while value > 0:
            # Take 7 least significant bits
            digit = value & 0x7f
            value >>= 7
            
            # Set high bit if more digits follow
            if value > 0:
                digit |= 0x80
            
            hex_digits.append(f"{digit:02x}")
        
        return "".join(hex_digits)
    
    @classmethod
    def _decode_vlq(cls, hex_str: str) -> int:
        """
        Decode a VLQ (Variable-Length Quantity) hex string.
        
        Args:
            hex_str: Hex-encoded VLQ string
            
        Returns:
            Decoded integer value
        """
        value = 0
        shift = 0
        
        # Convert hex to bytes
        try:
            bytes_data = bytes.fromhex(hex_str)
        except ValueError as e:
            raise VLQError(f"Invalid hex string: {hex_str}") from e
        
        for byte in bytes_data:
            # Extract 7 bits
            value |= (byte & 0x7f) << shift
            shift += 7
            
            # Check if this is the last byte
            if not (byte & 0x80):
                break
        
        return value
    
    @classmethod
    def serialize_int(cls, value: int) -> SerializedValue:
        """
        Serialize an Int value: `02` + VLQ(zigzag_i32)
        
        Args:
            value: 32-bit signed integer
            
        Returns:
            SerializedValue with hex-encoded result
        """
        # Validate 32-bit range
        if value < -2147483648 or value > 2147483647:
            raise VLQError(f"Int value out of 32-bit range: {value}")
        
        # Zigzag encode
        zigzag = cls._zigzag_encode_32(value)
        
        # VLQ encode
        vlq_hex = cls._encode_vlq(zigzag)
        
        # Add type tag
        serialized = cls.INT_TAG + vlq_hex
        
        return SerializedValue(
            value=serialized,
            type=ErgoType.INT,
            raw_value=value
        )
    
    @classmethod
    def deserialize_int(cls, hex_str: str) -> int:
        """
        Deserialize an Int value: `02` + VLQ(zigzag_i32)
        
        Args:
            hex_str: Hex-encoded Int value
            
        Returns:
            Original 32-bit signed integer
        """
        if not hex_str.startswith(cls.INT_TAG):
            raise VLQError(f"Invalid Int type tag: {hex_str}")
        
        # Remove type tag
        vlq_hex = hex_str[2:]
        
        # VLQ decode
        zigzag = cls._decode_vlq(vlq_hex)
        
        # Zigzag decode
        value = cls._zigzag_decode_32(zigzag)
        
        return value
    
    @classmethod
    def serialize_long(cls, value: int) -> SerializedValue:
        """
        Serialize a Long value: `04` + VLQ(zigzag_i64)
        
        Args:
            value: 64-bit signed integer
            
        Returns:
            SerializedValue with hex-encoded result
        """
        # Validate 64-bit range
        if value < -9223372036854775808 or value > 9223372036854775807:
            raise VLQError(f"Long value out of 64-bit range: {value}")
        
        # Zigzag encode
        zigzag = cls._zigzag_encode_64(value)
        
        # VLQ encode
        vlq_hex = cls._encode_vlq(zigzag)
        
        # Add type tag
        serialized = cls.LONG_TAG + vlq_hex
        
        return SerializedValue(
            value=serialized,
            type=ErgoType.LONG,
            raw_value=value
        )
    
    @classmethod
    def deserialize_long(cls, hex_str: str) -> int:
        """
        Deserialize a Long value: `04` + VLQ(zigzag_i64)
        
        Args:
            hex_str: Hex-encoded Long value
            
        Returns:
            Original 64-bit signed integer
        """
        if not hex_str.startswith(cls.LONG_TAG):
            raise VLQError(f"Invalid Long type tag: {hex_str}")
        
        # Remove type tag
        vlq_hex = hex_str[2:]
        
        # VLQ decode
        zigzag = cls._decode_vlq(vlq_hex)
        
        # Zigzag decode
        value = cls._zigzag_decode_64(zigzag)
        
        return value
    
    @classmethod
    def serialize_coll_byte(cls, data: bytes, sbyte_included: bool = False) -> SerializedValue:
        """
        Serialize a Coll[Byte] value: `0e` + `01` + VLQ(len) + hex
        
        Args:
            data: Byte array to serialize
            sbyte_included: If True, assume data already includes SByte (0x01)
            
        Returns:
            SerializedValue with hex-encoded result
        """
        if not isinstance(data, bytes):
            raise VLQError(f"Coll[Byte] requires bytes input, got {type(data)}")
        
        # Convert bytes to hex
        hex_data = data.hex()
        
        # Build serialized value
        if sbyte_included:
            # Format: 0e + VLQ(len) + hex (already includes 0x01)
            serialized = cls.COLL_BYTE_TAG + cls._encode_vlq(len(data)) + hex_data
        else:
            # Format: 0e + 01 + VLQ(len) + hex
            serialized = cls.COLL_BYTE_TAG + cls.COLL_BYTE_ELEM_TAG + cls._encode_vlq(len(data)) + hex_data
        
        return SerializedValue(
            value=serialized,
            type=ErgoType.COLL_BYTE,
            raw_value=data
        )
    
    @classmethod
    def deserialize_coll_byte(cls, hex_str: str) -> bytes:
        """
        Deserialize a Coll[Byte] value: `0e` + `01` + VLQ(len) + hex
        
        Args:
            hex_str: Hex-encoded Coll[Byte] value
            
        Returns:
            Original byte array
        """
        if not hex_str.startswith(cls.COLL_BYTE_TAG):
            raise VLQError(f"Invalid Coll[Byte] type tag: {hex_str}")
        
        # Remove type tag
        remaining = hex_str[2:]
        
        # Check if SByte is present
        if remaining.startswith(cls.COLL_BYTE_ELEM_TAG):
            # Format: 0e + 01 + VLQ(len) + hex
            sbyte = remaining[0:2]
            if sbyte != cls.COLL_BYTE_ELEM_TAG:
                raise VLQError(f"Invalid Coll[Byte] SByte: {sbyte}")
            remaining = remaining[2:]
        
        # Decode length
        try:
            # Find the end of VLQ (first byte without high bit set)
            length_hex = ""
            for i in range(0, len(remaining), 2):
                if i + 2 > len(remaining):
                    break
                byte = int(remaining[i:i+2], 16)
                length_hex += remaining[i:i+2]
                if not (byte & 0x80):
                    break
            
            length = cls._decode_vlq(length_hex)
            data_hex = remaining[len(length_hex):]
            
            # Validate length
            if len(data_hex) // 2 != length:
                raise VLQError(f"Coll[Byte] length mismatch: expected {length}, got {len(data_hex) // 2}")
            
            # Convert hex to bytes
            data = bytes.fromhex(data_hex)
            return data
            
        except Exception as e:
            raise VLQError(f"Failed to deserialize Coll[Byte]: {e}") from e
    
    @classmethod
    def serialize_sigma_prop(cls, public_key: bytes) -> SerializedValue:
        """
        Serialize a SigmaProp value: `08cd` + 33-byte compressed PK
        
        Args:
            public_key: 33-byte compressed public key
            
        Returns:
            SerializedValue with hex-encoded result
        """
        if len(public_key) != 33:
            raise VLQError(f"SigmaProp requires 33-byte public key, got {len(public_key)} bytes")
        
        # Add type tag and convert PK to hex
        serialized = cls.SIGMA_PROP_TAG + public_key.hex()
        
        return SerializedValue(
            value=serialized,
            type=ErgoType.SIGMA_PROP,
            raw_value=public_key
        )
    
    @classmethod
    def deserialize_sigma_prop(cls, hex_str: str) -> bytes:
        """
        Deserialize a SigmaProp value: `08cd` + 33-byte compressed PK
        
        Args:
            hex_str: Hex-encoded SigmaProp value
            
        Returns:
            Original 33-byte compressed public key
        """
        if not hex_str.startswith(cls.SIGMA_PROP_TAG):
            raise VLQError(f"Invalid SigmaProp type tag: {hex_str}")
        
        # Remove type tag
        pk_hex = hex_str[4:]
        
        # Validate length (33 bytes = 66 hex chars)
        if len(pk_hex) != 66:
            raise VLQError(f"SigmaProp requires 66 hex chars (33 bytes), got {len(pk_hex)}")
        
        # Convert hex to bytes
        try:
            return bytes.fromhex(pk_hex)
        except ValueError as e:
            raise VLQError(f"Invalid SigmaProp hex: {pk_hex}") from e
    
    @classmethod
    def serialize_value(cls, value: Any, value_type: ErgoType) -> SerializedValue:
        """
        Generic serialization method that dispatches to appropriate serializer.
        
        Args:
            value: Value to serialize
            value_type: Type of the value
            
        Returns:
            SerializedValue with hex-encoded result
        """
        try:
            if value_type == ErgoType.INT:
                return cls.serialize_int(int(value))
            elif value_type == ErgoType.LONG:
                return cls.serialize_long(int(value))
            elif value_type == ErgoType.COLL_BYTE:
                if isinstance(value, str):
                    # Assume hex string
                    return cls.serialize_coll_byte(bytes.fromhex(value))
                elif isinstance(value, bytes):
                    return cls.serialize_coll_byte(value)
                else:
                    raise VLQError(f"Unsupported Coll[Byte] input type: {type(value)}")
            elif value_type == ErgoType.SIGMA_PROP:
                if isinstance(value, str):
                    # Assume hex string
                    return cls.serialize_sigma_prop(bytes.fromhex(value))
                elif isinstance(value, bytes):
                    return cls.serialize_sigma_prop(value)
                else:
                    raise VLQError(f"Unsupported SigmaProp input type: {type(value)}")
            else:
                raise VLQError(f"Unsupported ErgoType: {value_type}")
        except Exception as e:
            raise VLQError(f"Failed to serialize {value_type} value: {e}") from e
    
    @classmethod
    def deserialize_value(cls, hex_str: str) -> Any:
        """
        Generic deserialization method that detects type from hex string.
        
        Args:
            hex_str: Hex-encoded Ergo value
            
        Returns:
            Deserialized value
        """
        try:
            if hex_str.startswith(cls.INT_TAG):
                return cls.deserialize_int(hex_str)
            elif hex_str.startswith(cls.LONG_TAG):
                return cls.deserialize_long(hex_str)
            elif hex_str.startswith(cls.COLL_BYTE_TAG):
                return cls.deserialize_coll_byte(hex_str)
            elif hex_str.startswith(cls.SIGMA_PROP_TAG):
                return cls.deserialize_sigma_prop(hex_str)
            else:
                raise VLQError(f"Unknown Ergo value type: {hex_str[:4]}...")
        except Exception as e:
            raise VLQError(f"Failed to deserialize value: {e}") from e
    
    @classmethod
    def detect_type(cls, hex_str: str) -> Optional[ErgoType]:
        """
        Detect the type of a hex-encoded Ergo value.
        
        Args:
            hex_str: Hex-encoded Ergo value
            
        Returns:
            Detected ErgoType or None if unknown
        """
        if hex_str.startswith(cls.INT_TAG):
            return ErgoType.INT
        elif hex_str.startswith(cls.LONG_TAG):
            return ErgoType.LONG
        elif hex_str.startswith(cls.COLL_BYTE_TAG):
            return ErgoType.COLL_BYTE
        elif hex_str.startswith(cls.SIGMA_PROP_TAG):
            return ErgoType.SIGMA_PROP
        else:
            return None