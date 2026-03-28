"""
Tests for validators.py module

MAT-363: Create validators.py module for Ergo address and input validation
"""

import pytest
from validators import validate_ergo_address, ValidationError


class TestValidateErgoAddress:
    """Test cases for validate_ergo_address function."""

    def test_valid_mainnet_address(self):
        """Test valid mainnet address (starts with '3')."""
        # Valid mainnet P2PK address (51 chars)
        valid_mainnet = "3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8vG"
        result = validate_ergo_address(valid_mainnet)
        assert result == valid_mainnet

    def test_valid_testnet_address(self):
        """Test valid testnet address (starts with '9')."""
        # Valid testnet P2PK address (51 chars)  
        valid_testnet = "9WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8vG"
        result = validate_ergo_address(valid_testnet)
        assert result == valid_testnet

    def test_valid_short_address(self):
        """Test valid shorter address (P2PKH, ~34 chars)."""
        valid_short = "3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJj"
        result = validate_ergo_address(valid_short)
        assert result == valid_short

    def test_valid_long_address(self):
        """Test valid longer address (custom script, ~60 chars)."""
        valid_long = "3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8vG3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJj"
        result = validate_ergo_address(valid_long)
        assert result == valid_long

    def test_address_stripping(self):
        """Test that address gets stripped of whitespace."""
        address_with_spaces = "  3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8vG  "
        result = validate_ergo_address(address_with_spaces)
        assert result == address_with_spaces.strip()

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

    def test_too_short_address(self):
        """Test address too short raises ValidationError."""
        too_short = "3abc"
        with pytest.raises(ValidationError, match="Address too short"):
            validate_ergo_address(too_short)

    def test_invalid_prefix(self):
        """Test address with invalid prefix raises ValidationError."""
        invalid_prefix = "1WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8vG"
        with pytest.raises(ValidationError, match="Invalid Ergo address prefix"):
            validate_ergo_address(invalid_prefix)

    def test_invalid_characters(self):
        """Test address with invalid Base58 characters raises ValidationError."""
        # Contains '0' which is not in Base58 alphabet
        invalid_chars = "3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8v0"
        with pytest.raises(ValidationError, match="Address contains invalid characters"):
            validate_ergo_address(invalid_chars)

    def test_invalid_characters_oh(self):
        """Test address with 'O' (capital o) which is invalid in Base58."""
        # Contains 'O' which is not in Base58 alphabet
        invalid_chars = "3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8vO"
        with pytest.raises(ValidationError, match="Address contains invalid characters"):
            validate_ergo_address(invalid_chars)

    def test_invalid_characters_il(self):
        """Test address with 'l' (lowercase L) which is invalid in Base58."""
        # Contains 'l' which is not in Base58 alphabet
        invalid_chars = "3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8vl"
        with pytest.raises(ValidationError, match="Address contains invalid characters"):
            validate_ergo_address(invalid_chars)

    def test_invalid_characters_I(self):
        """Test address with 'I' (capital I) which is invalid in Base58."""
        # Contains 'I' which is not in Base58 alphabet
        invalid_chars = "3WwxPekHc2jyV6Vj4zRkXW9X8V1Z6qJjXkY5V6R1j2eU8hK7gN9bX3fM8vI"
        with pytest.raises(ValidationError, match="Address contains invalid characters"):
            validate_ergo_address(invalid_chars)


class TestValidationError:
    """Test ValidationError exception class."""

    def test_validation_error_inheritance(self):
        """Test that ValidationError is a subclass of Exception."""
        assert issubclass(ValidationError, Exception)

    def test_validation_error_message(self):
        """Test ValidationError with custom message."""
        error_msg = "Test error message"
        error = ValidationError(error_msg)
        assert str(error) == error_msg

    def test_validation_error_empty_message(self):
        """Test ValidationError with empty message."""
        error = ValidationError("")
        assert str(error) == ""