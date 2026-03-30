"""
DuckPools Coinflip Contract v3 — Comprehensive Test Suite

Tests the canonical commit-reveal coinflip contract logic offline,
matching the on-chain ErgoScript exactly. These tests validate:

  1. Commitment verification: blake2b256(secret || choice_byte) == R6
  2. RNG derivation: blake2b256(parentBlockId || secret)[0] % 2
  3. Payout math: win = bet * 97/50 (1.94x), refund = bet - bet/50 (0.98x)
  4. Spending path guards: reveal (house) vs refund (timeout, player)
  5. Reveal window: R10 enforces HEIGHT >= rngBlockHeight && HEIGHT <= timeoutHeight
  6. Edge cases: boundary values, invalid commitments, wrong signers

Contract source: smart-contracts/coinflip_v3.es
Register layout: R4-R10 (see contract header)

Usage:
  pytest smart-contracts/tests/test_coinflip_v3.py -v

Note: These are OFF-CHAIN logic tests. They verify the contract's
      mathematical correctness. On-chain integration tests require
      a running Ergo node and sigma-rust/AppKit.
"""

import hashlib
import os
import pytest

# Add project root for imports
sys_path = os.path.join(os.path.dirname(__file__), '..', '..')
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)


# ─── Crypto Primitives (match ErgoScript on-chain) ───────────────────

def blake2b256(data: bytes) -> bytes:
    """Blake2b-256 hash matching Ergo's native opcode."""
    h = hashlib.blake2b(digest_size=32)
    h.update(data)
    return h.digest()


# ─── Contract Logic (exact replica of coinflip_v3.es) ────────────────

class CoinflipV3:
    """
    Pure-Python replica of the coinflip_v3.es contract.
    Every computation here MUST match the on-chain ErgoScript exactly.
    """

    HOUSE_EDGE_NUM = 97   # numerator for win payout: bet * 97 / 50
    HOUSE_EDGE_DEN = 50   # denominator
    REFUND_FEE_DEN = 50   # refund = bet - bet/50

    def __init__(self, house_pk: bytes, player_pk: bytes,
                 commitment_hash: bytes, player_choice: int,
                 timeout_height: int, player_secret: bytes,
                 bet_amount: int, current_height: int,
                 rng_block_height: int):
        self.house_pk = house_pk
        self.player_pk = player_pk
        self.commitment_hash = commitment_hash
        self.player_choice = player_choice
        self.timeout_height = timeout_height
        self.player_secret = player_secret
        self.bet_amount = bet_amount
        self.current_height = current_height
        self.rng_block_height = rng_block_height

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
                   output_pk: bytes, output_value: int,
                   reveal_height: int) -> bool:
        """Evaluate the REVEAL spending path with reveal window check."""
        # House signature check
        if spender_pk != self.house_pk:
            return False
        # Commitment verification
        if not self.verify_commitment():
            return False
        # Reveal window: HEIGHT >= rngBlockHeight && HEIGHT <= timeoutHeight
        if reveal_height < self.rng_block_height:
            return False
        if reveal_height > self.timeout_height:
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


def make_contract(secret: bytes = None, choice: int = 0,
                  bet: int = 1_000_000_000,
                  height: int = 500, timeout: int = 1000,
                  rng_height: int = 970):
    """Create a CoinflipV3 instance with valid commitment."""
    if secret is None:
        secret = os.urandom(32)
    commitment = make_commitment(secret, choice)
    return CoinflipV3(
        house_pk=HOUSE_PK,
        player_pk=PLAYER_PK,
        commitment_hash=commitment,
        player_choice=choice,
        timeout_height=timeout,
        player_secret=secret,
        bet_amount=bet,
        current_height=height,
        rng_block_height=rng_height,
    )


# ─── Mock Data ────────────────────────────────────────────────────────

HOUSE_PK = b'\x02' + b'\xaa' * 32   # 33-byte compressed PK (mock)
PLAYER_PK = b'\x03' + b'\xbb' * 32   # 33-byte compressed PK (mock)
MOCK_BLOCK_ID = b'\x01' * 32          # 32-byte block ID


# ═══════════════════════════════════════════════════════════════════════
# TEST: Commitment Verification
# ═══════════════════════════════════════════════════════════════════════

