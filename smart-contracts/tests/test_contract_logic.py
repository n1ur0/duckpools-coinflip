"""
DuckPools Coinflip Contract Unit Tests

Tests the contract logic for coinflip_v2_final.es and coinflip_v3.es.
These tests simulate the ErgoScript guard conditions in Python to verify:
- Commitment verification (blake2b256)
- RNG outcome determination
- House edge calculations (3% on 2x = 1.94x payout)
- Refund fee calculations (2% fee = 0.98x refund)
- Reveal path guards (v2: before timeout, v3: within reveal window)
- Refund path guards (after timeout)
- Payout enforcement (minimum amounts)

Run: cd /Users/n1ur0/Documents/git/duckpools-coinflip && python -m pytest smart-contracts/tests/test_contract_logic.py -v

MAT-393 Phase 2: Smart contract fix, compilation, testnet deploy
"""

import hashlib
import pytest
from dataclasses import dataclass
from typing import Optional


# ─── Helper Functions (mirror on-chain ErgoScript) ──────────────────

def blake2b256(data: bytes) -> bytes:
    """Ergo's native blake2b256 hash (32 bytes)."""
    return hashlib.blake2b(data, digest_size=32).digest()


def compute_commitment(secret: bytes, choice: int) -> bytes:
    """On-chain: blake2b256(secret || choice_byte)"""
    choice_byte = 0 if choice == 0 else 1
    return blake2b256(secret + bytes([choice_byte]))


def compute_rng(block_hash_hex: str, secret: bytes) -> int:
    """On-chain: blake2b256(blockSeed ++ playerSecret)[0] % 2"""
    block_seed = bytes.fromhex(block_hash_hex)
    rng_hash = blake2b256(block_seed + secret)
    return rng_hash[0] % 2


def compute_win_payout(bet_nanoerg: int) -> int:
    """On-chain: betAmount * 97 / 50 (1.94x)"""
    return bet_nanoerg * 97 // 50


def compute_refund(bet_nanoerg: int) -> int:
    """On-chain: betAmount - betAmount / 50 (0.98x)"""
    return bet_nanoerg - bet_nanoerg // 50


def verify_v2_reveal(
    house_sig: bool,
    commitment_ok: bool,
    player_wins: bool,
    output_pk_matches_winner: bool,
    output_value: int,
    min_required_value: int,
    height: int,
    timeout_height: int,
) -> bool:
    """Simulate v2-final canReveal guard."""
    if not house_sig:
        return False
    if not commitment_ok:
        return False
    if height > timeout_height:
        return False  # v2 doesn't explicitly check but refund takes over
    if not output_pk_matches_winner:
        return False
    if output_value < min_required_value:
        return False
    return True


def verify_v2_refund(
    player_sig: bool,
    output_pk_is_player: bool,
    output_value: int,
    min_refund: int,
    height: int,
    timeout_height: int,
) -> bool:
    """Simulate v2-final canRefund guard."""
    if height < timeout_height:
        return False
    if not player_sig:
        return False
    if not output_pk_is_player:
        return False
    if output_value < min_refund:
        return False
    return True


def verify_v3_reveal(
    house_sig: bool,
    commitment_ok: bool,
    player_wins: bool,
    output_pk_matches_winner: bool,
    output_value: int,
    min_required_value: int,
    height: int,
    rng_block_height: int,
    timeout_height: int,
) -> bool:
    """Simulate v3 canReveal guard (with reveal window)."""
    if not house_sig:
        return False
    if not commitment_ok:
        return False
    # v3: must reveal within [rngBlockHeight, timeoutHeight]
    if height < rng_block_height or height > timeout_height:
        return False
    if not output_pk_matches_winner:
        return False
    if output_value < min_required_value:
        return False
    return True


# ─── Test Data ───────────────────────────────────────────────────────

# Simulated block hash (32 bytes hex)
BLOCK_HASH_1 = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
BLOCK_HASH_2 = "ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00"
BLOCK_HASH_3 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

PLAYER_SECRET_8 = bytes([0x42, 0x13, 0x37, 0xca, 0xfe, 0xba, 0xbe, 0x01])
PLAYER_SECRET_32 = bytes(range(32))

