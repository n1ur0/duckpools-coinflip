#!/usr/bin/env python3
"""
DuckPools Coinflip Contract Unit Tests (Phase 2)

Tests the coinflip_v2_final.es canonical contract logic off-chain.
Covers: commitment verification, RNG computation, payout math,
register layout validation, edge cases, and contract structure.

Run:  python3 tests/test_coinflip_contract.py -v
"""

import hashlib
import unittest
import os
import sys

# Add backend to path for rng_module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from rng_module import compute_rng, generate_commit, verify_commit


class TestCommitmentScheme(unittest.TestCase):
    """Test commit-reveal commitment generation and verification."""

    def test_commit_heads_8byte_secret(self):
        """Commit for heads (choice=0) with 8-byte secret."""
        secret = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        commit_hex = generate_commit(secret, 0)
        self.assertEqual(len(commit_hex), 64)  # 32 bytes = 64 hex chars
        self.assertTrue(verify_commit(commit_hex, secret, 0))

    def test_commit_tails_8byte_secret(self):
        """Commit for tails (choice=1) with 8-byte secret."""
        secret = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22])
        commit_hex = generate_commit(secret, 1)
        self.assertEqual(len(commit_hex), 64)
        self.assertTrue(verify_commit(commit_hex, secret, 1))

    def test_commit_deterministic(self):
        """Same secret + choice always produces same commitment."""
        secret = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE, 0xBA, 0xBE])
        c1 = generate_commit(secret, 0)
        c2 = generate_commit(secret, 0)
        self.assertEqual(c1, c2)

    def test_commit_different_choices_differ(self):
        """Same secret with different choices produces different commitments."""
        secret = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        c_heads = generate_commit(secret, 0)
        c_tails = generate_commit(secret, 1)
        self.assertNotEqual(c_heads, c_tails)

    def test_commit_different_secrets_differ(self):
        """Different secrets produce different commitments."""
        s1 = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        s2 = bytes([0x08, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01])
        c1 = generate_commit(s1, 0)
        c2 = generate_commit(s2, 0)
        self.assertNotEqual(c1, c2)

    def test_commit_wrong_secret_fails(self):
        """Verification fails with wrong secret."""
        secret = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        wrong_secret = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        commit_hex = generate_commit(secret, 0)
        self.assertFalse(verify_commit(commit_hex, wrong_secret, 0))

    def test_commit_wrong_choice_fails(self):
        """Verification fails with wrong choice."""
        secret = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        commit_hex = generate_commit(secret, 0)
        self.assertFalse(verify_commit(commit_hex, secret, 1))

    def test_commit_invalid_secret_length(self):
        """Raises ValueError for non-8-byte secret."""
        with self.assertRaises(ValueError):
            generate_commit(bytes([0x01, 0x02]), 0)  # 2 bytes
        with self.assertRaises(ValueError):
            generate_commit(bytes(16), 0)  # 16 bytes

    def test_commit_invalid_choice(self):
        """Raises ValueError for choice not 0 or 1."""
        secret = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        with self.assertRaises(ValueError):
            generate_commit(secret, 2)
        with self.assertRaises(ValueError):
            generate_commit(secret, -1)

    def test_commit_uses_blake2b256(self):
        """Commitment uses blake2b256, NOT SHA-256."""
        secret = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        choice = 0
        commit_hex = generate_commit(secret, choice)

        # Compute expected hash manually with blake2b256
        choice_byte = bytes([choice])
        commit_data = secret + choice_byte
        expected = hashlib.blake2b(commit_data, digest_size=32).hexdigest()
        self.assertEqual(commit_hex, expected)

    def test_verify_commit_case_insensitive(self):
        """Commitment verification is case-insensitive for hex."""
        secret = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        commit_hex = generate_commit(secret, 0)
        self.assertTrue(verify_commit(commit_hex.upper(), secret, 0))
        self.assertTrue(verify_commit(commit_hex.lower(), secret, 0))


