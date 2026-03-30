"""
DuckPools Coinflip Contract v2-final — Comprehensive Test Suite

Tests the canonical commit-reveal coinflip contract logic offline,
matching the on-chain ErgoScript exactly. These tests validate:

  1. Commitment verification: blake2b256(secret || choice_byte) == R6
  2. RNG derivation: blake2b256(parentBlockId || secret)[0] % 2
  3. Payout math: win = bet * 97/50 (1.94x), refund = bet - bet/50 (0.98x)
  4. Spending path guards: reveal (house) vs refund (timeout, player)
  5. Edge cases: boundary values, invalid commitments, wrong signers

Contract source: smart-contracts/coinflip_v2_final.es
Compiled address: 3yNMkSZ6b36...TrJfJD3
Register layout: R4-R9 (see contract header)

Usage:
  pytest smart-contracts/tests/test_coinflip_v2_final.py -v

Note: These are OFF-CHAIN logic tests. They verify the contract's
      mathematical correctness. On-chain integration tests require
      a running Ergo node and sigma-rust/AppKit.
"""

import hashlib
import os
import struct
import sys
import pytest

# Add project root for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ─── Crypto Primitives (match ErgoScript on-chain) ───────────────────

def blake2b256(data: bytes) -> bytes:
    """Blake2b-256 hash matching Ergo's native opcode."""
    h = hashlib.blake2b(digest_size=32)
    h.update(data)
    return h.digest()


def decode_point(pk_bytes: bytes) -> bytes:
    """Mock decodePoint — returns raw bytes for comparison."""
    # On-chain this produces a GroupElement; here we just pass through
    return pk_bytes


# ─── Contract Logic (exact replica of coinflip_v2_final.es) ───────────

class CoinflipV2Final:
    """
    Pure-Python replica of the coinflip_v2_final.es contract.
    Every computation here MUST match the on-chain ErgoScript exactly.
    """

    HOUSE_EDGE_NUM = 97   # numerator for win payout: bet * 97 / 50
    HOUSE_EDGE_DEN = 50   # denominator
    REFUND_FEE_DEN = 50   # refund = bet - bet/50

    def __init__(self, house_pk: bytes, player_pk: bytes,
                 commitment_hash: bytes, player_choice: int,
                 timeout_height: int, player_secret: bytes,
                 bet_amount: int, current_height: int):
        self.house_pk = house_pk
        self.player_pk = player_pk
        self.commitment_hash = commitment_hash
        self.player_choice = player_choice
        self.timeout_height = timeout_height
        self.player_secret = player_secret
        self.bet_amount = bet_amount
        self.current_height = current_height

    def verify_commitment(self) -> bool:
        """On-chain: computedHash = blake2b256(playerSecret ++ Coll(choiceByte))"""
        choice_byte = 0x00 if self.player_choice == 0 else 0x01
        computed = blake2b256(self.player_secret + bytes([choice_byte]))
        return computed == self.commitment_hash

    def compute_rng(self, parent_block_id: bytes) -> int:
        """On-chain: blake2b256(blockSeed ++ playerSecret)(0) % 2"""
        rng_hash = blake2b256(parent_block_id + self.player_secret)
        return rng_hash[0] % 2

    def compute_win_payout(self) -> int:
        """On-chain: betAmount * 97L / 50L"""
        return self.bet_amount * self.HOUSE_EDGE_NUM // self.HOUSE_EDGE_DEN

    def compute_refund_amount(self) -> int:
        """On-chain: betAmount - betAmount / 50L"""
        return self.bet_amount - self.bet_amount // self.REFUND_FEE_DEN

    def can_reveal(self, spender_pk: bytes, block_id: bytes,
                   output_pk: bytes, output_value: int) -> bool:
        """Evaluate the REVEAL spending path."""
        if spender_pk != self.house_pk:
            return False
        if not self.verify_commitment():
            return False

        flip = self.compute_rng(block_id)
        player_wins = (flip == self.player_choice)

        if player_wins:
            win_payout = self.compute_win_payout()
            return (output_pk == self.player_pk and
                    output_value >= win_payout)
        else:
            return (output_pk == self.house_pk and
                    output_value >= self.bet_amount)

    def can_refund(self, spender_pk: bytes, output_pk: bytes,
                   output_value: int) -> bool:
        """Evaluate the REFUND spending path."""
        if self.current_height < self.timeout_height:
            return False
        if spender_pk != self.player_pk:
            return False
        refund = self.compute_refund_amount()
        return (output_pk == self.player_pk and
                output_value >= refund)


