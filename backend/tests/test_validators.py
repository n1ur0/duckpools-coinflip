"""
Tests for backend/validators.py module
"""

import pytest
from validators import validate_ergo_address, ValidationError


class TestValidateErgoAddress:
    """Test cases for validate_ergo_address function."""

    def test_valid_p2pk_address_testnet(self):
        """Test valid P2PK address (testnet starts with 9)."""
        # Valid testnet P2PK address (9 + 51 chars)
        address = "9" + "A" * 51
        result = validate_ergo_address(address)
        assert result == address

    def test_valid_p2pk_address_mainnet(self):
        """Test valid P2PK address (mainnet starts with 3)."""
        # Valid mainnet P2PK address (3 + 51 chars)
        address = "3" + "B" * 51
        result = validate_ergo_address(address)
        assert result == address

    def test_valid_p2sh_address(self):
        """Test valid P2SH address."""
        # Valid P2SH address (shorter, ~34 chars)
        address = "3" + "C" * 33
        result = validate_ergo_address(address)
        assert result == address

    def test_address_stripped(self):
        """Test that leading/trailing whitespace is stripped."""
        address = "  9" + "A" * 51 + "  "
        result = validate_ergo_address(address)
        assert result == address.strip()
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_invalid_none(self):
        """Test None input raises ValidationError."""
        with pytest.raises(ValidationError, match="Address is required"):
            validate_ergo_address(None)

    def test_invalid_empty_string(self):
        """Test empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="Address is required"):
            validate_ergo_address("")
        with pytest.raises(ValidationError, match="Address too short"):
            validate_ergo_address("   ")

    def test_invalid_type(self):
        """Test non-string input raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_ergo_address(123)
        with pytest.raises(ValidationError, match="must be a string"):
            validate_ergo_address([])

    def test_invalid_prefix(self):
        """Test invalid prefix raises ValidationError."""
        # Test various invalid prefixes
        invalid_prefixes = ["1", "2", "4", "5", "6", "7", "8", "0", "A", "B"]
        for prefix in invalid_prefixes:
            address = prefix + "A" * 30
            with pytest.raises(ValidationError, match="Invalid Ergo address prefix"):
                validate_ergo_address(address)

    def test_too_short(self):
        """Test address too short raises ValidationError."""
        # Minimum length is 26, so test 25
        address = "9" + "A" * 24  # Total 25 chars
        with pytest.raises(ValidationError, match="Address too short"):
            validate_ergo_address(address)

    def test_invalid_characters(self):
        """Test address with invalid Base58 characters."""
        # Base58 excludes: 0, O, I, l
        invalid_chars = ["0", "O", "I", "l"]
        for char in invalid_chars:
            address = "9" + "A" * 25 + char + "A" * 25
            with pytest.raises(ValidationError, match="Address contains invalid characters"):
                validate_ergo_address(address)

    def test_very_long_valid_address(self):
        """Test maximum valid length address (60 chars)."""
        address = "9" + "A" * 59  # Total 60 chars
        result = validate_ergo_address(address)
        assert result == address

    def test_too_long_address(self):
        """Test address too long raises ValidationError."""
        # Maximum length is 60, so test 61
        address = "9" + "A" * 60  # Total 61 chars
        with pytest.raises(ValidationError, match="Address contains invalid characters or has wrong length"):
            validate_ergo_address(address)


class TestValidationError:
    """Test ValidationError exception class."""

    def test_validation_error_is_exception(self):
        """Test ValidationError is an Exception subclass."""
        assert issubclass(ValidationError, Exception)

    def test_validation_error_message(self):
        """Test ValidationError stores message correctly."""
        message = "Test validation error"
        error = ValidationError(message)
        assert str(error) == message
        assert error.args[0] == message