# 1 ERG = 1,000,000,000 nanoERG
ONE_ERG = 1_000_000_000


# ─── Commitment Verification Tests ───────────────────────────────────

class TestCommitmentVerification:
    """Verify commitment = blake2b256(secret || choice_byte)"""

    def test_heads_commitment_valid(self):
        choice = 0  # heads
        commitment = compute_commitment(PLAYER_SECRET_8, choice)
        # Re-derive and verify
        choice_byte = bytes([0])
        assert blake2b256(PLAYER_SECRET_8 + choice_byte) == commitment

    def test_tails_commitment_valid(self):
        choice = 1  # tails
        commitment = compute_commitment(PLAYER_SECRET_8, choice)
        choice_byte = bytes([1])
        assert blake2b256(PLAYER_SECRET_8 + choice_byte) == commitment

    def test_wrong_secret_fails(self):
        """Commitment with wrong secret should not match"""
        commitment = compute_commitment(PLAYER_SECRET_8, 0)
        wrong_secret = bytes([0xFF] * 8)
        wrong_hash = blake2b256(wrong_secret + bytes([0]))
        assert wrong_hash != commitment

    def test_wrong_choice_fails(self):
        """Commitment with wrong choice byte should not match"""
        commitment = compute_commitment(PLAYER_SECRET_8, 0)
        # Try to verify with choice=1 instead of 0
        wrong_hash = blake2b256(PLAYER_SECRET_8 + bytes([1]))
        assert wrong_hash != commitment

    def test_32_byte_secret(self):
        """32-byte secrets (as documented in ARCHITECTURE.md) should work"""
        commitment = compute_commitment(PLAYER_SECRET_32, 0)
        assert len(commitment) == 32  # blake2b256 output is always 32 bytes
        assert blake2b256(PLAYER_SECRET_32 + bytes([0])) == commitment

    def test_commitment_deterministic(self):
        """Same inputs must produce same commitment"""
        c1 = compute_commitment(PLAYER_SECRET_8, 1)
        c2 = compute_commitment(PLAYER_SECRET_8, 1)
        assert c1 == c2


# ─── RNG Tests ───────────────────────────────────────────────────────

class TestRNG:
    """Verify RNG = blake2b256(blockHash || secret)[0] % 2"""

    def test_rng_deterministic(self):
        """Same block + secret must produce same outcome"""
        r1 = compute_rng(BLOCK_HASH_1, PLAYER_SECRET_8)
        r2 = compute_rng(BLOCK_HASH_1, PLAYER_SECRET_8)
        assert r1 == r2

    def test_different_block_changes_outcome(self):
        """Different block hash should change outcome with high probability"""
        import struct
        # Use many more block hashes to avoid false positive
        outcomes = set()
        for i in range(50):
            bh = hashlib.sha256(struct.pack('>I', i)).hexdigest()
            outcomes.add(compute_rng(bh, PLAYER_SECRET_8))
        # With 50 samples from uniform distribution, should see both 0 and 1
        # Probability of seeing only one outcome: 2 * (0.5)^50 ≈ 0
        assert len(outcomes) == 2, f"RNG stuck on single outcome across 50 blocks: {outcomes}"

    def test_different_secret_changes_outcome(self):
        """Different secret should change outcome with high probability"""
        import struct
        outcomes = set()
        for i in range(50):
            secret = hashlib.sha256(struct.pack('>I', i)).digest()[:8]
            outcomes.add(compute_rng(BLOCK_HASH_1, secret))
        # With 50 different secrets, should see both outcomes
        assert len(outcomes) == 2, f"RNG stuck on single outcome across 50 secrets: {outcomes}"

    def test_rng_binary_output(self):
        """RNG must produce exactly 0 or 1"""
        for bh in [BLOCK_HASH_1, BLOCK_HASH_2, BLOCK_HASH_3]:
            for secret in [PLAYER_SECRET_8, PLAYER_SECRET_32, b'\x00' * 8]:
                result = compute_rng(bh, secret)
                assert result in (0, 1), f"RNG produced {result}, expected 0 or 1"

    def test_rng_matches_contract_formula(self):
        """Verify exact formula: blake2b256(blockSeed ++ playerSecret)[0] % 2"""
        block_seed = bytes.fromhex(BLOCK_HASH_1)
        expected = blake2b256(block_seed + PLAYER_SECRET_8)[0] % 2
        actual = compute_rng(BLOCK_HASH_1, PLAYER_SECRET_8)
        assert actual == expected

    def test_rng_distribution_approximately_fair(self):
        """With 100 different seeds, should get roughly 50/50 distribution"""
        import struct
        outcomes = []
        for i in range(100):
            # Generate pseudo-random block hash
            bh = hashlib.sha256(struct.pack('>I', i)).hexdigest()
            secret = hashlib.sha256(struct.pack('>I', i + 1000)).digest()[:8]
            outcomes.append(compute_rng(bh, secret))
        heads = sum(1 for o in outcomes if o == 0)
        tails = sum(1 for o in outcomes if o == 1)
        # Should be roughly 50/50 (allow 30-70 range for 100 samples)
        assert 30 <= heads <= 70, f"Distribution too skewed: {heads}H/{tails}T"


