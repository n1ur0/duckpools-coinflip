"""
Tests for VLQ Serializer implementation.

Tests encoding/decoding for all Ergo value types:
- Int: `02` + VLQ(zigzag_i32)
- Long: `04` + VLQ(zigzag_i64)
- Coll[Byte]: `0e` + `01` + VLQ(len) + hex
- SigmaProp: `08cd`+33-byte compressed PK
"""

import pytest
from backend.vlq_serializer import (
    VLQSerializer, 
    ErgoType, 
    SerializedValue, 
    VLQError
)


class TestVLQSerializer:
    """Test cases for VLQSerializer class."""
    
    def test_int_serialization(self):
        """Test Int serialization and deserialization."""
        test_cases = [
            0, 1, -1, 10, -10, 2147483647, -2147483648, 42, -42
        ]
        
        for value in test_cases:
            # Serialize
            serialized = VLQSerializer.serialize_int(value)
            
            # Check type and structure
            assert serialized.type == ErgoType.INT
            assert serialized.value.startswith("02")
            assert serialized.raw_value == value
            
            # Deserialize
            deserialized = VLQSerializer.deserialize_int(serialized.value)
            assert deserialized == value
    
    def test_int_overflow(self):
        """Test Int overflow detection."""
        # Test 64-bit values that should fail for 32-bit Int
        with pytest.raises(VLQError):
            VLQSerializer.serialize_int(2147483648)  # 2^31
        
        with pytest.raises(VLQError):
            VLQSerializer.serialize_int(-2147483649)  # -2^31 - 1
    
    def test_int_invalid_tag(self):
        """Test Int deserialization with invalid type tag."""
        with pytest.raises(VLQError):
            VLQSerializer.deserialize_int("04")  # Long tag instead of Int
    
    def test_long_serialization(self):
        """Test Long serialization and deserialization."""
        test_cases = [
            0, 1, -1, 10, -10, 2147483648, -2147483649, 
            9223372036854775807, -9223372036854775808, 42, -42
        ]
        
        for value in test_cases:
            # Serialize
            serialized = VLQSerializer.serialize_long(value)
            
            # Check type and structure
            assert serialized.type == ErgoType.LONG
            assert serialized.value.startswith("04")
            assert serialized.raw_value == value
            
            # Deserialize
            deserialized = VLQSerializer.deserialize_long(serialized.value)
            assert deserialized == value
    
    def test_long_overflow(self):
        """Test Long overflow detection."""
        # Test values outside 64-bit range
        with pytest.raises(VLQError):
            VLQSerializer.serialize_long(9223372036854775808)  # 2^63
        
        with pytest.raises(VLQError):
            VLQSerializer.serialize_long(-9223372036854775809)  # -2^63 - 1
    
    def test_long_invalid_tag(self):
        """Test Long deserialization with invalid type tag."""
        with pytest.raises(VLQError):
            VLQSerializer.deserialize_long("02")  # Int tag instead of Long
    
    def test_coll_byte_serialization(self):
        """Test Coll[Byte] serialization and deserialization."""
        test_cases = [
            b"",  # Empty bytes
            b"hello",  # ASCII
            bytes(range(256)),  # All byte values
            b"\x00\x01\x02\x03",  # Binary data
            b"\xff\xfe\xfd\xfc",  # High byte values
        ]
        
        for data in test_cases:
            # Serialize
            serialized = VLQSerializer.serialize_coll_byte(data)
            
            # Check type and structure
            assert serialized.type == ErgoType.COLL_BYTE
            assert serialized.value.startswith("0e01")
            assert serialized.raw_value == data
            
            # Deserialize
            deserialized = VLQSerializer.deserialize_coll_byte(serialized.value)
            assert deserialized == data
    
    def test_coll_byte_sbyte_included(self):
        """Test Coll[Byte] serialization with SByte already included."""
        data = b"hello"
        
        # Serialize with SByte already in data
        data_with_sbyte = b"\x01" + data
        serialized = VLQSerializer.serialize_coll_byte(data_with_sbyte, sbyte_included=True)
        
        # Should not include extra SByte
        assert serialized.value.startswith("0e")
        # Check that the SByte is only present once
        assert serialized.value[2:4] != "01"  # No extra SByte
        
        # Deserialize should work
        deserialized = VLQSerializer.deserialize_coll_byte(serialized.value)
        assert deserialized == data_with_sbyte
    
    def test_coll_byte_invalid_input(self):
        """Test Coll[Byte] with invalid input type."""
        with pytest.raises(VLQError):
            VLQSerializer.serialize_coll_byte("not bytes")  # String instead of bytes
    
    def test_coll_byte_invalid_tag(self):
        """Test Coll[Byte] deserialization with invalid type tag."""
        with pytest.raises(VLQError):
            VLQSerializer.deserialize_coll_byte("02")  # Int tag instead of Coll[Byte]
    
    def test_sigma_prop_serialization(self):
        """Test SigmaProp serialization and deserialization."""
        # Test with 33-byte public keys
        test_pks = [
            bytes([0x02] + [i % 256 for i in range(32)]),  # 33 bytes
            bytes([0x03] + [0xff] * 32),  # All 0xff after first byte
            bytes(range(33)),  # 33 bytes with values 0-32
        ]
        
        for pk in test_pks:
            # Serialize
            serialized = VLQSerializer.serialize_sigma_prop(pk)
            
            # Check type and structure
            assert serialized.type == ErgoType.SIGMA_PROP
            assert serialized.value.startswith("08cd")
            assert serialized.raw_value == pk
            
            # Deserialize
            deserialized = VLQSerializer.deserialize_sigma_prop(serialized.value)
            assert deserialized == pk
    
    def test_sigma_prop_invalid_length(self):
        """Test SigmaProp with invalid public key length."""
        with pytest.raises(VLQError):
            VLQSerializer.serialize_sigma_prop(b"too_short")  # Less than 33 bytes
        
        with pytest.raises(VLQError):
            VLQSerializer.serialize_sigma_prop(b"too_long_for_33_bytes")  # More than 33 bytes
    
    def test_sigma_prop_invalid_tag(self):
        """Test SigmaProp deserialization with invalid type tag."""
        with pytest.raises(VLQError):
            VLQSerializer.deserialize_sigma_prop("02")  # Int tag instead of SigmaProp
    
    def test_sigma_prop_invalid_hex(self):
        """Test SigmaProp deserialization with invalid hex."""
        with pytest.raises(VLQError):
            VLQSerializer.deserialize_sigma_prop("08cdinvalidhex")  # Invalid hex
    
    def test_generic_serialization(self):
        """Test generic serialization and deserialization."""
        test_cases = [
            (42, ErgoType.INT),
            (-42, ErgoType.INT),
            (2147483648, ErgoType.LONG),
            (-2147483649, ErgoType.LONG),
            ("aabbccdd", ErgoType.COLL_BYTE),
            (b"aabbccdd", ErgoType.COLL_BYTE),
            ("02" + "00" * 32, ErgoType.SIGMA_PROP),  # 33-byte hex PK
            (bytes([0x02] + [0] * 32), ErgoType.SIGMA_PROP),  # 33-byte PK
        ]
        
        for value, value_type in test_cases:
            # Serialize
            serialized = VLQSerializer.serialize_value(value, value_type)
            
            # Check type
            assert serialized.type == value_type
            
            # Deserialize
            deserialized = VLQSerializer.deserialize_value(serialized.value)
            
            # Compare
            if isinstance(value, str) and value_type in [ErgoType.COLL_BYTE, ErgoType.SIGMA_PROP]:
                # Convert hex string to bytes for comparison
                expected = bytes.fromhex(value)
                assert deserialized == expected
            else:
                assert deserialized == value
    
    def test_generic_serialization_error(self):
        """Test generic serialization with unsupported type."""
        with pytest.raises(VLQError):
            VLQSerializer.serialize_value("value", "unsupported_type")
    
    def test_type_detection(self):
        """Test type detection from hex strings."""
        test_cases = [
            ("0200", ErgoType.INT),
            ("0400", ErgoType.LONG),
            ("0e0100", ErgoType.COLL_BYTE),
            ("08cd" + "00" * 33, ErgoType.SIGMA_PROP),
            ("unknown", None),
        ]
        
        for hex_str, expected_type in test_cases:
            detected_type = VLQSerializer.detect_type(hex_str)
            assert detected_type == expected_type
    
    def test_vlq_edge_cases(self):
        """Test VLQ encoding/decoding edge cases."""
        # Test zero
        assert VLQSerializer._encode_vlq(0) == "00"
        assert VLQSerializer._decode_vlq("00") == 0
        
        # Test single byte
        assert VLQSerializer._encode_vlq(1) == "01"
        assert VLQSerializer._decode_vlq("01") == 1
        
        # Test multi-byte
        assert VLQSerializer._encode_vlq(128) == "8001"
        assert VLQSerializer._decode_vlq("8001") == 128
        
        # Test large value
        large_value = 0x12345678
        encoded = VLQSerializer._encode_vlq(large_value)
        decoded = VLQSerializer._decode_vlq(encoded)
        assert decoded == large_value
    
    def test_zigzag_encoding(self):
        """Test zigzag encoding/decoding."""
        test_cases = [
            (0, 0),
            (1, 2),
            (-1, 1),
            (2, 4),
            (-2, 3),
            (42, 84),
            (-42, 83),
            (2147483647, 4294967294),  # Max 32-bit positive
            (-2147483648, 4294967295),  # Min 32-bit negative
        ]
        
        for original, zigzag in test_cases:
            # 32-bit
            assert VLQSerializer._zigzag_encode_32(original) == zigzag
            assert VLQSerializer._zigzag_decode_32(zigzag) == original
            
            # 64-bit (same for small values)
            assert VLQSerializer._zigzag_encode_64(original) == zigzag
            assert VLQSerializer._zigzag_decode_64(zigzag) == original
    
    def test_real_world_examples(self):
        """Test with real-world examples from Ergo documentation."""
        # Int examples from ARCHITECTURE.md
        assert VLQSerializer.serialize_int(0).value == "0200"
        assert VLQSerializer.serialize_int(1).value == "0202"
        assert VLQSerializer.serialize_int(10).value == "0214"
        
        # Coll[Byte] example (32 bytes)
        data_32_bytes = bytes(range(32))
        serialized = VLQSerializer.serialize_coll_byte(data_32_bytes)
        assert serialized.value.startswith("0e01")
        assert len(serialized.value) == 2 + 2 + 2 + 64  # 0e + 01 + VLQ(len) + 32*2 hex chars
        
        # Long examples
        assert VLQSerializer.serialize_long(0).value == "0400"
        assert VLQSerializer.serialize_long(1).value == "0402"