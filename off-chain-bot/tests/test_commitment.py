"""
Tests for off-chain bot commitment verification.

MAT-419: Implement off-chain bot reveal logic
"""

import hashlib
import pytest
from commitment import compute_commitment_hash, verify_commitment


class TestComputeCommitmentHash:
    """Tests for compute_commitment_hash."""

    def test_heads_choice(self):
        """Test commitment computation for heads (choice=0)."""
        secret = b"\x42" * 32
        choice = 0
        choice_byte = b"\x00"
        expected = hashlib.blake2b(secret + choice_byte, digest_size=32).digest()

        result = compute_commitment_hash(secret, choice)
        assert result == expected

    def test_tails_choice(self):
        """Test commitment computation for tails (choice=1)."""
        secret = b"\xab" * 32
        choice = 1
        choice_byte = b"\x01"
        expected = hashlib.blake2b(secret + choice_byte, digest_size=32).digest()

        result = compute_commitment_hash(secret, choice)
        assert result == expected

    def test_empty_secret(self):
        """Empty secret should still produce a valid hash."""
        result = compute_commitment_hash(b"", 0)
        assert len(result) == 32

    def test_different_choices_produce_different_hashes(self):
        """Heads and tails with same secret must produce different hashes."""
        secret = b"\x00" * 32
        h0 = compute_commitment_hash(secret, 0)
        h1 = compute_commitment_hash(secret, 1)
        assert h0 != h1


class TestVerifyCommitment:
    """Tests for verify_commitment."""

    def test_valid_commitment_heads(self):
        """Valid heads commitment should verify."""
        secret = os.urandom(32) if 'os' in dir() else b"\x01" * 32
        secret = b"\x01" * 32
        commitment = compute_commitment_hash(secret, 0)

        ok, msg = verify_commitment(secret, 0, commitment)
        assert ok is True
        assert "verified" in msg.lower()

    def test_valid_commitment_tails(self):
        """Valid tails commitment should verify."""
        secret = b"\xff" * 32
        commitment = compute_commitment_hash(secret, 1)

        ok, msg = verify_commitment(secret, 1, commitment)
        assert ok is True

    def test_wrong_choice_fails(self):
        """Commitment with wrong choice should fail."""
        secret = b"\x42" * 32
        commitment = compute_commitment_hash(secret, 0)

        ok, msg = verify_commitment(secret, 1, commitment)
        assert ok is False
        assert "mismatch" in msg.lower()

    def test_wrong_secret_fails(self):
        """Commitment with wrong secret should fail."""
        secret1 = b"\x00" * 32
        secret2 = b"\xff" * 32
        commitment = compute_commitment_hash(secret1, 0)

        ok, msg = verify_commitment(secret2, 0, commitment)
        assert ok is False

    def test_invalid_choice_value(self):
        """Invalid choice (not 0 or 1) should fail."""
        ok, msg = verify_commitment(b"\x00" * 32, 5, b"\x00" * 32)
        assert ok is False
        assert "invalid choice" in msg.lower()

    def test_wrong_commitment_length(self):
        """Wrong commitment hash length should fail."""
        ok, msg = verify_commitment(b"\x00" * 32, 0, b"\x00" * 16)
        assert ok is False
        assert "32 bytes" in msg

    def test_empty_secret_fails(self):
        """Empty secret should fail validation."""
        ok, msg = verify_commitment(b"", 0, b"\x00" * 32)
        assert ok is False
        assert "empty" in msg.lower()