# ─── Test Helpers ─────────────────────────────────────────────────────

def make_commitment(secret: bytes, choice: int) -> bytes:
    """Compute blake2b256(secret || choice_byte) — frontend does this."""
    choice_byte = 0x00 if choice == 0 else 0x01
    return blake2b256(secret + bytes([choice_byte]))


HOUSE_PK = b'\x02' + b'\xaa' * 32   # 33-byte compressed PK (mock)
PLAYER_PK = b'\x03' + b'\xbb' * 32   # 33-byte compressed PK (mock)
MOCK_BLOCK_ID = b'\x01' * 32          # 32-byte block ID


# ─── Commitment Verification Tests ────────────────────────────────────

class TestCommitmentVerification:

    def test_valid_commitment_heads(self):
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 500)
        assert c.verify_commitment() is True

    def test_valid_commitment_tails(self):
        secret = os.urandom(32)
        commitment = make_commitment(secret, 1)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 1,
                            1000, secret, 1_000_000_000, 500)
        assert c.verify_commitment() is True

    def test_invalid_commitment_wrong_choice(self):
        """Commitment for heads (0) but R7 says tails (1)."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)  # committed to heads
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 1,
                            1000, secret, 1_000_000_000, 500)
        assert c.verify_commitment() is False

    def test_invalid_commitment_wrong_secret(self):
        """Commitment computed with different secret."""
        secret1 = os.urandom(32)
        secret2 = os.urandom(32)
        commitment = make_commitment(secret1, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret2, 1_000_000_000, 500)
        assert c.verify_commitment() is False

    def test_invalid_commitment_garbage_hash(self):
        """R6 contains random bytes, not a valid commitment."""
        secret = os.urandom(32)
        garbage = os.urandom(32)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, garbage, 0,
                            1000, secret, 1_000_000_000, 500)
        assert c.verify_commitment() is False

    def test_commitment_deterministic(self):
        """Same inputs always produce same commitment."""
        secret = b'\x42' * 32
        c1 = make_commitment(secret, 0)
        c2 = make_commitment(secret, 0)
        assert c1 == c2
        assert len(c1) == 32  # blake2b256 output is 32 bytes


# ─── RNG Tests ────────────────────────────────────────────────────────

class TestRNG:

    def test_rng_output_is_binary(self):
        """RNG must produce exactly 0 or 1."""
        for _ in range(100):
            secret = os.urandom(32)
            block_id = os.urandom(32)
            c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                                1000, secret, 1_000_000_000, 500)
            result = c.compute_rng(block_id)
            assert result in (0, 1), f"RNG produced {result}, not 0 or 1"

    def test_rng_deterministic(self):
        """Same block_id + secret always produces same result."""
        secret = b'\x01' * 32
        block_id = b'\x02' * 32
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, secret, 1_000_000_000, 500)
        r1 = c.compute_rng(block_id)
        r2 = c.compute_rng(block_id)
        assert r1 == r2

    def test_rng_changes_with_block_id(self):
        """Different block hashes should produce different results (probabilistically)."""
        secret = b'\x01' * 32
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, secret, 1_000_000_000, 500)
        results = set()
        for i in range(256):
            block_id = i.to_bytes(32, 'big')
            results.add(c.compute_rng(block_id))
        # With 256 different block IDs, we should see both 0 and 1
        assert len(results) == 2, f"RNG not varying: only saw {results}"

    def test_rng_changes_with_secret(self):
        """Different secrets with same block should vary."""
        block_id = b'\xff' * 32
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, b'\x00' * 32, 1_000_000_000, 500)
        results = set()
        for i in range(256):
            c.player_secret = i.to_bytes(32, 'big')
            results.add(c.compute_rng(block_id))
        assert len(results) == 2, f"RNG not varying with secret: {results}"

    def test_rng_distribution_approximately_fair(self):
        """Over many secrets, distribution should be ~50/50."""
        block_id = b'\xaa' * 32
        heads = 0
        n = 1000
        for i in range(n):
            secret = i.to_bytes(32, 'big')
            c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                                1000, secret, 1_000_000_000, 500)
            if c.compute_rng(block_id) == 0:
                heads += 1
        ratio = heads / n
        # Should be within 10% of 50%
        assert 0.40 < ratio < 0.60, f"RNG distribution biased: {ratio:.3f}"


# ─── Payout Math Tests ───────────────────────────────────────────────

class TestPayoutMath:

    def test_win_payout_1_erg(self):
        """1 ERG bet -> 1.94 ERG win payout."""
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, b'\x00' * 32, 1_000_000_000, 500)
        assert c.compute_win_payout() == 1_940_000_000  # 1.94 ERG

    def test_win_payout_0_1_erg(self):
        """0.1 ERG bet -> 0.194 ERG win payout."""
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, b'\x00' * 32, 100_000_000, 500)
        assert c.compute_win_payout() == 194_000_000  # 0.194 ERG

    def test_win_payout_10_erg(self):
        """10 ERG bet -> 19.4 ERG win payout."""
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, b'\x00' * 32, 10_000_000_000, 500)
        assert c.compute_win_payout() == 19_400_000_000  # 19.4 ERG

    def test_refund_1_erg(self):
        """1 ERG bet -> 0.98 ERG refund (2% fee)."""
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, b'\x00' * 32, 1_000_000_000, 500)
        assert c.compute_refund_amount() == 980_000_000  # 0.98 ERG

    def test_house_edge_is_3_percent(self):
        """Verify 3% house edge on the double-or-nothing."""
        bet = 1_000_000_000
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, b'\x00' * 32, bet, 500)
        payout = c.compute_win_payout()
        expected = bet * 2 * 0.97  # 97% of 2x
        assert abs(payout - expected) < 10  # integer rounding tolerance

    def test_refund_fee_is_2_percent(self):
        """Verify 2% refund fee."""
        bet = 1_000_000_000
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, b'\x00' * 32, bet, 500)
        refund = c.compute_refund_amount()
        expected = bet * 0.98
        assert abs(refund - expected) < 10

    def test_minimum_bet_payout(self):
        """Smallest meaningful bet (1 nanoERG) should still compute."""
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, b'\x00' * 32, 0,
                            1000, b'\x00' * 32, 1, 500)
        # 1 * 97 / 50 = 1 (integer division floors)
        assert c.compute_win_payout() == 1
        assert c.compute_refund_amount() == 1  # 1 - 1/50 = 1


# ─── Reveal Path Tests ───────────────────────────────────────────────

class TestRevealPath:

    def _make_contract(self, secret: bytes, choice: int,
                       block_id: bytes, bet: int = 1_000_000_000,
                       height: int = 500, timeout: int = 1000):
        commitment = make_commitment(secret, choice)
        return CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, choice,
                               timeout, secret, bet, height)

    def test_reveal_player_wins_pays_player(self):
        """When player wins, OUTPUTS(0) must go to player with >= 1.94x."""
        # Find a secret+block that makes player win (choice=0, need flip=0)
        secret = b'\x00' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = self._make_contract(secret, 0, block_id)
            if c.compute_rng(block_id) == 0:  # player wins
                win_payout = c.compute_win_payout()
                assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK, win_payout)
                break
        else:
            pytest.fail("Could not find player-winning RNG in 1000 iterations")

    def test_reveal_house_wins_pays_house(self):
        """When house wins, OUTPUTS(0) must go to house with >= bet."""
        secret = b'\x00' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = self._make_contract(secret, 0, block_id)
            if c.compute_rng(block_id) == 1:  # house wins
                assert c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                    c.bet_amount)
                break
        else:
            pytest.fail("Could not find house-winning RNG in 1000 iterations")

    def test_reveal_rejects_player_as_spender(self):
        """Only house can reveal. Player attempting reveal should fail."""
        secret = os.urandom(32)
        block_id = os.urandom(32)
        c = self._make_contract(secret, 0, block_id)
        # Player tries to spend on reveal path — should fail
        assert not c.can_reveal(PLAYER_PK, block_id, PLAYER_PK,
                                c.compute_win_payout())

    def test_reveal_rejects_wrong_output_recipient(self):
        """If player wins but OUTPUTS(0) goes to house, should fail."""
        secret = b'\x00' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = self._make_contract(secret, 0, block_id)
            if c.compute_rng(block_id) == 0:  # player wins
                # House tries to pay itself when player won — rejected
                assert not c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                        c.bet_amount)
                break
        else:
            pytest.skip("Could not find player-winning RNG")

    def test_reveal_rejects_insufficient_payout(self):
        """If player wins but payout < 1.94x, should fail."""
        secret = b'\x00' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = self._make_contract(secret, 0, block_id)
            if c.compute_rng(block_id) == 0:  # player wins
                win_payout = c.compute_win_payout()
                # Pay less than required
                assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                        win_payout - 1)
                break
        else:
            pytest.skip("Could not find player-winning RNG")

    def test_reveal_accepts_overpayment(self):
        """Paying MORE than required to winner should still succeed (>= check)."""
        secret = b'\x00' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = self._make_contract(secret, 0, block_id)
            if c.compute_rng(block_id) == 0:
                win_payout = c.compute_win_payout()
                assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                    win_payout + 1_000_000)
                break
        else:
            pytest.skip("Could not find player-winning RNG")


# ─── Refund Path Tests ───────────────────────────────────────────────

class TestRefundPath:

    def test_refund_after_timeout_succeeds(self):
        """Player can refund after timeout with >= 0.98x bet."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 1001)
        refund = c.compute_refund_amount()
        assert c.can_refund(PLAYER_PK, PLAYER_PK, refund)

    def test_refund_before_timeout_fails(self):
        """Player cannot refund before timeout height."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 999)
        assert not c.can_refund(PLAYER_PK, PLAYER_PK, 980_000_000)

    def test_refund_at_exact_timeout_succeeds(self):
        """HEIGHT == timeoutHeight should allow refund (>= check)."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 1000)
        assert c.can_refund(PLAYER_PK, PLAYER_PK, 980_000_000)

    def test_refund_rejects_house_as_spender(self):
        """Only player can refund. House attempting refund should fail."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 1001)
        assert not c.can_refund(HOUSE_PK, PLAYER_PK, 980_000_000)

    def test_refund_rejects_insufficient_amount(self):
        """Refund paying less than 0.98x should fail."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 1001)
        assert not c.can_refund(PLAYER_PK, PLAYER_PK, 979_999_999)

    def test_refund_accepts_overpayment(self):
        """Refund paying MORE than 0.98x should succeed (>= check)."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 1001)
        assert c.can_refund(PLAYER_PK, PLAYER_PK, 1_000_000_000)


# ─── Integration / End-to-End Tests ──────────────────────────────────

class TestEndToEnd:

    def test_full_game_flow_player_wins(self):
        """Complete game: commit -> reveal -> player wins -> payout."""
        secret = os.urandom(32)
        choice = 0  # heads
        commitment = make_commitment(secret, choice)
        bet = 5_000_000_000  # 5 ERG

        # Create bet box
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, choice,
                            1000, secret, bet, 500)

        # House reveals at height 600 (before timeout)
        c.current_height = 600

        # Find block that makes player win
        for i in range(10000):
            block_id = i.to_bytes(32, 'big')
            if c.compute_rng(block_id) == choice:
                # Verify reveal pays player correctly
                win_payout = c.compute_win_payout()
                assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                    win_payout)
                # Verify house can't steal by paying wrong recipient
                assert not c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                        win_payout)
                return
        pytest.fail("No player-winning block found in 10k iterations")

    def test_full_game_flow_house_wins(self):
        """Complete game: commit -> reveal -> house wins -> house keeps bet."""
        secret = os.urandom(32)
        choice = 1  # tails
        commitment = make_commitment(secret, choice)
        bet = 3_000_000_000  # 3 ERG

        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, choice,
                            1000, secret, bet, 500)
        c.current_height = 600

        for i in range(10000):
            block_id = i.to_bytes(32, 'big')
            if c.compute_rng(block_id) != choice:  # house wins
                assert c.can_reveal(HOUSE_PK, block_id, HOUSE_PK, bet)
                # Player shouldn't get paid
                assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                        c.compute_win_payout())
                return
        pytest.fail("No house-winning block found in 10k iterations")

    def test_full_game_flow_timeout_refund(self):
        """Game times out: player reclaims 98% of bet."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        bet = 2_000_000_000  # 2 ERG

        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            100, secret, bet, 50)

        # Before timeout — no refund
        assert not c.can_refund(PLAYER_PK, PLAYER_PK, 1_960_000_000)

        # After timeout — refund available
        c.current_height = 101
        assert c.can_refund(PLAYER_PK, PLAYER_PK, 1_960_000_000)

        # Verify exact refund amount
        expected_refund = 1_960_000_000  # 2 ERG - 2/50 ERG
        assert c.compute_refund_amount() == expected_refund