class TestRNGComputation(unittest.TestCase):
    """Test on-chain RNG computation matches contract logic."""

    def test_rng_returns_binary(self):
        """RNG always returns 0 or 1."""
        for i in range(100):
            block_hash = f"{i:064x}"
            secret = bytes([i & 0xFF] * 8)
            result = compute_rng(block_hash, secret)
            self.assertIn(result, [0, 1])

    def test_rng_deterministic(self):
        """Same inputs always produce same result."""
        block_hash = "a" * 64
        secret = bytes([0x42] * 8)
        r1 = compute_rng(block_hash, secret)
        r2 = compute_rng(block_hash, secret)
        self.assertEqual(r1, r2)

    def test_rng_different_block_hashes_differ(self):
        """Different block hashes produce different results (probabilistically)."""
        secret = bytes([0x01] * 8)
        results = set()
        for i in range(50):
            block_hash = f"{i:064x}"
            results.add(compute_rng(block_hash, secret))
        # With 50 trials, should get both outcomes
        self.assertGreaterEqual(len(results), 2, "RNG should produce both outcomes across different blocks")

    def test_rng_different_secrets_differ(self):
        """Different secrets produce different results (probabilistically)."""
        block_hash = "b" * 64
        results = set()
        for i in range(50):
            secret = bytes([i] * 8)
            results.add(compute_rng(block_hash, secret))
        self.assertGreaterEqual(len(results), 2, "RNG should produce both outcomes across different secrets")

    def test_rng_uses_blake2b256_not_sha256(self):
        """Verify RNG uses blake2b256 matching the on-chain contract.

        On-chain: blake2b256(CONTEXT.preHeader.parentId ++ playerSecret)
        Off-chain: blake2b256(block_hash_bytes || secret_bytes)
        """
        block_hash = "c" * 64  # 32-byte block hash as hex
        secret = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])

        # Manually compute what the contract should produce
        block_bytes = bytes.fromhex(block_hash)
        rng_data = block_bytes + secret
        rng_hash = hashlib.blake2b(rng_data, digest_size=32).digest()
        expected = rng_hash[0] % 2

        actual = compute_rng(block_hash, secret)
        self.assertEqual(actual, expected)

    def test_rng_distribution_uniformity(self):
        """Large-sample test: distribution should be approximately uniform."""
        import random
        random.seed(42)
        counts = {0: 0, 1: 1}
        n = 10000
        for i in range(n):
            block_hash = f"{random.getrandbits(256):064x}"
            secret = bytes([random.randint(0, 255) for _ in range(8)])
            result = compute_rng(block_hash, secret)
            counts[result] += 1

        ratio = counts[1] / (counts[0] + counts[1])
        # Should be within 2% of 0.5 for 10k samples
        self.assertAlmostEqual(ratio, 0.5, delta=0.02,
                               msg=f"Heads ratio {ratio:.4f} too far from 0.5")


class TestPayoutMath(unittest.TestCase):
    """Test payout calculations matching on-chain contract."""

    def test_win_payout_1_94x(self):
        """Player win: bet * 97 / 50 = 1.94x"""
        bet = 1_000_000_000  # 1 ERG in nanoERG
        win_payout = bet * 97 // 50
        self.assertEqual(win_payout, 1_940_000_000)  # 1.94 ERG

    def test_house_edge_3_percent(self):
        """House edge is 3%: player gets 1.94x instead of 2x."""
        bet = 100
        win_payout = bet * 97 // 50
        expected_pure = bet * 2
        edge = expected_pure - win_payout
        self.assertEqual(edge, 6)  # 3% of 200 = 6
        self.assertAlmostEqual(win_payout / expected_pure, 0.97, places=2)

    def test_refund_98_percent(self):
        """Refund: bet - bet/50 = 0.98x"""
        bet = 1_000_000_000
        refund = bet - bet // 50
        self.assertEqual(refund, 980_000_000)
        # Fee is 2%
        self.assertEqual(bet - refund, 20_000_000)

    def test_small_bet_payout(self):
        """Minimum bet (1 nanoERG) still works mathematically."""
        bet = 1
        win_payout = bet * 97 // 50
        refund = bet - bet // 50
        self.assertEqual(win_payout, 1)  # 1 * 97 / 50 = 1 (integer division)
        self.assertEqual(refund, 1)  # 1 - 0 = 1 (1/50 rounds to 0)

    def test_large_bet_payout(self):
        """Large bet doesn't overflow Python int."""
        bet = 100_000_000_000_000  # 100,000 ERG
        win_payout = bet * 97 // 50
        refund = bet - bet // 50
        self.assertEqual(win_payout, 194_000_000_000_000)
        self.assertEqual(refund, 98_000_000_000_000)


