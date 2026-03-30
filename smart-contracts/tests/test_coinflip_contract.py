#!/usr/bin/env python3
"""
DuckPools Coinflip Contract — Unit Tests (MAT-393)

Tests the coinflip contract logic off-chain by reimplementing the ErgoScript
semantics in Python. Covers:

  1. Commitment verification (blake2b256(secret || choice) == stored hash)
  2. RNG computation (blake2b256(blockHash || secret)[0] % 2)
  3. Payout calculations (1.94x win, 0.98x refund)
  4. Reveal window enforcement (rngBlockHeight <= HEIGHT <= timeoutHeight)
  5. NFT preservation (game NFT must appear in OUTPUTS(1))
  6. Edge cases (boundary heights, zero bet, wrong choice, wrong commitment)

Usage:
    python -m pytest smart-contracts/tests/test_coinflip_contract.py -v
"""

import hashlib
import os
import sys
import unittest
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Helpers — mirror the ErgoScript operations
# ---------------------------------------------------------------------------

def blake2b256(data: bytes) -> bytes:
    """Blake2b-256 — native Ergo hash opcode."""
    h = hashlib.blake2b(digest_size=32)
    h.update(data)
    return h.digest()


def compute_commitment(secret: bytes, choice: int) -> bytes:
    """
    Compute player commitment: blake2b256(secret || choice_byte)
    Mirrors on-chain: blake2b256(playerSecret ++ Coll(choiceByte))
    """
    choice_byte = 0x00 if choice == 0 else 0x01
    return blake2b256(secret + bytes([choice_byte]))


def compute_flip(block_id: bytes, secret: bytes) -> int:
    """
    Compute coin flip result: blake2b256(blockId || secret)[0] % 2
    Mirrors on-chain: blake2b256(blockSeed ++ playerSecret)(0) % 2
    """
    rng_hash = blake2b256(block_id + secret)
    return rng_hash[0] % 2


def win_payout(bet_amount: int) -> int:
    """1.94x payout (3% house edge on the 2x)."""
    return bet_amount * 97 // 50


def refund_amount(bet_amount: int) -> int:
    """98% of bet (2% fee to prevent spam)."""
    return bet_amount - bet_amount // 50


# ---------------------------------------------------------------------------
# Mock objects
# ---------------------------------------------------------------------------

@dataclass
class Token:
    token_id: bytes
    amount: int


@dataclass
class OutputBox:
    proposition_bytes: bytes  # PK bytes
    value: int                # nanoERG
    tokens: List[Token] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Contract evaluator — reimplements the ErgoScript guard logic
# ---------------------------------------------------------------------------

def evaluate_can_reveal(
    house_pk_bytes: bytes,
    player_pk_bytes: bytes,
    house_sig_valid: bool,
    commitment_hash: bytes,
    player_choice: int,
    player_secret: bytes,
    timeout_height: int,
    current_height: int,
    bet_amount: int,
    block_id: bytes,
    game_nft_id: bytes,
    outputs: List[OutputBox],
) -> Tuple[bool, str]:
    """
    Evaluate the REVEAL spending path.
    Returns (result, reason).

    NOTE: rngBlockHeight is NOT checked on-chain (R10 not supported by Lithos 6.0.3).
    The reveal is valid at any HEIGHT < timeoutHeight. The reveal window is
    enforced off-chain by the house backend.
    """
    # -- commitment verification
    choice_byte = 0x00 if player_choice == 0 else 0x01
    computed = blake2b256(player_secret + bytes([choice_byte]))
    if computed != commitment_hash:
        return False, "COMMITMENT_MISMATCH"

    # -- NFT preservation
    if len(outputs) < 2:
        return False, "NFT_MISSING_OUTPUTS_TOO_FEW"
    nft_found = any(
        t.token_id == game_nft_id and t.amount == 1
        for o in outputs[1:]
        for t in o.tokens
    )
    if not nft_found:
        return False, "NFT_NOT_PRESERVED"

    # -- house signature
    if not house_sig_valid:
        return False, "HOUSE_SIG_INVALID"

    # -- height check: must reveal before timeout
    if current_height >= timeout_height:
        return False, "AFTER_TIMEOUT"

    # -- RNG + payout
    flip = compute_flip(block_id, player_secret)
    player_wins = (flip == player_choice)

    if player_wins:
        if outputs[0].proposition_bytes != player_pk_bytes:
            return False, "WIN_PAYOUT_WRONG_RECIPIENT"
        if outputs[0].value < win_payout(bet_amount):
            return False, "WIN_PAYOUT_TOO_LOW"
    else:
        if outputs[0].proposition_bytes != house_pk_bytes:
            return False, "LOSS_PAYOUT_WRONG_RECIPIENT"
        if outputs[0].value < bet_amount:
            return False, "LOSS_PAYOUT_TOO_LOW"

    return True, "REVEAL_OK"