# ─── Edge Case Tests ─────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_secret(self):
        """Empty secret (0 bytes) — commitment should still work."""
        # Contract expects Coll[Byte] so 0-length is valid
        secret = b''
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 500)
        assert c.verify_commitment()

    def test_single_byte_secret(self):
        """1-byte secret — minimum entropy but valid."""
        secret = b'\x42'
        commitment = make_commitment(secret, 1)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 1,
                            1000, secret, 1_000_000_000, 500)
        assert c.verify_commitment()

    def test_large_secret(self):
        """256-byte secret — no length restriction in contract."""
        secret = os.urandom(256)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(HOUSE_PK, PLAYER_PK, commitment, 0,
                            1000, secret, 1_000_000_000, 500)
        assert c.verify_commitment()

    def test_commitment_collision_resistance(self):
        """Two different (secret, choice) pairs should not collide."""
        seen = set()
        for i in range(1000):
            secret = i.to_bytes(32, 'big')
            choice = i % 2
            c = make_commitment(secret, choice)
            assert c not in seen, f"Collision at i={i}"
            seen.add(c)

    def test_choice_outside_0_1(self):
        """Contract doesn't validate choice range — choice=2 is valid ErgoScript
        but choice_byte becomes 1 (else branch). This is a known limitation."""
        secret = os.urandom(32)
        # In the contract: if (playerChoice == 0) 0.toByte else 1.toByte
        # So choice=2 produces choice_byte=1, same as tails
        commitment_for_2 = make_commitment(secret, 2)  # same as choice=1
        commitment_for_1 = make_commitment(secret, 1)
        assert commitment_for_2 == commitment_for_1

    def test_same_keys_house_and_player(self):
        """Edge case: house PK == player PK. Contract doesn't prevent this."""
        pk = PLAYER_PK
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV2Final(pk, pk, commitment, 0,
                            1000, secret, 1_000_000_000, 500)
        # Both reveal and refund would work for this PK
        # (This is a known issue — production should check PK != PK)


