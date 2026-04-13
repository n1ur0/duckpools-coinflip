"""
Unit tests for validators module.

Tests Ergo address validation and ValidationError handling.
"""

import pytest
from validators import validate_ergo_address, ValidationError


class TestValidateErgoAddress:
    """Test validate_ergo_address function."""

    def test_valid_p2pk_address(self):
        """Test valid P2PK addresses (starts with 9)."""
        # Valid testnet P2PK address (51 chars)
        valid_p2pk = "9iH1sUa1h1e1P1h1e1P1h1e1P1h1e1P1h1e1P1h1e1P1h1e1P1h1e1"
        result = validate_ergo_address(valid_p2pk)
        assert result == valid_p2pk

    def test_valid_p2s_address(self):
        """Test valid P2S addresses (starts with 3)."""
        # Valid mainnet P2S address (34 chars)
        valid_p2s = "3WwsXf7Xp9X7g7Y7g7Y7g7Y7g7Y7g7Y7g7Y7"
        result = validate_ergo_address(valid_p2s)
        assert result == valid_p2s

    def test_address_stripped(self):
        """Test that address is stripped of whitespace."""
        address_with_spaces = "  9iH1sUa1h1e1P1h1e1P1h1e1P1h1e1P1h1e1P1h1e1P1h1e1  "
        expected = "9iH1sUa1h1e1P1h1e1P1h1e1P1h1e1P1h1e1P1h1e1P1h1e1"
        result = validate_ergo_address(address_with_spaces)
        assert result == expected

    def test_empty_address(self):
        """Test empty address raises ValidationError."""
        with pytest.raises(ValidationError, match="Address is required"):
            validate_ergo_address("")

    def test_none_address(self):
        """Test None address raises ValidationError."""
        with pytest.raises(ValidationError, match="Address is required"):
            validate_ergo_address(None)

    def test_non_string_address(self):
        """Test non-string address raises ValidationError."""
        with pytest.raises(ValidationError, match="Address is required"):
            validate_ergo_address(123)

    def test_address_too_short(self):
        """Test address too short raises ValidationError."""
        short_address = "9abc"
        with pytest.raises(ValidationError, match="Address too short"):
            validate_ergo_address(short_address)

    def test_address_too_long(self):
        """Test address too long raises ValidationError."""
        long_address = "9" + "a" * 60  # 61 chars, exceeds max
        with pytest.raises(ValidationError, match="Address contains invalid characters or has wrong length"):
            validate_ergo_address(long_address)

    def test_invalid_prefix_mainnet(self):
        """Test invalid prefix for mainnet."""
        invalid_prefix = "1abc12345678901234567890123456789012345"
        with pytest.raises(ValidationError, match="Invalid Ergo address prefix"):
            validate_ergo_address(invalid_prefix)

    def test_invalid_prefix_testnet(self):
        """Test invalid prefix for testnet."""
        invalid_prefix = "2abc12345678901234567890123456789012345"
        with pytest.raises(ValidationError, match="Invalid Ergo address prefix"):
            validate_ergo_address(invalid_prefix)

    def test_invalid_characters_zero(self):
        """Test address with invalid character '0'."""
        invalid_char = "9abc12345678901234567890123456789012340"
        with pytest.raises(ValidationError, match="Address contains invalid characters"):
            validate_ergo_address(invalid_char)

    def test_invalid_characters_O(self):
        """Test address with invalid character 'O'."""
        invalid_char = "9abc1234567890123456789012345678901234O"
        with pytest.raises(ValidationError, match="Address contains invalid characters"):
            validate_ergo_address(invalid_char)

    def test_invalid_characters_I(self):
        """Test address with invalid character 'I'."""
        invalid_char = "9abc1234567890123456789012345678901234I"
        with pytest.raises(ValidationError, match="Address contains invalid characters"):
            validate_ergo_address(invalid_char)

    def test_invalid_characters_l(self):
        """Test address with invalid character 'l'."""
        invalid_char = "9abc1234567890123456789012345678901234l"
        with pytest.raises(ValidationError, match="Address contains invalid characters"):
            validate_ergo_address(invalid_char)

    def test_minimum_length_address(self):
        """Test minimum valid length address."""
        min_addr = "9" + "a" * 25  # 26 chars total
        result = validate_ergo_address(min_addr)
        assert result == min_addr

    def test_maximum_length_address(self):
        """Test maximum valid length address."""
        max_addr = "9" + "a" * 59  # 60 chars total
        result = validate_ergo_address(max_addr)
        assert result == max_addr

    def test_realistic_testnet_address(self):
        """Test realistic testnet address pattern."""
        realistic = "9fZ8vKq1qZJzN7uNQJx7Q1xu4Fw1Y9K2p1L3v5M6n8P"
        result = validate_ergo_address(realistic)
        assert result == realistic

    def test_realistic_mainnet_address(self):
        """Test realistic mainnet address pattern."""
        realistic = "3WxT8JfZzNQ7u1qZJx7Q1xu4Fw1Y9K2p1L3v5M6n"
        result = validate_ergo_address(realistic)
        assert result == realistic


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_message(self):
        """Test ValidationError stores message correctly."""
        error = ValidationError("Test error message")
        assert str(error) == "Test error message"
        assert error.args[0] == "Test error message"

    def test_validation_error_inheritance(self):
        """Test ValidationError inherits from Exception."""
        error = ValidationError("Test")
        assert isinstance(error, Exception)
        assert issubclass(ValidationError, Exception)