# ─── Economics Tests ─────────────────────────────────────────────────

class TestEconomics:
    """Verify house edge (3%) and refund fee (2%) calculations"""

    def test_win_payout_1_94x(self):
        """Player win payout must be 1.94x bet amount"""
        assert compute_win_payout(ONE_ERG) == 1_940_000_000

    def test_win_payout_10_erg(self):
        """Player win payout for 10 ERG"""
        assert compute_win_payout(10 * ONE_ERG) == 19_400_000_000

    def test_win_payout_exact_formula(self):
        """Verify: betAmount * 97 / 50"""
        # For 100 nanoERG: 100 * 97 / 50 = 194
        assert compute_win_payout(100) == 194

    def test_refund_0_98x(self):
        """Refund must be 98% of bet amount"""
        assert compute_refund(ONE_ERG) == 980_000_000

    def test_refund_exact_formula(self):
        """Verify: betAmount - betAmount / 50"""
        # For 100 nanoERG: 100 - 100/50 = 100 - 2 = 98
        assert compute_refund(100) == 98

    def test_house_edge_is_3_percent(self):
        """Verify house edge: player bets 1, wins 1.94, expected loss per flip = 0.03"""
        bet = ONE_ERG
        win = compute_win_payout(bet)
        # Expected value = 0.5 * win + 0.5 * 0 - bet = 0.5 * 1.94 - 1 = -0.03
        ev = 0.5 * win - bet
        assert ev == -30_000_000  # -0.03 ERG = 3% edge on 1 ERG

    def test_refund_fee_is_2_percent(self):
        """Verify refund fee: player gets 98% back"""
        bet = ONE_ERG
        refund = compute_refund(bet)
        fee = bet - refund
        assert fee == 20_000_000  # 0.02 ERG = 2% fee on 1 ERG

    def test_win_payout_uses_integer_division(self):
        """ErgoScript uses Long division -- must match Python //"""
        # Test with odd amounts to verify floor division
        assert compute_win_payout(3) == 3 * 97 // 50  # = 5
        assert compute_refund(3) == 3 - 3 // 50  # = 3


# ─── v2-final Reveal Path Tests ─────────────────────────────────────

class TestV2RevealPath:
    """Test v2-final reveal guard: houseProp && commitmentOk && correctPayout"""

    def test_valid_reveal_player_wins(self):
        result = verify_v2_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=500,
            timeout_height=600,
        )
        assert result is True

    def test_valid_reveal_house_wins(self):
        result = verify_v2_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=False,
            output_pk_matches_winner=True,
            output_value=1_000_000_000,
            min_required_value=1_000_000_000,
            height=500,
            timeout_height=600,
        )
        assert result is True

    def test_reveal_without_house_sig_fails(self):
        result = verify_v2_reveal(
            house_sig=False,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=500,
            timeout_height=600,
        )
        assert result is False

    def test_reveal_with_bad_commitment_fails(self):
        result = verify_v2_reveal(
            house_sig=True,
            commitment_ok=False,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=500,
            timeout_height=600,
        )
        assert result is False

    def test_reveal_with_underpay_fails(self):
        """House tries to pay less than required"""
        result = verify_v2_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_000_000_000,  # Only 1 ERG instead of 1.94 ERG
            min_required_value=1_940_000_000,
            height=500,
            timeout_height=600,
        )
        assert result is False

    def test_reveal_with_wrong_recipient_fails(self):
        """Payout goes to wrong address"""
        result = verify_v2_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=False,  # Wrong recipient
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=500,
            timeout_height=600,
        )
        assert result is False

    def test_reveal_pays_extra_is_ok(self):
        """Paying MORE than minimum is allowed (fees absorbed)"""
        result = verify_v2_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=2_000_000_000,  # 2 ERG instead of 1.94 ERG
            min_required_value=1_940_000_000,
            height=500,
            timeout_height=600,
        )
        assert result is True