class TestCommitmentVerification:

    def test_valid_commitment_heads(self):
        secret = os.urandom(32)
        c = make_contract(secret=secret, choice=0)
        assert c.verify_commitment() is True

    def test_valid_commitment_tails(self):
        secret = os.urandom(32)
        c = make_contract(secret=secret, choice=1)
        assert c.verify_commitment() is True

    def test_invalid_commitment_wrong_choice(self):
        """Commitment for heads (0) but R7 says tails (1)."""
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)  # committed to heads
        c = CoinflipV3(HOUSE_PK, PLAYER_PK, commitment, 1,
                        1000, secret, 1_000_000_000, 500, 970)
        assert c.verify_commitment() is False

    def test_invalid_commitment_wrong_secret(self):
        """Commitment computed with different secret."""
        secret1 = os.urandom(32)
        secret2 = os.urandom(32)
        commitment = make_commitment(secret1, 0)
        c = CoinflipV3(HOUSE_PK, PLAYER_PK, commitment, 0,
                        1000, secret2, 1_000_000_000, 500, 970)
        assert c.verify_commitment() is False

    def test_invalid_commitment_garbage_hash(self):
        """R6 contains random bytes, not a valid commitment."""
        secret = os.urandom(32)
        garbage = os.urandom(32)
        c = CoinflipV3(HOUSE_PK, PLAYER_PK, garbage, 0,
                        1000, secret, 1_000_000_000, 500, 970)
        assert c.verify_commitment() is False

    def test_commitment_deterministic(self):
        """Same inputs always produce same commitment."""
        secret = b'\x42' * 32
        c1 = make_commitment(secret, 0)
        c2 = make_commitment(secret, 0)
        assert c1 == c2
        assert len(c1) == 32  # blake2b256 output is always 32 bytes

    def test_commitment_different_for_different_choices(self):
        """Same secret, different choices produce different commitments."""
        secret = os.urandom(32)
        c_heads = make_commitment(secret, 0)
        c_tails = make_commitment(secret, 1)
        assert c_heads != c_tails

    def test_commitment_collision_resistance(self):
        """1000 different (secret, choice) pairs should not collide."""
        seen = set()
        for i in range(1000):
            secret = i.to_bytes(32, 'big')
            choice = i % 2
            c = make_commitment(secret, choice)
            assert c not in seen, f"Collision at i={i}"
            seen.add(c)


# ═══════════════════════════════════════════════════════════════════════
# TEST: On-Chain RNG (blake2b256 block-hash, NO Math.random)
# ═══════════════════════════════════════════════════════════════════════

class TestOnChainRNG:

    def test_rng_output_is_binary(self):
        """RNG must produce exactly 0 or 1."""
        for _ in range(100):
            secret = os.urandom(32)
            block_id = os.urandom(32)
            c = make_contract(secret=secret)
            result = c.compute_rng(block_id)
            assert result in (0, 1), f"RNG produced {result}, not 0 or 1"

    def test_rng_deterministic(self):
        """Same block_id + secret always produces same result."""
        secret = b'\x01' * 32
        block_id = b'\x02' * 32
        c = make_contract(secret=secret)
        r1 = c.compute_rng(block_id)
        r2 = c.compute_rng(block_id)
        assert r1 == r2

    def test_rng_changes_with_block_id(self):
        """Different block hashes should produce different results."""
        secret = b'\xff' * 32
        c = make_contract(secret=secret)
        results = set()
        for i in range(256):
            block_id = i.to_bytes(32, 'big')
            results.add(c.compute_rng(block_id))
        assert len(results) == 2, f"RNG not varying: only saw {results}"

    def test_rng_changes_with_secret(self):
        """Different secrets with same block should vary."""
        block_id = b'\xaa' * 32
        c = make_contract(secret=b'\x00' * 32)
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
            c = make_contract(secret=secret)
            if c.compute_rng(block_id) == 0:
                heads += 1
        ratio = heads / n
        assert 0.40 < ratio < 0.60, f"RNG distribution biased: {ratio:.3f}"

    def test_rng_entropy_per_byte(self):
        """First byte of blake2b256 output should have ~4 bits set on average."""
        block_id = b'\xcc' * 32
        bit_counts = []
        for i in range(100):
            secret = i.to_bytes(32, 'big')
            c = make_contract(secret=secret)
            rng_hash = blake2b256(block_id + c.player_secret)
            bit_counts.append(bin(rng_hash[0]).count('1'))
        avg_bits = sum(bit_counts) / len(bit_counts)
        assert 3.0 < avg_bits < 5.0, f"Entropy check failed: avg bits = {avg_bits}"


