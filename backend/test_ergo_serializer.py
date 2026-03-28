"""
Test cases for ergo_serializer.py

Unit tests for VLQ encoder/decoder and Ergo value serialization.
"""

import sys
import unittest
from ergo_serializer import (
    SerializationError,
    encode_vlq,
    decode_vlq,
    zigzag_encode_i32,
    zigzag_encode_i64,
    zigzag_decode_i32,
    zigzag_decode_i64,
    serialize_int,
    serialize_long,
    serialize_coll_byte,
    serialize_sigma_prop,
    serialize_boolean,
    serialize_option,
    serialize_pair,
    deserialize_int,
    deserialize_long,
    deserialize_coll_byte,
    deserialize_sigma_prop,
    deserialize_boolean,
    deserialize_option,
    serialize_svalue,
    deserialize_svalue,
    debug_serialize_deserialize,
    validate_vlq_encoding,
    bytes_to_hex,
    hex_to_bytes,
)


class TestVLQEncoding(unittest.TestCase):
    """Test VLQ encoding/decoding."""
    
    def test_encode_vlq_zero(self):
        """Test encoding zero."""
        result = encode_vlq(0)
        self.assertEqual(result, b'\x00')
    
    def test_encode_vlq_single_byte(self):
        """Test encoding single-byte values."""
        self.assertEqual(encode_vlq(1), b'\x01')
        self.assertEqual(encode_vlq(127), b'\x7f')
    
    def test_encode_vlq_multi_byte(self):
        """Test encoding multi-byte values."""
        self.assertEqual(encode_vlq(128), b'\x80\x01')
        self.assertEqual(encode_vlq(255), b'\xff\x01')
        self.assertEqual(encode_vlq(256), b'\x80\x02')
        self.assertEqual(encode_vlq(16383), b'\xff\x7f')
        self.assertEqual(encode_vlq(16384), b'\x80\x80\x01')
    
    def test_decode_vlq_zero(self):
        """Test decoding zero."""
        value, offset = decode_vlq(b'\x00')
        self.assertEqual(value, 0)
        self.assertEqual(offset, 1)
    
    def test_decode_vlq_single_byte(self):
        """Test decoding single-byte values."""
        value, offset = decode_vlq(b'\x7f')
        self.assertEqual(value, 127)
        self.assertEqual(offset, 1)
    
    def test_decode_vlq_multi_byte(self):
        """Test decoding multi-byte values."""
        value, offset = decode_vlq(b'\x80\x01')
        self.assertEqual(value, 128)
        self.assertEqual(offset, 2)
        
        value, offset = decode_vlq(b'\x80\x80\x01')
        self.assertEqual(value, 16384)
        self.assertEqual(offset, 3)
    
    def test_decode_vlq_with_offset(self):
        """Test decoding with offset."""
        data = b'\xff\x80\x01\xfe'
        value, offset = decode_vlq(data, 1)
        self.assertEqual(value, 128)
        self.assertEqual(offset, 3)
    
    def test_decode_vlq_invalid(self):
        """Test decoding invalid VLQ."""
        with self.assertRaises(SerializationError):
            decode_vlq(b'\x80')  # Missing continuation byte


class TestZigZagEncoding(unittest.TestCase):
    """Test ZigZag encoding/decoding."""
    
    def test_zigzag_i32_roundtrip(self):
        """Test 32-bit ZigZag roundtrip."""
        test_values = [0, 1, -1, 42, -42, 2147483647, -2147483648]
        
        for value in test_values:
            encoded = zigzag_encode_i32(value)
            decoded = zigzag_decode_i32(encoded)
            self.assertEqual(decoded, value)
    
    def test_zigzag_i64_roundtrip(self):
        """Test 64-bit ZigZag roundtrip."""
        test_values = [0, 1, -1, 42, -42, 9223372036854775807, -9223372036854775808]
        
        for value in test_values:
            encoded = zigzag_encode_i64(value)
            decoded = zigzag_decode_i64(encoded)
            self.assertEqual(decoded, value)
    
    def test_zigzag_mappings(self):
        """Test specific ZigZag mappings."""
        self.assertEqual(zigzag_encode_i32(0), 0)
        self.assertEqual(zigzag_encode_i32(-1), 1)
        self.assertEqual(zigzag_encode_i32(1), 2)
        self.assertEqual(zigzag_encode_i32(-2), 3)
        self.assertEqual(zigzag_encode_i32(2), 4)