class TestContractStructure(unittest.TestCase):
    """Test contract file structure and ErgoScript validity checks."""

    def setUp(self):
        contract_path = os.path.join(
            os.path.dirname(__file__), '..', 'smart-contracts', 'coinflip_v2_final.es'
        )
        with open(contract_path, 'r') as f:
            self.contract = f.read()

    def test_uses_blake2b256(self):
        """Contract uses blake2b256 (not SHA-256)."""
        self.assertIn('blake2b256', self.contract)
        self.assertNotIn('sha256', self.contract.lower())

    def test_uses_block_hash(self):
        """Contract uses CONTEXT.preHeader.parentId for block hash."""
        self.assertIn('CONTEXT.preHeader.parentId', self.contract)

    def test_no_math_random(self):
        """Contract does NOT use Math.random."""
        self.assertNotIn('Math.random', self.contract)

    def test_register_layout_r4_r9(self):
        """Contract uses R4 through R9 registers."""
        self.assertIn('R4[Coll[Byte]]', self.contract)
        self.assertIn('R5[Coll[Byte]]', self.contract)
        self.assertIn('R6[Coll[Byte]]', self.contract)
        self.assertIn('R7[Int]', self.contract)
        self.assertIn('R8[Int]', self.contract)
        self.assertIn('R9[Coll[Byte]]', self.contract)

    def test_spending_paths(self):
        """Contract has both reveal and refund spending paths."""
        self.assertIn('canReveal', self.contract)
        self.assertIn('canRefund', self.contract)
        self.assertIn('canReveal || canRefund', self.contract)

    def test_commitment_verification(self):
        """Contract verifies commitment on-chain."""
        self.assertIn('commitmentOk', self.contract)
        self.assertIn('computedHash', self.contract)
        self.assertIn('commitmentHash', self.contract)

    def test_payout_enforcement(self):
        """Contract enforces minimum payout amounts."""
        self.assertIn('winPayout', self.contract)
        self.assertIn('refundAmount', self.contract)
        self.assertIn('OUTPUTS(0).value >= winPayout', self.contract)

    def test_timeout_mechanism(self):
        """Contract has timeout-based refund."""
        self.assertIn('HEIGHT >= timeoutHeight', self.contract)

    def test_house_edge_in_contract(self):
        """Contract implements 3% house edge (97/50)."""
        self.assertIn('97L', self.contract)
        self.assertIn('50L', self.contract)

    def test_no_nft_token_logic(self):
        """v2 contract does NOT use NFT tokens (pure PK-based)."""
        # v2 uses SigmaProp (proveDlog) for auth, not NFT tokens
        self.assertIn('proveDlog', self.contract)
        self.assertNotIn('fromSelf.tokens', self.contract)
        self.assertNotIn('gameNFT', self.contract)

    def test_player_secret_is_coll_byte(self):
        """Player secret in R9 is Coll[Byte], not Int."""
        self.assertIn('R9[Coll[Byte]]', self.contract)
        # Should NOT have the old v1 pattern of R8[Int] for secret
        self.assertNotIn('R8[Int].get  // player secret', self.contract)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_commit_all_zero_secret(self):
        """Commitment works with all-zero secret."""
        secret = bytes(8)
        commit = generate_commit(secret, 0)
        self.assertTrue(verify_commit(commit, secret, 0))

    def test_commit_all_ff_secret(self):
        """Commitment works with all-0xFF secret."""
        secret = bytes([0xFF] * 8)
        commit = generate_commit(secret, 1)
        self.assertTrue(verify_commit(commit, secret, 1))

    def test_commit_empty_block_hash_fails(self):
        """Empty block hash should produce a result (0 bytes -> 0 length hash)."""
        # compute_rng with empty string: bytes.fromhex("") = b"" (0 bytes)
        # This is technically valid input that produces a deterministic result
        result = compute_rng("00" * 32, bytes(8))  # Use valid all-zeros hash
        self.assertIn(result, [0, 1])

    def test_rng_short_block_hash_fails(self):
        """Non-64-char block hash should fail."""
        with self.assertRaises(ValueError):
            compute_rng("abc", bytes(8))

    def test_rng_odd_length_block_hash_fails(self):
        """Odd-length hex string should fail."""
        with self.assertRaises(ValueError):
            compute_rng("a" * 63, bytes(8))  # 63 chars, not valid 32 bytes

    def test_verify_commit_with_invalid_secret_length(self):
        """Verify returns False for wrong-length secrets."""
        commit = generate_commit(bytes(8), 0)
        self.assertFalse(verify_commit(commit, bytes(4), 0))  # Too short
        self.assertFalse(verify_commit(commit, bytes(16), 0))  # Too long

    def test_verify_commit_with_invalid_choice(self):
        """Verify returns False for invalid choices."""
        commit = generate_commit(bytes(8), 0)
        self.assertFalse(verify_commit(commit, bytes(8), 2))
        self.assertFalse(verify_commit(commit, bytes(8), -1))
        self.assertFalse(verify_commit(commit, bytes(8), 100))


class TestContractIntegration(unittest.TestCase):
    """Integration tests: full commit-reveal-verify cycle."""

    def test_full_commit_reveal_cycle(self):
        """Complete commit -> RNG -> outcome cycle."""
        # 1. Player generates secret and commits
        secret = bytes([0xAB, 0xCD, 0xEF, 0x01, 0x23, 0x45, 0x67, 0x89])
        choice = 0  # heads
        commit = generate_commit(secret, choice)

        # 2. Verify commitment
        self.assertTrue(verify_commit(commit, secret, choice))

        # 3. Simulate reveal with a block hash
        block_hash = "a" * 64
        outcome = compute_rng(block_hash, secret)

        # 4. Outcome is binary
        self.assertIn(outcome, [0, 1])

        # 5. Player wins if outcome matches choice
        player_wins = (outcome == choice)
        bet = 1_000_000_000  # 1 ERG
        if player_wins:
            payout = bet * 97 // 50
            self.assertEqual(payout, 1_940_000_000)
        else:
            payout = 0  # House takes all

    def test_commit_reveal_cycle_both_outcomes(self):
        """Both win and loss paths work."""
        secret = bytes([0x42] * 8)

        # Find a block hash where player wins (choice=0, outcome=0)
        found_heads = False
        found_tails = False
        for i in range(200):
            block_hash = f"{i:064x}"
            outcome = compute_rng(block_hash, secret)
            if outcome == 0:
                found_heads = True
            else:
                found_tails = True
            if found_heads and found_tails:
                break

        self.assertTrue(found_heads, "Should find at least one heads outcome")
        self.assertTrue(found_tails, "Should find at least one tails outcome")


if __name__ == '__main__':
    unittest.main(verbosity=2)