# ─── Contract Constants Verification ─────────────────────────────────

class TestContractConstants:
    """Verify that Python test constants match the compiled contract."""

    def test_deployed_address_matches_v2_final(self):
        """The compiled v2_final address must match coinflip_deployed.json."""
        with open(os.path.join(os.path.dirname(__file__), '..',
                               'coinflip_deployed.json')) as f:
            import json
            deployed = json.load(f)
        with open(os.path.join(os.path.dirname(__file__), '..',
                               'coinflip_v2_final_compiled.json')) as f:
            compiled = json.load(f)
        assert deployed['p2sAddress'] == compiled['address'], \
            "Deployed address does not match v2_final compiled address"

    def test_register_layout_matches(self):
        """Verify register layout documentation is consistent."""
        with open(os.path.join(os.path.dirname(__file__), '..',
                               'coinflip_deployed.json')) as f:
            import json
            deployed = json.load(f)
        expected = {
            'R4': 'housePubKey (Coll[Byte])',
            'R5': 'playerPubKey (Coll[Byte])',
            'R6': 'commitmentHash (Coll[Byte])',
            'R7': 'playerChoice (Int)',
            'R8': 'timeoutHeight (Int)',
            'R9': 'playerSecret (Coll[Byte])',
        }
        actual = deployed['registerLayout']
        for reg, desc in expected.items():
            assert reg in actual, f"Missing register {reg}"
            assert actual[reg].startswith(desc.split(' (')[0]), \
                f"Register {reg} description mismatch"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
