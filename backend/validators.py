"""
DuckPools - Input Validators

Shared validation functions for Ergo addresses and other protocol-specific inputs.

BE-9: Ergo address validation regex for LP route models.
SEC-A5: Address validation to prevent SSRF and injection via address fields.
"""

import re


# Ergo addresses are Base58Check encoded.
# Mainnet P2PK: starts with '3'
# Testnet P2PK: starts with '9'
# Length: typically 30-40 characters.
# Base58 alphabet excludes: 0, O, I, l (ambiguous characters).
ERGO_ADDRESS_RE = re.compile(
    r"^[39][1-9A-HJ-NP-Za-km-z]{29,39}$"
)


class ValidationError(Exception):
    """Raised when input fails validation."""
    pass


def validate_ergo_address(address: str) -> str:
    """
    Validate an Ergo address format.

    Checks:
    1. Starts with '3' (mainnet) or '9' (testnet)
    2. Contains only Base58 characters (no 0, O, I, l)
    3. Length is in valid range (30-40 chars total)

    Does NOT verify the Base58Check checksum (would require a base58 library).
    The Ergo node will reject malformed addresses at transaction build time.

    Args:
        address: The Ergo address string to validate.

    Returns:
        The address string (stripped) if valid.

    Raises:
        ValidationError: If the address format is invalid.
    """
    if not address or not isinstance(address, str):
        raise ValidationError("Address is required and must be a string")

    address = address.strip()

    if len(address) < 30:
        raise ValidationError(f"Address too short ({len(address)} chars, expected 30-40)")

    if not ERGO_ADDRESS_RE.match(address):
        if not address.startswith(("3", "9")):
            raise ValidationError(
                f"Invalid Ergo address prefix: expected '3' (mainnet) or '9' (testnet), "
                f"got '{address[0]}'"
            )
        raise ValidationError(
            f"Address contains invalid characters or has wrong length "
            f"({len(address)} chars, expected 30-40)"
        )

    return address
