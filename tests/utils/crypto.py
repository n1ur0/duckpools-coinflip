"""
Cryptographic utility functions for tests.
"""

import hashlib


def sha256(data: bytes) -> bytes:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data).digest()