# ═══════════════════════════════════════════════════════════════════════
# TEST: Payout Math
# ═══════════════════════════════════════════════════════════════════════

class TestPayoutMath:

    def test_win_payout_1_erg(self):
        """1 ERG bet -> 1.94 ERG win payout."""
        c = make_contract(bet=1_000_000_000)
        assert c.compute_win_payout() == 1_940_000_000

    def test_win_payout_0_1_erg(self):
        """0.1 ERG bet -> 0.194 ERG win payout."""
        c = make_contract(bet=100_000_000)
        assert c.compute_win_payout() == 194_000_000

    def test_win_payout_10_erg(self):
        """10 ERG bet -> 19.4 ERG win payout."""
        c = make_contract(bet=10_000_000_000)
        assert c.compute_win_payout() == 19_400_000_000

    def test_refund_1_erg(self):
        """1 ERG bet -> 0.98 ERG refund (2% fee)."""
        c = make_contract(bet=1_000_000_000)
        assert c.compute_refund_amount() == 980_000_000

    def test_refund_10_erg(self):
        """10 ERG bet -> 9.8 ERG refund."""
        c = make_contract(bet=10_000_000_000)
        assert c.compute_refund_amount() == 9_800_000_000

    def test_house_edge_is_3_percent(self):
        """Verify 3% house edge on the double-or-nothing."""
        bet = 1_000_000_000
        c = make_contract(bet=bet)
        payout = c.compute_win_payout()
        expected = bet * 2 * 0.97  # 97% of 2x
        assert abs(payout - expected) < 10

    def test_refund_fee_is_2_percent(self):
        """Verify 2% refund fee."""
        bet = 1_000_000_000
        c = make_contract(bet=bet)
        refund = c.compute_refund_amount()
        expected = bet * 0.98
        assert abs(refund - expected) < 10

    def test_minimum_bet_payout(self):
        """Smallest meaningful bet (1 nanoERG) should still compute."""
        c = make_contract(bet=1)
        assert c.compute_win_payout() == 1
        assert c.compute_refund_amount() == 1

    def test_large_bet_payout(self):
        """100 ERG bet should compute without overflow."""
        c = make_contract(bet=100_000_000_000)
        assert c.compute_win_payout() == 194_000_000_000
        assert c.compute_refund_amount() == 98_000_000_000


# ═══════════════════════════════════════════════════════════════════════
# TEST: Reveal Path
# ═══════════════════════════════════════════════════════════════════════