class TestIntSerialization(unittest.TestCase):
    """Test Int serialization/deserialization."""
    
    def test_serialize_int_positive(self):
        """Test serializing positive int."""
        result = serialize_int(42)
        self.assertEqual(result[0], 0x02)  # Int type tag
    
    def test_serialize_int_negative(self):
        """Test serializing negative int."""
        result = serialize_int(-1)
        self.assertEqual(result[0], 0x02)  # Int type tag
    
    def test_serialize_int_bounds(self):
        """Test int bounds checking."""
        with self.assertRaises(SerializationError):
            serialize_int(-2147483649)  # Too small
        with self.assertRaises(SerializationError):
            serialize_int(2147483648)   # Too large
    
    def test_deserialize_int(self):
        """Test deserializing int."""
        serialized = serialize_int(42)
        value, offset = deserialize_int(serialized)
        self.assertEqual(value, 42)
        self.assertEqual(offset, len(serialized))
    
    def test_int_roundtrip(self):
        """Test int serialization roundtrip."""
        test_values = [0, 1, -1, 42, -42, 2147483647, -2147483648]
        
        for value in test_values:
            serialized = serialize_int(value)
            deserialized, _ = deserialize_int(serialized)
            self.assertEqual(deserialized, value)


class TestLongSerialization(unittest.TestCase):
    """Test Long serialization/deserialization."""
    
    def test_serialize_long_positive(self):
        """Test serializing positive long."""
        result = serialize_long(42)
        self.assertEqual(result[0], 0x04)  # Long type tag
    
    def test_serialize_long_negative(self):
        """Test serializing negative long."""
        result = serialize_long(-1)
        self.assertEqual(result[0], 0x04)  # Long type tag
    
    def test_serialize_long_bounds(self):
        """Test long bounds checking."""
        with self.assertRaises(SerializationError):
            serialize_long(-9223372036854775809)  # Too small
        with self.assertRaises(SerializationError):
            serialize_long(9223372036854775808)   # Too large
    
    def test_deserialize_long(self):
        """Test deserializing long."""
        serialized = serialize_long(42)
        value, offset = deserialize_long(serialized)
        self.assertEqual(value, 42)
        self.assertEqual(offset, len(serialized))
    
    def test_long_roundtrip(self):
        """Test long serialization roundtrip."""
        test_values = [0, 1, -1, 42, -42, 9223372036854775807, -9223372036854775808]
        
        for value in test_values:
            serialized = serialize_long(value)
            deserialized, _ = deserialize_long(serialized)
            self.assertEqual(deserialized, value)


class TestCollByteSerialization(unittest.TestCase):
    """Test Coll[Byte] serialization/deserialization."""
    
    def test_serialize_coll_byte_with_element_type(self):
        """Test serializing Coll[Byte] with element type."""
        data = b'hello'
        result = serialize_coll_byte(data, include_element_type=True)
        self.assertEqual(result[0], 0x0e)  # Coll type tag
        self.assertEqual(result[1], 0x01)  # Element type tag
    
    def test_serialize_coll_byte_without_element_type(self):
        """Test serializing Coll[Byte] without element type."""
        data = b'hello'
        result = serialize_coll_byte(data, include_element_type=False)
        self.assertEqual(result[0], 0x0e)  # Coll type tag
        self.assertNotEqual(result[1], 0x01)  # No element type tag
    
    def test_deserialize_coll_byte(self):
        """Test deserializing Coll[Byte]."""
        data = b'hello'
        serialized = serialize_coll_byte(data)
        deserialized, offset = deserialize_coll_byte(serialized)
        self.assertEqual(deserialized, data)
        self.assertEqual(offset, len(serialized))
    
    def test_coll_byte_roundtrip(self):
        """Test Coll[Byte] serialization roundtrip."""
        test_data = [b'', b'a', b'hello', b'\x00\x01\x02\xff']
        
        for data in test_data:
            serialized = serialize_coll_byte(data)
            deserialized, _ = deserialize_coll_byte(serialized)
            self.assertEqual(deserialized, data)


class TestSigmaPropSerialization(unittest.TestCase):
    """Test SigmaProp serialization/deserialization."""
    
    def test_serialize_sigma_prop(self):
        """Test serializing SigmaProp."""
        pk = bytes([i for i in range(33)])  # 33-byte PK
        result = serialize_sigma_prop(pk)
        self.assertEqual(len(result), 35)  # 0x08 + 0xcd + 33 bytes
        self.assertEqual(result[0], 0x08)
        self.assertEqual(result[1], 0xcd)
    
    def test_serialize_sigma_prop_invalid_length(self):
        """Test serializing SigmaProp with invalid PK length."""
        with self.assertRaises(SerializationError):
            serialize_sigma_prop(b'too_short')
    
    def test_deserialize_sigma_prop(self):
        """Test deserializing SigmaProp."""
        pk = bytes([i for i in range(33)])
        serialized = serialize_sigma_prop(pk)
        deserialized, offset = deserialize_sigma_prop(serialized)
        self.assertEqual(deserialized, pk)
        self.assertEqual(offset, 35)
    
    def test_sigma_prop_roundtrip(self):
        """Test SigmaProp serialization roundtrip."""
        pk = bytes([i for i in range(33)])
        serialized = serialize_sigma_prop(pk)
        deserialized, _ = deserialize_sigma_prop(serialized)
        self.assertEqual(deserialized, pk)