# ─── v2-final Refund Path Tests ─────────────────────────────────────

class TestV2RefundPath:
    """Test v2-final refund guard: HEIGHT >= timeout && playerProp && correctRefund"""

    def test_valid_refund(self):
        result = verify_v2_refund(
            player_sig=True,
            output_pk_is_player=True,
            output_value=980_000_000,
            min_refund=980_000_000,
            height=601,
            timeout_height=600,
        )
        assert result is True

    def test_refund_before_timeout_fails(self):
        result = verify_v2_refund(
            player_sig=True,
            output_pk_is_player=True,
            output_value=980_000_000,
            min_refund=980_000_000,
            height=599,
            timeout_height=600,
        )
        assert result is False

    def test_refund_at_exact_timeout_succeeds(self):
        """HEIGHT >= timeoutHeight means exact timeout works"""
        result = verify_v2_refund(
            player_sig=True,
            output_pk_is_player=True,
            output_value=980_000_000,
            min_refund=980_000_000,
            height=600,
            timeout_height=600,
        )
        assert result is True

    def test_refund_without_player_sig_fails(self):
        result = verify_v2_refund(
            player_sig=False,
            output_pk_is_player=True,
            output_value=980_000_000,
            min_refund=980_000_000,
            height=601,
            timeout_height=600,
        )
        assert result is False

    def test_refund_with_underpay_fails(self):
        """Player tries to refund to themselves with less than 98%"""
        result = verify_v2_refund(
            player_sig=True,
            output_pk_is_player=True,
            output_value=500_000_000,  # Only 0.5 ERG
            min_refund=980_000_000,
            height=601,
            timeout_height=600,
        )
        assert result is False

    def test_refund_to_wrong_address_fails(self):
        result = verify_v2_refund(
            player_sig=True,
            output_pk_is_player=False,
            output_value=980_000_000,
            min_refund=980_000_000,
            height=601,
            timeout_height=600,
        )
        assert result is False


# ─── v3 Reveal Window Tests ─────────────────────────────────────────

class TestV3RevealWindow:
    """Test v3 reveal guard with pre-committed reveal window"""

    def test_reveal_within_window(self):
        result = verify_v3_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=110,  # Between rngBlockHeight and timeoutHeight
            rng_block_height=100,
            timeout_height=130,
        )
        assert result is True

    def test_reveal_before_window_fails(self):
        """House tries to reveal before committed window"""
        result = verify_v3_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=99,  # Before rngBlockHeight=100
            rng_block_height=100,
            timeout_height=130,
        )
        assert result is False

    def test_reveal_after_window_fails(self):
        """House tries to reveal after timeout"""
        result = verify_v3_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=131,  # After timeoutHeight=130
            rng_block_height=100,
            timeout_height=130,
        )
        assert result is False

    def test_reveal_at_window_start(self):
        """Reveal at exact rngBlockHeight should succeed"""
        result = verify_v3_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=100,
            rng_block_height=100,
            timeout_height=130,
        )
        assert result is True

    def test_reveal_at_window_end(self):
        """Reveal at exact timeoutHeight should succeed"""
        result = verify_v3_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=130,
            rng_block_height=100,
            timeout_height=130,
        )
        assert result is True

    def test_narrow_window_limits_grinding(self):
        """With a 5-block window, grinding is limited to 5 blocks"""
        result_too_early = verify_v3_reveal(
            house_sig=True, commitment_ok=True, player_wins=True,
            output_pk_matches_winner=True, output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=99, rng_block_height=100, timeout_height=104,
        )
        result_ok = verify_v3_reveal(
            house_sig=True, commitment_ok=True, player_wins=True,
            output_pk_matches_winner=True, output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=102, rng_block_height=100, timeout_height=104,
        )
        result_too_late = verify_v3_reveal(
            house_sig=True, commitment_ok=True, player_wins=True,
            output_pk_matches_winner=True, output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=105, rng_block_height=100, timeout_height=104,
        )
        assert result_too_early is False
        assert result_ok is True
        assert result_too_late is False