class TestRevealPath:

    def test_reveal_player_wins_pays_player(self):
        """When player wins, OUTPUTS(0) must go to player with >= 1.94x."""
        secret = b'\x01' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = make_contract(secret=secret, choice=0)
            if c.compute_rng(block_id) == 0:
                win_payout = c.compute_win_payout()
                assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                    win_payout, reveal_height=980)
                break
        else:
            pytest.fail("No player-winning RNG in 1000 iterations")

    def test_reveal_house_wins_pays_house(self):
        """When house wins, OUTPUTS(0) must go to house with >= bet."""
        secret = b'\x02' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = make_contract(secret=secret, choice=0)
            if c.compute_rng(block_id) == 1:
                assert c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                    c.bet_amount, reveal_height=980)
                break
        else:
            pytest.fail("No house-winning RNG in 1000 iterations")

    def test_reveal_rejects_player_as_spender(self):
        """Only house can reveal. Player attempting reveal should fail."""
        secret = os.urandom(32)
        block_id = os.urandom(32)
        c = make_contract(secret=secret)
        assert not c.can_reveal(PLAYER_PK, block_id, PLAYER_PK,
                                c.compute_win_payout(), reveal_height=980)

    def test_reveal_rejects_wrong_output_recipient(self):
        """If player wins but OUTPUTS(0) goes to house, should fail."""
        secret = b'\x03' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = make_contract(secret=secret, choice=0)
            if c.compute_rng(block_id) == 0:
                assert not c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                        c.bet_amount, reveal_height=980)
                break
        else:
            pytest.skip("No player-winning RNG found")

    def test_reveal_rejects_insufficient_payout(self):
        """If player wins but payout < 1.94x, should fail."""
        secret = b'\x04' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = make_contract(secret=secret, choice=0)
            if c.compute_rng(block_id) == 0:
                win_payout = c.compute_win_payout()
                assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                        win_payout - 1, reveal_height=980)
                break
        else:
            pytest.skip("No player-winning RNG found")

    def test_reveal_accepts_overpayment(self):
        """Paying MORE than required to winner should still succeed."""
        secret = b'\x05' * 32
        for i in range(1000):
            block_id = i.to_bytes(32, 'big')
            c = make_contract(secret=secret, choice=0)
            if c.compute_rng(block_id) == 0:
                win_payout = c.compute_win_payout()
                assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                    win_payout + 1_000_000, reveal_height=980)
                break
        else:
            pytest.skip("No player-winning RNG found")

    def test_reveal_rejects_invalid_commitment(self):
        """Even with correct house sig and block, bad commitment fails."""
        secret = os.urandom(32)
        block_id = os.urandom(32)
        garbage_commitment = os.urandom(32)
        c = CoinflipV3(HOUSE_PK, PLAYER_PK, garbage_commitment, 0,
                        1000, secret, 1_000_000_000, 500, 970)
        assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                2_000_000_000, reveal_height=980)


# ═══════════════════════════════════════════════════════════════════════
# TEST: Reveal Window (R10 — the key v3 improvement)
# ═══════════════════════════════════════════════════════════════════════

class TestRevealWindow:

    def test_reveal_before_rng_height_fails(self):
        """House cannot reveal before rngBlockHeight (R10)."""
        secret = os.urandom(32)
        block_id = os.urandom(32)
        c = make_contract(secret=secret, rng_height=970)
        # Try to reveal at height 969 (before rng_height 970)
        assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                c.compute_win_payout(), reveal_height=969)

    def test_reveal_at_exact_rng_height_succeeds(self):
        """House CAN reveal at exactly rngBlockHeight."""
        secret = os.urandom(32)
        block_id = os.urandom(32)
        c = make_contract(secret=secret, rng_height=970)
        # Reveal at exactly 970
        flip = c.compute_rng(block_id)
        if flip == c.player_choice:
            # player wins
            assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                c.compute_win_payout(), reveal_height=970)
        else:
            # house wins
            assert c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                c.bet_amount, reveal_height=970)

    def test_reveal_at_timeout_height_succeeds(self):
        """House CAN reveal at exactly timeoutHeight (last block)."""
        secret = os.urandom(32)
        block_id = os.urandom(32)
        timeout = 1000
        c = make_contract(secret=secret, timeout=timeout)
        # Reveal at exactly timeout
        flip = c.compute_rng(block_id)
        if flip == c.player_choice:
            assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                c.compute_win_payout(), reveal_height=timeout)
        else:
            assert c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                c.bet_amount, reveal_height=timeout)

    def test_reveal_after_timeout_fails(self):
        """House CANNOT reveal after timeoutHeight — falls to refund."""
        secret = os.urandom(32)
        block_id = os.urandom(32)
        timeout = 1000
        c = make_contract(secret=secret, timeout=timeout)
        # Try at 1001 (after timeout)
        assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                c.compute_win_payout(), reveal_height=1001)

    def test_reveal_window_is_30_blocks(self):
        """Default reveal window should be 30 blocks (timeout - rng_height)."""
        c = make_contract(timeout=1000, rng_height=970)
        window = c.timeout_height - c.rng_block_height
        assert window == 30

    def test_grinding_window_limited(self):
        """With 30-block window, house has at most 30 blocks to grind."""
        # Simulate: house tries 30 different blocks
        secret = os.urandom(32)
        c = make_contract(secret=secret, timeout=1000, rng_height=970)
        results = set()
        for h in range(970, 1001):
            block_id = h.to_bytes(32, 'big')
            results.add(c.compute_rng(block_id))
        # Should see both outcomes across 30 blocks (probabilistically)
        assert len(results) == 2, \
            f"Only one outcome across 30 blocks — grinding trivial: {results}"

    def test_tight_window_still_allows_both_outcomes(self):
        """Even a 10-block window should produce both outcomes."""
        secret = os.urandom(32)
        c = make_contract(secret=secret, timeout=980, rng_height=970)
        results = set()
        for h in range(970, 981):
            block_id = h.to_bytes(32, 'big')
            results.add(c.compute_rng(block_id))
        # 10 blocks should still see both outcomes (probabilistically)
        # This is a soft check — sometimes it misses, so we accept single-outcome
        # but flag it as a concern
        if len(results) == 1:
            pytest.xfail("10-block window produced only one outcome — "
                         "acceptable probabilistically but watch in production")
        else:
            assert len(results) == 2


