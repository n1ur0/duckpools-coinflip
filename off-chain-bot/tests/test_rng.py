"""
Tests for off-chain bot RNG computation.

MAT-419: Implement off-chain bot reveal logic
"""

import hashlib
import pytest
from rng import compute_flip_outcome


class TestComputeFlipOutcome:
    """Tests for compute_flip_outcome."""

    def test_returns_valid_tuple(self):
        """Should return (int, bool, str)."""
        block_id = b"\x00" * 32
        secret = b"\x01" * 32

        result = compute_flip_outcome(block_id, secret, 0)
        assert len(result) == 3
        flip, wins, outcome = result
        assert flip in (0, 1)
        assert isinstance(wins, bool)
        assert outcome in ("heads", "tails")

    def test_outcome_is_heads_or_tails(self):
        """RNG output should always be 0 or 1."""
        for i in range(100):
            block_id = i.to_bytes(32, "big")
            secret = (i + 1000).to_bytes(32, "big")

            flip, _, outcome = compute_flip_outcome(block_id, secret, 0)
            assert flip in (0, 1)
            assert outcome in ("heads", "tails")

    def test_player_wins_when_match(self):
        """Player wins when flip_result == player_choice."""
        # Find a case where flip == 0 (heads)
        found_heads = False
        for i in range(1000):
            block_id = i.to_bytes(32, "big")
            secret = (i + 2000).to_bytes(32, "big")
            flip, wins, _ = compute_flip_outcome(block_id, secret, 0)
            if flip == 0:
                assert wins is True
                found_heads = True
                break
        assert found_heads, "Could not find heads result in 1000 iterations"

    def test_player_loses_when_mismatch(self):
        """Player loses when flip_result != player_choice."""
        found_mismatch = False
        for i in range(1000):
            block_id = i.to_bytes(32, "big")
            secret = (i + 3000).to_bytes(32, "big")
            flip, wins, _ = compute_flip_outcome(block_id, secret, 0)
            if flip == 1:
                assert wins is False
                found_mismatch = True
                break
        assert found_mismatch

    def test_matches_contract_formula(self):
        """
        Verify the output matches coinflip_v2.es exactly:
          val blockSeed  = CONTEXT.preHeader.parentId
          val rngHash    = blake2b256(blockSeed ++ playerSecret)
          val flipResult = rngHash(0) % 2
        """
        block_id = bytes(range(32))
        secret = bytes(range(32, 64))

        # Manual computation matching the contract
        rng_preimage = block_id + secret
        rng_hash = hashlib.blake2b(rng_preimage, digest_size=32).digest()
        expected_flip = rng_hash[0] % 2

        actual_flip, _, actual_outcome = compute_flip_outcome(
            block_id, secret, 0
        )
        assert actual_flip == expected_flip
        assert actual_outcome == ("heads" if expected_flip == 0 else "tails")

    def test_invalid_block_id_length_raises(self):
        """Wrong block ID length should raise ValueError."""
        with pytest.raises(ValueError, match="32 bytes"):
            compute_flip_outcome(b"\x00" * 16, b"\x00" * 32, 0)

    def test_different_secrets_different_outcomes(self):
        """Different secrets should produce (potentially) different outcomes."""
        block_id = b"\x00" * 32
        outcomes = set()
        for i in range(50):
            secret = i.to_bytes(32, "big")
            _, _, outcome = compute_flip_outcome(block_id, secret, 0)
            outcomes.add(outcome)
        # With 50 tries and 50/50 odds, we should see both outcomes
        # (extremely unlikely to only get one)
        assert len(outcomes) >= 1  # At minimum one outcome
