#!/usr/bin/env python3
"""Test register decoding against known sigma-serialized values."""

def decode_vlq_unsigned(raw: bytes, start: int) -> tuple:
    """Decode a VLQ-encoded unsigned integer."""
    value = 0
    i = start
    while i < len(raw):
        byte = raw[i]
        value = (value << 7) | (byte & 0x7F)
        i += 1
        if not (byte & 0x80):
            break
    return value, i - start

def decode_coll_sbyte(sv_hex: str) -> str:
    """Decode Coll[SByte] from sigma serialization."""
    raw = bytes.fromhex(sv_hex)
    if raw[0] != 0x09 or raw[1] != 0x01:
        raise ValueError(f"Not Coll[SByte]: {sv_hex[:4]}")
    length, vlq_bytes = decode_vlq_unsigned(raw, 2)
    data_start = 2 + vlq_bytes
    return raw[data_start:data_start + length].hex()

def decode_sint(sv_hex: str) -> int:
    """Decode SInt from sigma serialization."""
    raw = bytes.fromhex(sv_hex)
    if raw[0] != 0x03:
        raise ValueError(f"Not SInt: {sv_hex[:2]}")
    zigzag_val, _ = decode_vlq_unsigned(raw, 1)
    return (zigzag_val >> 1) ^ -(zigzag_val & 1)

# Test Coll[SByte] with 33-byte pubkey (66 hex chars)
# Format: 09 01 <VLQ(33)> <33 bytes>
# VLQ(33) = 0x21 (single byte, 33 < 128)
test_pubkey = "02abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"  # 33 bytes
vlq_33 = "21"  # 33 in VLQ
sv_hex = "0901" + vlq_33 + test_pubkey
result = decode_coll_sbyte(sv_hex)
assert result == test_pubkey, f"Expected {test_pubkey}, got {result}"
print(f"PASS: Coll[SByte] decode 33-byte pubkey")

# Test Coll[SByte] with 32-byte hash (64 hex chars)
test_hash = "aabbccdd" * 8  # 32 bytes
vlq_32 = "20"  # 32 in VLQ
sv_hex = "0901" + vlq_32 + test_hash
result = decode_coll_sbyte(sv_hex)
assert result == test_hash, f"Expected {test_hash}, got {result}"
print(f"PASS: Coll[SByte] decode 32-byte hash")

# Test Coll[SByte] with 8-byte secret
test_secret = "0102030405060708"
vlq_8 = "08"
sv_hex = "0901" + vlq_8 + test_secret
result = decode_coll_sbyte(sv_hex)
assert result == test_secret, f"Expected {test_secret}, got {result}"
print(f"PASS: Coll[SByte] decode 8-byte secret")

# Test SInt with value 0
sv_hex = "0300"  # SInt type + VLQ(0)
result = decode_sint(sv_hex)
assert result == 0, f"Expected 0, got {result}"
print(f"PASS: SInt decode 0")

# Test SInt with value 1
sv_hex = "0302"  # SInt type + zigzag(1)=2 + VLQ(2)
result = decode_sint(sv_hex)
assert result == 1, f"Expected 1, got {result}"
print(f"PASS: SInt decode 1")

# Test SInt with value 100 (timeout height example)
# zigzag(100) = 200, VLQ(200) = 0xC8 0x01
sv_hex = "03c801"
result = decode_sint(sv_hex)
assert result == 100, f"Expected 100, got {result}"
print(f"PASS: SInt decode 100")

print("\nAll register decoding tests passed!")