# ═══════════════════════════════════════════════════════════════════════
# TEST: Refund Path
# ═══════════════════════════════════════════════════════════════════════

class TestRefundPath:

    def test_refund_after_timeout_succeeds(self):
        """Player can refund after timeout with >= 0.98x bet."""
        c = make_contract(height=1001)
        refund = c.compute_refund_amount()
        assert c.can_refund(PLAYER_PK, PLAYER_PK, refund)

    def test_refund_before_timeout_fails(self):
        """Player cannot refund before timeout height."""
        c = make_contract(height=999)
        assert not c.can_refund(PLAYER_PK, PLAYER_PK, 980_000_000)

    def test_refund_at_exact_timeout_succeeds(self):
        """HEIGHT == timeoutHeight should allow refund (>= check)."""
        c = make_contract(height=1000)
        assert c.can_refund(PLAYER_PK, PLAYER_PK, 980_000_000)

    def test_refund_rejects_house_as_spender(self):
        """Only player can refund. House attempting refund should fail."""
        c = make_contract(height=1001)
        assert not c.can_refund(HOUSE_PK, PLAYER_PK, 980_000_000)

    def test_refund_rejects_insufficient_amount(self):
        """Refund paying less than 0.98x should fail."""
        c = make_contract(height=1001, bet=1_000_000_000)
        assert not c.can_refund(PLAYER_PK, PLAYER_PK, 979_999_999)

    def test_refund_accepts_overpayment(self):
        """Refund paying MORE than 0.98x should succeed (>= check)."""
        c = make_contract(height=1001)
        assert c.can_refund(PLAYER_PK, PLAYER_PK, 1_000_000_000)

    def test_refund_rejects_wrong_recipient(self):
        """Refund must go to player, not house."""
        c = make_contract(height=1001)
        assert not c.can_refund(PLAYER_PK, HOUSE_PK, 980_000_000)


# ═══════════════════════════════════════════════════════════════════════
# TEST: End-to-End Game Flows
# ═══════════════════════════════════════════════════════════════════════