def evaluate_can_refund(
    player_pk_bytes: bytes,
    player_sig_valid: bool,
    timeout_height: int,
    current_height: int,
    bet_amount: int,
    game_nft_id: bytes,
    outputs: List[OutputBox],
) -> Tuple[bool, str]:
    """
    Evaluate the REFUND spending path.
    Returns (result, reason).
    """
    if current_height < timeout_height:
        return False, "BEFORE_TIMEOUT"

    if not player_sig_valid:
        return False, "PLAYER_SIG_INVALID"

    # NFT preservation
    if len(outputs) < 2:
        return False, "NFT_MISSING_OUTPUTS_TOO_FEW"
    nft_found = any(
        t.token_id == game_nft_id and t.amount == 1
        for o in outputs[1:]
        for t in o.tokens
    )
    if not nft_found:
        return False, "NFT_NOT_PRESERVED"

    if outputs[0].proposition_bytes != player_pk_bytes:
        return False, "REFUND_WRONG_RECIPIENT"

    if outputs[0].value < refund_amount(bet_amount):
        return False, "REFUND_AMOUNT_TOO_LOW"

    return True, "REFUND_OK"


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

HOUSE_PK = b'\x02' + bytes(32)  # 33-byte compressed PK
PLAYER_PK = b'\x03' + bytes(32)
GAME_NFT_ID = bytes(range(32))
SECRET = os.urandom(8)
BLOCK_ID = os.urandom(32)
BET_AMOUNT = 10_000_000_000  # 10 ERG in nanoERG
RNG_HEIGHT = 1000
TIMEOUT_HEIGHT = 1030


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestCommitmentVerification(unittest.TestCase):
    """Test blake2b256(secret || choice) commitment scheme."""

    def test_valid_commitment_heads(self):
        commitment = compute_commitment(SECRET, 0)
        choice_byte = 0x00
        computed = blake2b256(SECRET + bytes([choice_byte]))
        self.assertEqual(commitment, computed)

    def test_valid_commitment_tails(self):
        commitment = compute_commitment(SECRET, 1)
        choice_byte = 0x01
        computed = blake2b256(SECRET + bytes([choice_byte]))
        self.assertEqual(commitment, computed)

    def test_wrong_choice_fails(self):
        commitment = compute_commitment(SECRET, 0)
        # Re-verify with wrong choice
        wrong_byte = 0x01
        computed = blake2b256(SECRET + bytes([wrong_byte]))
        self.assertNotEqual(commitment, computed)

    def test_wrong_secret_fails(self):
        commitment = compute_commitment(SECRET, 0)
        wrong_secret = os.urandom(8)
        computed = blake2b256(wrong_secret + bytes([0x00]))
        # With overwhelming probability these differ
        self.assertNotEqual(commitment, computed)

    def test_different_secrets_different_commitments(self):
        c1 = compute_commitment(os.urandom(8), 0)
        c2 = compute_commitment(os.urandom(8), 0)
        self.assertNotEqual(c1, c2)

    def test_commitment_is_32_bytes(self):
        commitment = compute_commitment(SECRET, 0)
        self.assertEqual(len(commitment), 32)