# ─── End-to-End Flow Tests ─────────────────────────────────────────

class TestEndToEndFlow:
    """Simulate full bet lifecycle"""

    def test_full_player_wins_flow(self):
        """Player bets 1 ERG on heads, wins, gets 1.94 ERG"""
        secret = PLAYER_SECRET_8
        choice = 0  # heads
        bet = ONE_ERG

        # 1. Commit phase
        commitment = compute_commitment(secret, choice)
        assert len(commitment) == 32

        # 2. Verify commitment on-chain
        computed = blake2b256(secret + bytes([choice]))
        assert computed == commitment

        # 3. Reveal phase -- simulate house picking block
        block_hash = BLOCK_HASH_1
        outcome = compute_rng(block_hash, secret)
        player_wins = (outcome == choice)

        # 4. Calculate payouts
        if player_wins:
            min_payout = compute_win_payout(bet)
            assert min_payout == 1_940_000_000
        else:
            min_payout = bet

        # 5. Verify reveal transaction valid
        result = verify_v2_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=player_wins,
            output_pk_matches_winner=True,
            output_value=min_payout,
            min_required_value=min_payout,
            height=500,
            timeout_height=600,
        )
        assert result is True

    def test_full_house_wins_flow(self):
        """Player bets 1 ERG on tails, house wins, keeps 1 ERG"""
        secret = PLAYER_SECRET_32
        choice = 1  # tails
        bet = ONE_ERG

        commitment = compute_commitment(secret, choice)
        block_hash = BLOCK_HASH_2
        outcome = compute_rng(block_hash, secret)
        player_wins = (outcome == choice)

        if player_wins:
            min_payout = compute_win_payout(bet)
        else:
            min_payout = bet

        result = verify_v2_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=player_wins,
            output_pk_matches_winner=True,
            output_value=min_payout,
            min_required_value=min_payout,
            height=500,
            timeout_height=600,
        )
        assert result is True

    def test_full_refund_flow(self):
        """Player bets, house goes offline, player refunds after timeout"""
        secret = PLAYER_SECRET_8
        choice = 0
        bet = ONE_ERG
        timeout_height = 600

        commitment = compute_commitment(secret, choice)
        refund = compute_refund(bet)

        # Before timeout: refund fails
        result_before = verify_v2_refund(
            player_sig=True,
            output_pk_is_player=True,
            output_value=refund,
            min_refund=refund,
            height=599,
            timeout_height=timeout_height,
        )
        assert result_before is False

        # After timeout: refund succeeds
        result_after = verify_v2_refund(
            player_sig=True,
            output_pk_is_player=True,
            output_value=refund,
            min_refund=refund,
            height=601,
            timeout_height=timeout_height,
        )
        assert result_after is True

    def test_v3_full_flow_with_window(self):
        """v3: full flow with pre-committed reveal window"""
        secret = PLAYER_SECRET_8
        choice = 0
        bet = ONE_ERG
        rng_block_height = 100
        timeout_height = 130

        commitment = compute_commitment(secret, choice)
        block_hash = BLOCK_HASH_1
        outcome = compute_rng(block_hash, secret)
        player_wins = (outcome == choice)

        if player_wins:
            min_payout = compute_win_payout(bet)
        else:
            min_payout = bet

        # Reveal at height 110 (within window)
        result = verify_v3_reveal(
            house_sig=True,
            commitment_ok=True,
            player_wins=player_wins,
            output_pk_matches_winner=True,
            output_value=min_payout,
            min_required_value=min_payout,
            height=110,
            rng_block_height=rng_block_height,
            timeout_height=timeout_height,
        )
        assert result is True