class TestEndToEnd:

    def test_full_game_player_wins(self):
        """Complete game: commit -> reveal -> player wins -> payout."""
        secret = os.urandom(32)
        choice = 0  # heads
        bet = 5_000_000_000  # 5 ERG

        c = make_contract(secret=secret, choice=choice, bet=bet)

        # Find block within reveal window that makes player win
        for h in range(970, 1001):
            block_id = h.to_bytes(32, 'big')
            if c.compute_rng(block_id) == choice:
                win_payout = c.compute_win_payout()
                # Reveal succeeds
                assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                    win_payout, reveal_height=h)
                # House can't steal by paying itself
                assert not c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                        win_payout, reveal_height=h)
                # Refund not available (reveal happened before timeout)
                c.current_height = h
                assert not c.can_refund(PLAYER_PK, PLAYER_PK, win_payout)
                return
        pytest.fail("No player-winning block in reveal window")

    def test_full_game_house_wins(self):
        """Complete game: commit -> reveal -> house wins -> house keeps bet."""
        secret = os.urandom(32)
        choice = 1  # tails
        bet = 3_000_000_000  # 3 ERG

        c = make_contract(secret=secret, choice=choice, bet=bet)

        for h in range(970, 1001):
            block_id = h.to_bytes(32, 'big')
            if c.compute_rng(block_id) != choice:
                # House wins
                assert c.can_reveal(HOUSE_PK, block_id, HOUSE_PK,
                                    bet, reveal_height=h)
                # Player doesn't get paid
                assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                        c.compute_win_payout(), reveal_height=h)
                return
        pytest.fail("No house-winning block in reveal window")

    def test_full_game_timeout_refund(self):
        """Game times out: player reclaims 98% of bet."""
        secret = os.urandom(32)
        bet = 2_000_000_000  # 2 ERG
        timeout = 100

        c = make_contract(secret=secret, bet=bet, timeout=timeout,
                          rng_height=70, height=50)

        # Before timeout — no refund
        assert not c.can_refund(PLAYER_PK, PLAYER_PK, 1_960_000_000)

        # Before rng_height — house can't reveal either
        assert not c.can_reveal(HOUSE_PK, os.urandom(32), PLAYER_PK,
                                c.compute_win_payout(), reveal_height=60)

        # After timeout — refund available
        c.current_height = 101
        expected_refund = 1_960_000_000  # 2 ERG * 0.98
        assert c.compute_refund_amount() == expected_refund
        assert c.can_refund(PLAYER_PK, PLAYER_PK, expected_refund)

    def test_game_between_commit_and_reveal_window(self):
        """Between bet creation and rngBlockHeight, nothing can happen."""
        secret = os.urandom(32)
        c = make_contract(secret=secret, height=500, timeout=1000,
                          rng_height=970)

        # House tries to reveal early (height 500 < rng_height 970)
        block_id = os.urandom(32)
        assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                c.compute_win_payout(), reveal_height=500)

        # Player tries to refund early (height 500 < timeout 1000)
        assert not c.can_refund(PLAYER_PK, PLAYER_PK, 980_000_000)


# ═══════════════════════════════════════════════════════════════════════
# TEST: Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_empty_secret(self):
        """Empty secret (0 bytes) — commitment should still work mathematically."""
        secret = b''
        c = make_contract(secret=secret)
        assert c.verify_commitment()

    def test_single_byte_secret(self):
        """1-byte secret — minimum entropy but valid."""
        secret = b'\x42'
        c = make_contract(secret=secret)
        assert c.verify_commitment()

    def test_large_secret(self):
        """256-byte secret — no length restriction in contract."""
        secret = os.urandom(256)
        c = make_contract(secret=secret)
        assert c.verify_commitment()

    def test_choice_outside_0_1_maps_to_tails(self):
        """choice=2 produces choice_byte=1 (else branch), same as tails."""
        secret = os.urandom(32)
        commitment_for_2 = make_commitment(secret, 2)
        commitment_for_1 = make_commitment(secret, 1)
        assert commitment_for_2 == commitment_for_1

    def test_zero_bet(self):
        """Zero bet — edge case. Payouts compute to 0."""
        c = make_contract(bet=0)
        assert c.compute_win_payout() == 0
        assert c.compute_refund_amount() == 0

    def test_same_keys_house_and_player(self):
        """house PK == player PK: both paths would work for same PK.
        This is a known issue — production should enforce PK != PK."""
        pk = PLAYER_PK
        secret = os.urandom(32)
        commitment = make_commitment(secret, 0)
        c = CoinflipV3(pk, pk, commitment, 0,
                        1000, secret, 1_000_000_000, 1001, 970)
        # Both reveal and refund would work for this PK (known limitation)
        block_id = os.urandom(32)
        # We don't assert here, just verify no crash
        c.can_reveal(pk, block_id, pk, c.compute_win_payout(), 980)
        c.can_refund(pk, pk, c.compute_refund_amount())

    def test_reveal_window_zero_blocks(self):
        """rng_height == timeout means no reveal window at all."""
        c = make_contract(timeout=1000, rng_height=1000)
        # Can only reveal at exactly height 1000
        block_id = os.urandom(32)
        assert not c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                c.compute_win_payout(), reveal_height=999)
        # At 1000 it should work (if commitment is valid and within window)
        # Note: height 1000 is both rng_height AND timeout, so reveal works
        flip = c.compute_rng(block_id)
        if flip == c.player_choice:
            assert c.can_reveal(HOUSE_PK, block_id, PLAYER_PK,
                                c.compute_win_payout(), reveal_height=1000)
        # After timeout (1001), refund kicks in
        c.current_height = 1001
        assert c.can_refund(PLAYER_PK, PLAYER_PK, c.compute_refund_amount())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