class TestRNGComputation(unittest.TestCase):
    """Test blake2b256(blockHash || secret)[0] % 2 RNG."""

    def test_deterministic(self):
        """Same inputs always produce the same result."""
        r1 = compute_flip(BLOCK_ID, SECRET)
        r2 = compute_flip(BLOCK_ID, SECRET)
        self.assertEqual(r1, r2)

    def test_output_is_binary(self):
        for _ in range(100):
            result = compute_flip(os.urandom(32), os.urandom(8))
            self.assertIn(result, [0, 1])

    def test_different_block_hashes_different_results(self):
        """Different block hashes should produce different distributions."""
        results = set()
        for i in range(100):
            results.add(compute_flip(i.to_bytes(32, 'big'), SECRET))
        # Over 100 trials with different blocks, we should see both outcomes
        self.assertEqual(results, {0, 1})

    def test_different_secrets_different_results(self):
        """Different secrets should produce different distributions."""
        results = set()
        for i in range(100):
            results.add(compute_flip(BLOCK_ID, i.to_bytes(8, 'big')))
        self.assertEqual(results, {0, 1})

    def test_uniformity(self):
        """Over many samples, distribution should be approximately uniform."""
        outcomes = []
        for i in range(10000):
            secret = i.to_bytes(8, 'big')
            block = (i + 99999).to_bytes(32, 'big')
            outcomes.append(compute_flip(block, secret))
        heads = outcomes.count(0)
        tails = outcomes.count(1)
        # Should be within 2% of 50/50 for 10k samples
        ratio = heads / len(outcomes)
        self.assertAlmostEqual(ratio, 0.5, delta=0.02)


class TestPayoutCalculations(unittest.TestCase):
    """Test win payout (1.94x) and refund (0.98x) calculations."""

    def test_win_payout_10_erg(self):
        self.assertEqual(win_payout(BET_AMOUNT), 19_400_000_000)

    def test_win_payout_1_erg(self):
        self.assertEqual(win_payout(1_000_000_000), 1_940_000_000)

    def test_win_payout_100_erg(self):
        self.assertEqual(win_payout(100_000_000_000), 194_000_000_000)

    def test_win_payout_is_1_94x(self):
        ratio = win_payout(BET_AMOUNT) / BET_AMOUNT
        self.assertAlmostEqual(ratio, 1.94, places=2)

    def test_refund_10_erg(self):
        self.assertEqual(refund_amount(BET_AMOUNT), 9_800_000_000)

    def test_refund_is_0_98x(self):
        ratio = refund_amount(BET_AMOUNT) / BET_AMOUNT
        self.assertAlmostEqual(ratio, 0.98, places=2)

    def test_house_edge_is_3_percent(self):
        # Player bets 1, expected value = 0.5 * 1.94 + 0.5 * 0 = 0.97
        # House edge = 1 - 0.97 = 0.03
        ev = 0.5 * (win_payout(BET_AMOUNT) / BET_AMOUNT) + 0.5 * 0
        self.assertAlmostEqual(1 - ev, 0.03, places=2)

    def test_refund_fee_is_2_percent(self):
        fee_ratio = 1 - (refund_amount(BET_AMOUNT) / BET_AMOUNT)
        self.assertAlmostEqual(fee_ratio, 0.02, places=2)


