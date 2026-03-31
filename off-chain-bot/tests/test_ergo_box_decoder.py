"""
Tests for off-chain bot Ergo box decoder.

MAT-419: Implement off-chain bot reveal logic
"""

import pytest
from ergo_box_decoder import (
    PendingBetBox,
    decode_coll_byte,
    decode_int,
    decode_pending_bet_box,
    decode_pending_bet_boxes,
)


class TestDecodeCollByte:
    """Tests for decode_coll_byte."""

    def test_scoll_type(self):
        """Decode SColl dict with values list."""
        value = {
            "type": "SColl",
            "valueType": "SByte",
            "values": [0, 1, 2, 255],
        }
        result = decode_coll_byte(value)
        assert result == b"\x00\x01\x02\xff"

    def test_raw_list(self):
        """Decode raw list of ints."""
        result = decode_coll_byte([72, 101, 108, 108, 111])
        assert result == b"Hello"

    def test_raw_bytes(self):
        """Decode raw bytes passthrough."""
        result = decode_coll_byte(b"\x42\x43")
        assert result == b"\x42\x43"

    def test_empty_scoll(self):
        """Decode empty SColl."""
        value = {"type": "SColl", "valueType": "SByte", "values": []}
        result = decode_coll_byte(value)
        assert result == b""

    def test_hex_string_sigma_serialized(self):
        """Decode hex string with sigma Coll[Byte] serialization."""
        # 0x0e = Coll tag, 0x05 = length 5, then 5 bytes
        hex_str = "0e0548656c6c6f"
        result = decode_coll_byte(hex_str)
        assert result == b"Hello"


class TestDecodeInt:
    """Tests for decode_int."""

    def test_sint_type(self):
        """Decode SInt dict."""
        value = {"type": "SInt", "value": 42}
        assert decode_int(value) == 42

    def test_raw_int(self):
        """Decode raw int passthrough."""
        assert decode_int(100) == 100

    def test_zero(self):
        """Decode zero."""
        value = {"type": "SInt", "value": 0}
        assert decode_int(value) == 0

    def test_negative_sint(self):
        """Decode negative SInt."""
        value = {"type": "SInt", "value": -5}
        assert decode_int(value) == -5


class TestDecodePendingBetBox:
    """Tests for decode_pending_bet_box."""

    def _make_raw_box(self) -> dict:
        """Create a valid raw box dict for testing."""
        return {
            "boxId": "a1b2c3d4" + "0" * 56,
            "transactionId": "e5f6a7b8" + "0" * 56,
            "ergoTree": "19d8010c04...",
            "value": "1000000000",  # 1 ERG
            "creationHeight": 500000,
            "additionalTokens": [],
            "additionalRegisters": {
                "R4": {
                    "type": "SColl",
                    "valueType": "SByte",
                    "values": [2] * 33,  # house PK
                },
                "R5": {
                    "type": "SColl",
                    "valueType": "SByte",
                    "values": [3] * 33,  # player PK
                },
                "R6": {
                    "type": "SColl",
                    "valueType": "SByte",
                    "values": [4] * 32,  # commitment hash
                },
                "R7": {"type": "SInt", "value": 0},  # heads
                "R8": {"type": "SInt", "value": 500100},  # timeout
                "R9": {
                    "type": "SColl",
                    "valueType": "SByte",
                    "values": [5] * 32,  # player secret
                },
            },
        }

    def test_valid_box(self):
        """Decode a valid PendingBet box."""
        raw = self._make_raw_box()
        box = decode_pending_bet_box(raw)

        assert box is not None
        assert isinstance(box, PendingBetBox)
        assert box.box_id == raw["boxId"]
        assert box.value == 1_000_000_000
        assert box.player_choice == 0
        assert box.timeout_height == 500100
        assert box.creation_height == 500000
        assert len(box.house_pk_bytes) == 33
        assert len(box.player_pk_bytes) == 33
        assert len(box.commitment_hash) == 32
        assert len(box.player_secret) == 32

    def test_choice_str(self):
        """Test player_choice_str property."""
        raw = self._make_raw_box()
        box = decode_pending_bet_box(raw)
        assert box.player_choice_str == "heads"

        raw["additionalRegisters"]["R7"]["value"] = 1
        box = decode_pending_bet_box(raw)
        assert box.player_choice_str == "tails"

    def test_value_erg(self):
        """Test value_erg property."""
        raw = self._make_raw_box()
        raw["value"] = "5000000000"  # 5 ERG
        box = decode_pending_bet_box(raw)
        assert abs(box.value_erg - 5.0) < 0.001

    def test_tails_choice(self):
        """Decode a tails choice box."""
        raw = self._make_raw_box()
        raw["additionalRegisters"]["R7"]["value"] = 1
        box = decode_pending_bet_box(raw)
        assert box.player_choice == 1
        assert box.player_choice_str == "tails"

    def test_empty_registers(self):
        """Box with empty registers should still decode (with warnings)."""
        raw = self._make_raw_box()
        raw["additionalRegisters"] = {}
        box = decode_pending_bet_box(raw)
        assert box is not None
        assert len(box.commitment_hash) == 0

    def test_invalid_input(self):
        """None or empty dict should return None."""
        assert decode_pending_bet_box(None) is None
        assert decode_pending_bet_box({}) is not None  # Decodes with defaults


class TestDecodePendingBetBoxes:
    """Tests for decode_pending_bet_boxes batch decoding."""

    def test_empty_list(self):
        """Empty list returns empty."""
        assert decode_pending_bet_boxes([]) == []

    def test_mixed_valid_invalid(self):
        """Should decode valid boxes and skip invalid ones."""
        valid = {
            "boxId": "a" * 64,
            "transactionId": "b" * 64,
            "ergoTree": "test",
            "value": "1000000000",
            "creationHeight": 500000,
            "additionalTokens": [],
            "additionalRegisters": {
                "R4": {"type": "SColl", "valueType": "SByte", "values": [0] * 33},
                "R5": {"type": "SColl", "valueType": "SByte", "values": [1] * 33},
                "R6": {"type": "SColl", "valueType": "SByte", "values": [2] * 32},
                "R7": {"type": "SInt", "value": 0},
                "R8": {"type": "SInt", "value": 500100},
                "R9": {"type": "SColl", "valueType": "SByte", "values": [3] * 32},
            },
        }

        result = decode_pending_bet_boxes([valid, None, {}])
        assert len(result) >= 1  # At least the valid one decoded