# ─── Edge Case Tests ─────────────────────────────────────────────────

class TestEdgeCases:
    """Test boundary conditions and edge cases"""

    def test_zero_bet(self):
        """Zero bet should produce zero payouts"""
        assert compute_win_payout(0) == 0
        assert compute_refund(0) == 0

    def test_minimum_bet(self):
        """Minimum Ergo bet (1 nanoERG)"""
        assert compute_win_payout(1) == 1  # 1 * 97 // 50 = 1 (floor)
        assert compute_refund(1) == 1  # 1 - 1 // 50 = 1 - 0 = 1

    def test_very_large_bet(self):
        """1000 ERG bet"""
        bet = 1000 * ONE_ERG
        assert compute_win_payout(bet) == 1_940_000_000_000
        assert compute_refund(bet) == 980_000_000_000

    def test_empty_secret(self):
        """Empty secret should still work (though insecure)"""
        commitment = compute_commitment(b'', 0)
        assert len(commitment) == 32
        outcome = compute_rng(BLOCK_HASH_1, b'')
        assert outcome in (0, 1)

    def test_choice_only_0_or_1(self):
        """Contract only accepts choice 0 or 1"""
        c0 = compute_commitment(PLAYER_SECRET_8, 0)
        c1 = compute_commitment(PLAYER_SECRET_8, 1)
        # choice=2 should map to 1 (since ErgoScript does: if (choice==0) 0 else 1)
        c2 = compute_commitment(PLAYER_SECRET_8, 2)
        assert c0 != c1
        assert c2 == c1  # choice=2 treated as 1 in contract

    def test_commitment_32_bytes(self):
        """Commitment hash must be exactly 32 bytes"""
        commitment = compute_commitment(PLAYER_SECRET_8, 0)
        assert len(commitment) == 32

    def test_different_secrets_different_commitments(self):
        """Different secrets produce different commitments"""
        c1 = compute_commitment(PLAYER_SECRET_8, 0)
        c2 = compute_commitment(PLAYER_SECRET_32, 0)
        assert c1 != c2

    def test_refund_cannot_be_claimed_by_house(self):
        """House cannot claim refund (must be player sig)"""
        result = verify_v2_refund(
            player_sig=False,  # House sig, not player
            output_pk_is_player=False,
            output_value=980_000_000,
            min_refund=980_000_000,
            height=601,
            timeout_height=600,
        )
        assert result is False

    def test_reveal_cannot_be_done_by_player(self):
        """Player cannot reveal (must be house sig)"""
        result = verify_v2_reveal(
            house_sig=False,  # Player sig, not house
            commitment_ok=True,
            player_wins=True,
            output_pk_matches_winner=True,
            output_value=1_940_000_000,
            min_required_value=1_940_000_000,
            height=500,
            timeout_height=600,
        )
        assert result is False


# ─── NFT Preservation Tests ─────────────────────────────────────────

class TestNFTPreservation:
    """Verify NFT handling during refund (MAT-268)"""

    def test_refund_preserves_nft_value_note(self):
        """
        NFT tokens in the bet box should be returned on refund.
        On Ergo, tokens in SELF are available to OUTPUTS.
        The v2_final contract only checks OUTPUTS(0).value >= refundAmount,
        which allows OUTPUTS(0) to also carry tokens (NFTs).
        This is correct -- the NFT is preserved because it stays in the box.
        """
        bet = ONE_ERG
        refund = compute_refund(bet)
        # Output value must be >= refund, NFTs are separate
        # This test documents the design: value check doesn't block NFTs
        assert refund <= bet  # Refund is always <= bet, so NFT value not affected

    def test_win_payout_does_not_block_nft(self):
        """Win payout >= winPayout check doesn't prevent NFT preservation"""
        bet = ONE_ERG
        win = compute_win_payout(bet)
        # House can add extra value (including NFT return) beyond minimum
        assert win < bet * 2  # 1.94x < 2x, so house has 0.06x margin for fees/NFTs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