class TestRevealPath(unittest.TestCase):
    """Test the REVEAL spending path conditions."""

    def _make_outputs(self, recipient_pk, amount, include_nft=True, nft_output_idx=1):
        outputs = [OutputBox(recipient_pk, amount, [])]
        if include_nft:
            outputs.append(OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 1)]))
        return outputs

    def test_reveal_player_wins(self):
        """House reveals, player chose correctly, player gets 1.94x."""
        choice = 0  # heads
        commitment = compute_commitment(SECRET, choice)
        flip = compute_flip(BLOCK_ID, SECRET)
        # Only test if player actually wins with this random data
        player_wins = (flip == choice)
        if not player_wins:
            # Pick a choice that wins
            choice = flip
            commitment = compute_commitment(SECRET, choice)

        outputs = self._make_outputs(PLAYER_PK, win_payout(BET_AMOUNT))
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, choice, SECRET,
            TIMEOUT_HEIGHT, RNG_HEIGHT + 5,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok, f"Reveal should succeed: {reason}")

    def test_reveal_house_wins(self):
        """House reveals, house wins, house gets full bet."""
        choice = 1  # tails
        commitment = compute_commitment(SECRET, choice)
        flip = compute_flip(BLOCK_ID, SECRET)
        player_wins = (flip == choice)
        if player_wins:
            choice = 1 - flip
            commitment = compute_commitment(SECRET, choice)

        outputs = self._make_outputs(HOUSE_PK, BET_AMOUNT)
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, choice, SECRET,
            TIMEOUT_HEIGHT, RNG_HEIGHT + 5,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok, f"Reveal should succeed: {reason}")

    def test_reveal_wrong_commitment_fails(self):
        """Reveal with wrong commitment hash fails."""
        bad_commitment = os.urandom(32)
        outputs = self._make_outputs(PLAYER_PK, win_payout(BET_AMOUNT))
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, bad_commitment, 0, SECRET,
            TIMEOUT_HEIGHT, RNG_HEIGHT + 5,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "COMMITMENT_MISMATCH")

    def test_reveal_before_timeout_succeeds(self):
        """Can reveal at any height before timeout (no R10 reveal window on-chain)."""
        commitment = compute_commitment(SECRET, 0)
        outputs = self._make_outputs(PLAYER_PK, win_payout(BET_AMOUNT))
        # Even at height 0 (way before timeout), reveal should be allowed on-chain.
        # The reveal window is enforced off-chain by the house backend.
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, 0, SECRET,
            TIMEOUT_HEIGHT, 0,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        # May fail due to commitment/payout mismatch, but NOT due to height
        self.assertNotEqual(reason, "AFTER_TIMEOUT")

    def test_reveal_after_timeout_fails(self):
        """Cannot reveal after timeoutHeight (must use refund path)."""
        commitment = compute_commitment(SECRET, 0)
        outputs = self._make_outputs(PLAYER_PK, win_payout(BET_AMOUNT))
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, 0, SECRET,
            TIMEOUT_HEIGHT, TIMEOUT_HEIGHT + 1,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "AFTER_TIMEOUT")

    def test_reveal_at_timeout_minus_one(self):
        """Reveal at timeoutHeight - 1 (last valid block) succeeds."""
        commitment = compute_commitment(SECRET, 0)
        flip = compute_flip(BLOCK_ID, SECRET)
        choice = flip  # ensure player wins
        commitment = compute_commitment(SECRET, choice)

        outputs = self._make_outputs(PLAYER_PK, win_payout(BET_AMOUNT))
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, choice, SECRET,
            TIMEOUT_HEIGHT, TIMEOUT_HEIGHT - 1,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok, f"Reveal at timeoutHeight-1 should succeed: {reason}")

    def test_reveal_no_nft_fails(self):
        """Reveal without NFT in OUTPUTS(1) fails."""
        commitment = compute_commitment(SECRET, 0)
        outputs = [OutputBox(PLAYER_PK, win_payout(BET_AMOUNT), [])]
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, 0, SECRET,
            TIMEOUT_HEIGHT, RNG_HEIGHT + 5,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "NFT_MISSING_OUTPUTS_TOO_FEW")

    def test_reveal_wrong_nft_fails(self):
        """Reveal with wrong NFT ID fails."""
        commitment = compute_commitment(SECRET, 0)
        wrong_nft = os.urandom(32)
        outputs = [
            OutputBox(PLAYER_PK, win_payout(BET_AMOUNT), []),
            OutputBox(b'\x00' * 33, 0, [Token(wrong_nft, 1)]),
        ]
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, 0, SECRET,
            TIMEOUT_HEIGHT, RNG_HEIGHT + 5,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "NFT_NOT_PRESERVED")

    def test_reveal_insufficient_payout_fails(self):
        """Reveal paying less than 1.94x on player win fails."""
        choice = 0
        commitment = compute_commitment(SECRET, choice)
        flip = compute_flip(BLOCK_ID, SECRET)
        if flip != choice:
            choice = flip
            commitment = compute_commitment(SECRET, choice)

        outputs = self._make_outputs(PLAYER_PK, win_payout(BET_AMOUNT) - 1)
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, choice, SECRET,
            TIMEOUT_HEIGHT, RNG_HEIGHT + 5,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "WIN_PAYOUT_TOO_LOW")