class TestBooleanSerialization(unittest.TestCase):
    """Test Boolean serialization/deserialization."""
    
    def test_serialize_boolean_true(self):
        """Test serializing true."""
        result = serialize_boolean(True)
        self.assertEqual(result, b'\x07')
    
    def test_serialize_boolean_false(self):
        """Test serializing false."""
        result = serialize_boolean(False)
        self.assertEqual(result, b'\x06')
    
    def test_deserialize_boolean(self):
        """Test deserializing boolean."""
        true_serialized = serialize_boolean(True)
        false_serialized = serialize_boolean(False)
        
        value, offset = deserialize_boolean(true_serialized)
        self.assertTrue(value)
        self.assertEqual(offset, 1)
        
        value, offset = deserialize_boolean(false_serialized)
        self.assertFalse(value)
        self.assertEqual(offset, 1)
    
    def test_boolean_roundtrip(self):
        """Test Boolean serialization roundtrip."""
        for value in [True, False]:
            serialized = serialize_boolean(value)
            deserialized, _ = deserialize_boolean(serialized)
            self.assertEqual(deserialized, value)


class TestOptionSerialization(unittest.TestCase):
    """Test Option serialization/deserialization."""
    
    def test_serialize_option_none(self):
        """Test serializing None option."""
        result = serialize_option(None)
        self.assertEqual(result, b'\x0b')
    
    def test_serialize_option_some(self):
        """Test serializing Some option."""
        inner_value = serialize_int(42)
        result = serialize_option(inner_value)
        self.assertEqual(result[0], 0x0b)
        self.assertEqual(result[1:], inner_value)
    
    def test_deserialize_option_none(self):
        """Test deserializing None option."""
        serialized = serialize_option(None)
        value, offset = deserialize_option(serialized)
        self.assertIsNone(value)
        self.assertEqual(offset, 1)
    
    def test_deserialize_option_some(self):
        """Test deserializing Some option."""
        inner_value = serialize_int(42)
        serialized = serialize_option(inner_value)
        value, offset = deserialize_option(serialized)
        self.assertIsNotNone(value)
        self.assertEqual(offset, len(serialized))


class TestGenericSerialization(unittest.TestCase):
    """Test generic SValue serialization/deserialization."""
    
    def test_serialize_int_type(self):
        """Test generic Int serialization."""
        result = serialize_svalue('Int', 42)
        self.assertEqual(result[0], 0x02)
    
    def test_serialize_long_type(self):
        """Test generic Long serialization."""
        result = serialize_svalue('Long', 42)
        self.assertEqual(result[0], 0x04)
    
    def test_serialize_coll_byte_type(self):
        """Test generic Coll[Byte] serialization."""
        result = serialize_svalue('Coll[Byte]', b'hello')
        self.assertEqual(result[0], 0x0e)
    
    def test_serialize_boolean_type(self):
        """Test generic Boolean serialization."""
        result = serialize_svalue('Boolean', True)
        self.assertEqual(result[0], 0x07)
    
    def test_deserialize_int_type(self):
        """Test generic Int deserialization."""
        serialized = serialize_svalue('Int', 42)
        value, type_name, offset = deserialize_svalue(serialized)
        self.assertEqual(value, 42)
        self.assertEqual(type_name, 'Int')
        self.assertEqual(offset, len(serialized))
    
    def test_deserialize_unknown_type(self):
        """Test deserializing unknown type."""
        with self.assertRaises(SerializationError):
            deserialize_svalue(b'\xff')  # Unknown type tag


class TestUtilities(unittest.TestCase):
    """Test utility functions."""
    
    def test_bytes_to_hex(self):
        """Test bytes to hex conversion."""
        data = b'hello'
        hex_str = bytes_to_hex(data)
        self.assertEqual(hex_str, '68656c6c6f')
    
    def test_hex_to_bytes(self):
        """Test hex to bytes conversion."""
        hex_str = '68656c6c6f'
        data = hex_to_bytes(hex_str)
        self.assertEqual(data, b'hello')
    
    def test_validate_vlq_encoding(self):
        """Test VLQ encoding validation."""
        self.assertTrue(validate_vlq_encoding())
    
    def test_debug_serialize_deserialize(self):
        """Test debug roundtrip function."""
        self.assertTrue(debug_serialize_deserialize('Int', 42))
        self.assertTrue(debug_serialize_deserialize('Boolean', True))
        self.assertTrue(debug_serialize_deserialize('Boolean', False))
        self.assertTrue(debug_serialize_deserialize('Option', None))
        self.assertTrue(debug_serialize_deserialize('Coll[Byte]', b'hello'))


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)