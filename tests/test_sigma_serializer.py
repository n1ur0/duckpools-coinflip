#!/usr/bin/env python3
"""
Test suite for sigma_serializer.py

Ground-truth serialization library for DuckPools protocol.
Tests all encoding/decoding functions and edge cases.

Author: Serialization Specialist Jr (350d346f-f2d2-4b0c-8792-b9fc5ef3fd38)
Team: Protocol Core
Company: Matsuzaka (DuckPools)
"""

import sys
import os

# Add off-chain-bot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'off-chain-bot'))

from sigma_serializer import (
    encode_vlq, decode_vlq,
    zigzag_encode_i32, zigzag_encode_i64,
    zigzag_decode_i32, zigzag_decode_i64,
    serialize_int, serialize_long,
    serialize_coll_byte, deserialize_coll_byte, detect_coll_byte_format,
    serialize_sigmaprop,
    serialize_pending_bet_registers,
)


class TestVLQ:
    """Test Variable-Length Quantity encoding."""

    def test_zero(self):
        assert encode_vlq(0) == "00"
        assert decode_vlq("00") == 0

    def test_single_byte_values(self):
        assert encode_vlq(1) == "01"
        assert encode_vlq(127) == "7f"
        assert decode_vlq("01") == 1
        assert decode_vlq("7f") == 127

    def test_multi_byte_values(self):
        assert encode_vlq(128) == "8001"
        assert encode_vlq(255) == "ff01"
        assert encode_vlq(16383) == "ff7f"
        assert encode_vlq(16384) == "808001"
        assert decode_vlq("8001") == 128
        assert decode_vlq("ff01") == 255

    def test_large_values(self):
        assert decode_vlq(encode_vlq(1_000_000_000)) == 1_000_000_000

    def test_negative_raises(self):
        try:
            encode_vlq(-1)
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestZigZag:
    """Test ZigZag signed/unsigned mapping."""

    def test_i32_basic(self):
        assert zigzag_encode_i32(0) == 0
        assert zigzag_encode_i32(1) == 2
        assert zigzag_encode_i32(-1) == 1
        assert zigzag_encode_i32(2) == 4
        assert zigzag_encode_i32(-2) == 3

    def test_i32_roundtrip(self):
        for v in [-100, -1, 0, 1, 100, 1000, 1000000]:
            encoded = zigzag_encode_i32(v)
            decoded = zigzag_decode_i32(encoded)
            assert decoded == v, f"Roundtrip failed for {v}"

    def test_i64_basic(self):
        assert zigzag_encode_i64(0) == 0
        assert zigzag_encode_i64(1) == 2
        assert zigzag_encode_i64(-1) == 1

    def test_i64_roundtrip(self):
        for v in [-100, -1, 0, 1, 100, 1000, 1000000]:
            encoded = zigzag_encode_i64(v)
            decoded = zigzag_decode_i64(encoded)
            assert decoded == v, f"Roundtrip failed for {v}"

    def test_i32_i64_consistency(self):
        for v in [-100, -1, 0, 1, 100, 1000]:
            assert zigzag_encode_i32(v) == zigzag_encode_i64(v)


class TestIntSerialization:
    """Test IntConstant (i32) serialization."""

    def test_basic_values(self):
        assert serialize_int(0) == "0200"
        assert serialize_int(1) == "0202"
        assert serialize_int(10) == "0214"

    def test_negative_values(self):
        assert serialize_int(-1) == "0201"
        assert serialize_int(-10) == "0213"


class TestLongSerialization:
    """Test LongConstant (i64) serialization."""

    def test_basic_values(self):
        assert serialize_long(0) == "0400"
        assert serialize_long(1) == "0402"


class TestCollByteSerialization:
    """Test Coll[Byte] serialization with format detection."""

    def test_format_a(self):
        data = b'\x00' * 32
        result = serialize_coll_byte(data)
        assert result.startswith("0e01")
        assert len(result) == 4 + 2 + 64  # 0e01 + VLQ(32) + 64 hex chars

    def test_format_b(self):
        data = b'\x00' * 32
        result = serialize_coll_byte(data, format="without_type")
        assert result.startswith("0e")
        assert result[2:4] != "01"
        assert len(result) == 2 + 2 + 64  # 0e + VLQ(32) + 64 hex chars

    def test_detection(self):
        assert detect_coll_byte_format("0e012000") == "with_type"
        assert detect_coll_byte_format("0e2000") == "without_type"

    def test_deserialization_format_a(self):
        data = b'\x12\x34\x56\x78'
        serialized = serialize_coll_byte(data)
        deserialized = deserialize_coll_byte(serialized)
        assert deserialized == data

    def test_deserialization_format_b(self):
        data = b'\x12\x34\x56\x78'
        serialized = serialize_coll_byte(data, format="without_type")
        deserialized = deserialize_coll_byte(serialized)
        assert deserialized == data


class TestSigmaPropSerialization:
    """Test SigmaProp encoding."""

    def test_basic(self):
        pk = b'\x02' + b'\x00' * 32
        result = serialize_sigmaprop(pk)
        assert result.startswith("08cd")
        assert len(result) == 4 + 66  # 08cd + 33*2 hex chars

    def test_wrong_length_raises(self):
        try:
            serialize_sigmaprop(b'\x00' * 32)
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestPendingBetRegisters:
    """Test PendingBet box register serialization."""

    def test_all_registers(self):
        registers = serialize_pending_bet_registers(
            ergo_tree=b'\x00' * 10,
            commitment_hash=b'\x11' * 32,
            bet_choice=1,
            player_secret=12345,
            bet_id=b'\x22' * 32
        )

        assert "R4" in registers
        assert "R5" in registers
        assert "R6" in registers
        assert "R7" in registers
        assert "R8" in registers

        assert registers["R4"].startswith("0e01")  # Coll[Byte]
        assert registers["R5"].startswith("0e01")  # Coll[Byte]
        assert registers["R6"].startswith("02")    # Int
        assert registers["R7"].startswith("02")    # Int
        assert registers["R8"].startswith("0e01")  # Coll[Byte]


def run_tests():
    """Run all test classes."""
    test_classes = [
        TestVLQ,
        TestZigZag,
        TestIntSerialization,
        TestLongSerialization,
        TestCollByteSerialization,
        TestSigmaPropSerialization,
        TestPendingBetRegisters,
    ]

    total_tests = 0
    passed_tests = 0

    for test_class in test_classes:
        print(f"Running {test_class.__name__}...")
        for attr in dir(test_class):
            if attr.startswith('test_'):
                total_tests += 1
                try:
                    test_instance = test_class()
                    method = getattr(test_instance, attr)
                    method()
                    passed_tests += 1
                    print(f"  ✓ {attr}")
                except Exception as e:
                    print(f"  ✗ {attr}: {e}")
        print()

    print(f"Results: {passed_tests}/{total_tests} tests passed")
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