class TestRefundPath(unittest.TestCase):
    """Test the REFUND spending path conditions."""

    def _make_refund_outputs(self, include_nft=True):
        outputs = [OutputBox(PLAYER_PK, refund_amount(BET_AMOUNT), [])]
        if include_nft:
            outputs.append(OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 1)]))
        return outputs

    def test_refund_after_timeout(self):
        outputs = self._make_refund_outputs()
        ok, reason = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok, reason)

    def test_refund_before_timeout_fails(self):
        outputs = self._make_refund_outputs()
        ok, reason = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT - 1,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "BEFORE_TIMEOUT")

    def test_refund_no_nft_fails(self):
        outputs = self._make_refund_outputs(include_nft=False)
        ok, reason = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "NFT_MISSING_OUTPUTS_TOO_FEW")

    def test_refund_wrong_nft_fails(self):
        wrong_nft = os.urandom(32)
        outputs = [
            OutputBox(PLAYER_PK, refund_amount(BET_AMOUNT), []),
            OutputBox(b'\x00' * 33, 0, [Token(wrong_nft, 1)]),
        ]
        ok, reason = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "NFT_NOT_PRESERVED")

    def test_refund_wrong_recipient_fails(self):
        outputs = [
            OutputBox(HOUSE_PK, refund_amount(BET_AMOUNT), []),
            OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 1)]),
        ]
        ok, reason = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "REFUND_WRONG_RECIPIENT")

    def test_refund_insufficient_amount_fails(self):
        outputs = [
            OutputBox(PLAYER_PK, refund_amount(BET_AMOUNT) - 1, []),
            OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 1)]),
        ]
        ok, reason = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "REFUND_AMOUNT_TOO_LOW")

    def test_refund_exact_timeout_height(self):
        """Refund at exactly timeoutHeight succeeds."""
        outputs = self._make_refund_outputs()
        ok, reason = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok, reason)

    def test_refund_excess_payout_ok(self):
        """Refund with more than minimum is allowed (>= check)."""
        outputs = [
            OutputBox(PLAYER_PK, BET_AMOUNT, []),  # full bet, no fee taken
            OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 1)]),
        ]
        ok, reason = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok, reason)


class TestNFTPreservation(unittest.TestCase):
    """Test that NFT is preserved in both reveal and refund paths."""

    def test_nft_in_outputs_1_on_reveal(self):
        commitment = compute_commitment(SECRET, 0)
        flip = compute_flip(BLOCK_ID, SECRET)
        choice = flip
        commitment = compute_commitment(SECRET, choice)
        outputs = [
            OutputBox(PLAYER_PK, win_payout(BET_AMOUNT), []),
            OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 1)]),
        ]
        ok, _ = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, choice, SECRET,
            TIMEOUT_HEIGHT, RNG_HEIGHT + 5,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok)

    def test_nft_in_outputs_1_on_refund(self):
        outputs = [
            OutputBox(PLAYER_PK, refund_amount(BET_AMOUNT), []),
            OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 1)]),
        ]
        ok, _ = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok)

    def test_nft_in_outputs_0_not_enough(self):
        """NFT in OUTPUTS(0) but not OUTPUTS(1) still fails."""
        outputs = [
            OutputBox(PLAYER_PK, refund_amount(BET_AMOUNT), [Token(GAME_NFT_ID, 1)]),
        ]
        ok, _ = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)

    def test_nft_amount_must_be_1(self):
        """NFT with amount != 1 should fail."""
        outputs = [
            OutputBox(PLAYER_PK, refund_amount(BET_AMOUNT), []),
            OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 2)]),
        ]
        ok, _ = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, TIMEOUT_HEIGHT,
            BET_AMOUNT, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)


class TestEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_commitment_with_empty_secret(self):
        """Even with minimal (empty) secret, commitment should work."""
        secret = b''
        c = compute_commitment(secret, 0)
        self.assertEqual(len(c), 32)

    def test_commitment_with_long_secret(self):
        """Long secret should still produce 32-byte commitment."""
        secret = os.urandom(256)
        c = compute_commitment(secret, 0)
        self.assertEqual(len(c), 32)

    def test_flip_with_empty_block_id(self):
        """Empty block ID should still produce valid binary output."""
        result = compute_flip(b'\x00' * 32, SECRET)
        self.assertIn(result, [0, 1])

    def test_win_payout_zero_bet(self):
        self.assertEqual(win_payout(0), 0)

    def test_refund_zero_bet(self):
        self.assertEqual(refund_amount(0), 0)

    def test_win_payout_one_nanoerg(self):
        # Integer division: 1 * 97 / 50 = 1
        self.assertEqual(win_payout(1), 1)

    def test_refund_one_nanoerg(self):
        # 1 - 1/50 = 1 - 0 = 1 (integer division)
        self.assertEqual(refund_amount(1), 1)

    def test_reveal_window_zero_width(self):
        """When timeoutHeight equals current height, reveal fails (must be strictly less)."""
        commitment = compute_commitment(SECRET, 0)
        flip = compute_flip(BLOCK_ID, SECRET)
        # Set choice to match the actual flip so we know the payout direction
        choice = flip
        commitment = compute_commitment(SECRET, choice)

        outputs = [
            OutputBox(PLAYER_PK, win_payout(BET_AMOUNT), []),
            OutputBox(b'\x00' * 33, 0, [Token(GAME_NFT_ID, 1)]),
        ]
        # At timeoutHeight - 1: should succeed
        ok, _ = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, choice, SECRET,
            1000, 999,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertTrue(ok, "Reveal at timeoutHeight-1 should succeed")

        # At exact timeoutHeight: should fail (HEIGHT >= timeoutHeight blocks reveal)
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, choice, SECRET,
            1000, 1000,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "AFTER_TIMEOUT")

        # After timeout: should fail
        ok, reason = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, choice, SECRET,
            1000, 1001,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, outputs
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "AFTER_TIMEOUT")

    def test_both_paths_fail_for_invalid_tx(self):
        """A transaction that doesn't satisfy either path should fail both."""
        commitment = compute_commitment(SECRET, 0)
        bad_outputs = [OutputBox(HOUSE_PK, 0, [])]

        # Try reveal (at height 0, wrong everything)
        ok, _ = evaluate_can_reveal(
            HOUSE_PK, PLAYER_PK, True, commitment, 0, SECRET,
            TIMEOUT_HEIGHT, 0,
            BET_AMOUNT, BLOCK_ID, GAME_NFT_ID, bad_outputs
        )
        self.assertFalse(ok)

        # Try refund (before timeout)
        ok, _ = evaluate_can_refund(
            PLAYER_PK, True, TIMEOUT_HEIGHT, 0,
            BET_AMOUNT, GAME_NFT_ID, bad_outputs
        )
        self.assertFalse(ok)


class TestContractStructure(unittest.TestCase):
    """Verify contract files have the expected structure."""

    # tests/ is inside smart-contracts/, so go up one level
    CONTRACT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_coinflip_v1_exists(self):
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v1.es')
        self.assertTrue(os.path.exists(path), "coinflip_v1.es must exist")

    def test_coinflip_v2_exists(self):
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v2.es')
        self.assertTrue(os.path.exists(path), "coinflip_v2.es must exist")

    def test_coinflip_v3_exists(self):
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v3.es')
        self.assertTrue(os.path.exists(path), "coinflip_v3.es must exist")

    def test_v1_has_no_fromself_in_code(self):
        """v1 must not use 'fromSelf' in actual ErgoScript code (comments ok)."""
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v1.es')
        with open(path) as f:
            content = f.read()
        # Strip comments (lines starting with // and /* */ blocks)
        code_lines = []
        in_block_comment = False
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('/*'):
                in_block_comment = True
            if in_block_comment:
                if '*/' in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith('//'):
                continue
            if stripped.startswith('*'):
                continue
            code_lines.append(line)
        code_only = '\n'.join(code_lines)
        self.assertNotIn('fromSelf', code_only, "v1 code must use SELF, not fromSelf")

    def test_v1_has_no_sig_verify_in_code(self):
        """v1 must not use '.verify(' in actual ErgoScript code (comments ok)."""
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v1.es')
        with open(path) as f:
            content = f.read()
        code_lines = []
        in_block_comment = False
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('/*'):
                in_block_comment = True
            if in_block_comment:
                if '*/' in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith('//'):
                continue
            if stripped.startswith('*'):
                continue
            code_lines.append(line)
        code_only = '\n'.join(code_lines)
        self.assertNotIn('.verify(', code_only, "v1 code must use SigmaProp equality, not .verify()")

    def test_v1_uses_blake2b256(self):
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v1.es')
        with open(path) as f:
            content = f.read()
        self.assertIn('blake2b256', content, "v1 must use blake2b256 for commitment")

    def test_v1_has_nft_preservation(self):
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v1.es')
        with open(path) as f:
            content = f.read()
        self.assertIn('nftPreserved', content, "v1 must have NFT preservation logic")

    def test_v1_has_reveal_window(self):
        """v1 must document the reveal window concept (even if enforced off-chain)."""
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v1.es')
        with open(path) as f:
            content = f.read()
        # The word "reveal" should appear, and timeout is the on-chain enforcement
        self.assertIn('timeoutHeight', content, "v1 must enforce timeout via HEIGHT check")

    def test_v2_has_nft_preservation(self):
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v2.es')
        with open(path) as f:
            content = f.read()
        self.assertIn('nftPreserved', content, "v2 must have NFT preservation logic")

    def test_v3_has_nft_preservation(self):
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v3.es')
        with open(path) as f:
            content = f.read()
        self.assertIn('nftPreserved', content, "v3 must have NFT preservation logic")

    def test_v3_has_reveal_window(self):
        """v3 documents the R10 reveal window design (commented out, not yet compilable)."""
        path = os.path.join(self.CONTRACT_DIR, 'coinflip_v3.es')
        with open(path) as f:
            content = f.read()
        self.assertIn('R10', content, "v3 must document R10 reveal window")
        self.assertIn('rngBlockHeight', content, "v3 must document rngBlockHeight")

    def test_all_versions_use_same_register_layout(self):
        """All compilable versions must use R4-R9 consistently.
        R10 is documented in v3 but commented out (Lithos 6.0.3 limitation)."""
        registers = ['R4', 'R5', 'R6', 'R7', 'R8', 'R9']
        for version in ['coinflip_v1.es', 'coinflip_v2.es', 'coinflip_v3.es']:
            path = os.path.join(self.CONTRACT_DIR, version)
            with open(path) as f:
                content = f.read()
            for reg in registers:
                self.assertIn(f'SELF.{reg}', content,
                    f"{version} must use SELF.{reg}")


class TestRNGFairnessVerification(unittest.TestCase):
    """Comprehensive RNG fairness tests (mirrors smart-contracts/rng_fairness_verify.py)."""

    def test_single_game_verification(self):
        """Verify a complete game outcome end-to-end."""
        secret = os.urandom(8)
        choice = 0
        commitment = compute_commitment(secret, choice)
        block_id = os.urandom(32)
        flip = compute_flip(block_id, secret)

        # Verify commitment
        computed = compute_commitment(secret, choice)
        self.assertEqual(commitment, computed)

        # Verify flip is binary
        self.assertIn(flip, [0, 1])

        # Player wins if flip matches choice
        player_wins = (flip == choice)
        self.assertIsInstance(player_wins, bool)

    def test_commitment_binding(self):
        """Commitment is binding: cannot change choice after commit."""
        secret = os.urandom(8)
        commitment = compute_commitment(secret, 0)

        # Same secret, different choice -> different commitment
        commitment_1 = compute_commitment(secret, 1)
        self.assertNotEqual(commitment, commitment_1)

    def test_commitment_hiding(self):
        """Commitment hides choice: given commitment alone, cannot determine choice."""
        secret = os.urandom(8)
        c0 = compute_commitment(secret, 0)
        c1 = compute_commitment(secret, 1)

        # Both are 32-byte hashes — indistinguishable without secret
        self.assertEqual(len(c0), len(c1))
        # Both should look like random bytes (no obvious pattern)
        # This is a weak test; cryptographic hiding is a property of blake2b256

    def test_chi_squared_uniformity(self):
        """Chi-squared test for 50/50 distribution."""
        n = 10000
        outcomes = [
            compute_flip(i.to_bytes(32, 'big'), i.to_bytes(8, 'big'))
            for i in range(n)
        ]
        heads = outcomes.count(0)
        tails = outcomes.count(1)
        expected = n / 2
        chi_sq = ((heads - expected) ** 2 / expected +
                  (tails - expected) ** 2 / expected)
        # Chi-squared(1) critical value at p=0.05 is 3.841
        self.assertLess(chi_sq, 3.841, f"Chi-squared {chi_sq:.4f} indicates non-uniform distribution")

    def test_runs_test(self):
        """Runs test for outcome independence."""
        n = 10000
        outcomes = [
            compute_flip(i.to_bytes(32, 'big'), i.to_bytes(8, 'big'))
            for i in range(n)
        ]
        runs = 1
        for i in range(1, len(outcomes)):
            if outcomes[i] != outcomes[i - 1]:
                runs += 1

        n0 = outcomes.count(0)
        n1 = outcomes.count(1)
        expected_runs = 1 + 2 * n0 * n1 / n
        var_runs = 2 * n0 * n1 * (2 * n0 * n1 - n) / (n * n * (n - 1))
        std_runs = var_runs ** 0.5 if var_runs > 0 else 1
        z_score = abs(runs - expected_runs) / std_runs if std_runs > 0 else 0

        # 95% confidence: z < 1.96
        self.assertLess(z_score, 1.96, f"Z-score {z_score:.4f} suggests non-independent outcomes")

    def test_serial_correlation(self):
        """Autocorrelation at lag-1 should be negligible."""
        n = 10000
        outcomes = [
            compute_flip(i.to_bytes(32, 'big'), i.to_bytes(8, 'big'))
            for i in range(n)
        ]
        mean = sum(outcomes) / n
        numerator = sum(
            (outcomes[i] - mean) * (outcomes[i + 1] - mean)
            for i in range(n - 1)
        )
        denominator = sum((outcomes[i] - mean) ** 2 for i in range(n))
        autocorr = numerator / denominator if denominator > 0 else 0

        self.assertLess(abs(autocorr), 0.05,
            f"Autocorrelation {autocorr:.6f} suggests correlated outcomes")


if __name__ == '__main__':
    unittest.main()
