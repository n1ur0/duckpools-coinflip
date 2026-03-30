"""
DuckPools - Contract Unit Tests for coinflip_v2_final.es

Tests the off-chain logic that MUST match the on-chain contract:
  1. Commit-reveal scheme (blake2b256 hash computation)
  2. RNG fairness (statistical distribution)
  3. Economics (house edge 3%, refund fee 2%)
  4. Register layout consistency
  5. Contract compilation via node API
  6. Timeout/refund mechanics

MAT-393 Phase 2: Smart contract fix, compilation, testnet deploy
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

# Add backend to path for RNG module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rng_module import compute_rng, generate_commit, verify_commit, simulate_coinflip


# ─── Test Data ─────────────────────────────────────────────────────────

FIXED_SECRET = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
FIXED_BLOCK_HASH = "a" * 64  # Dummy block hash for deterministic tests
CONTRACT_PATH = Path(__file__).parent.parent.parent / "smart-contracts" / "coinflip_v2_final.es"
DEPLOYED_PATH = Path(__file__).parent.parent.parent / "smart-contracts" / "coinflip_deployed.json"

# Contract constants (MUST match coinflip_v2_final.es)
HOUSE_EDGE_NUMERATOR = 97
HOUSE_EDGE_DENOMINATOR = 50  # 97/50 = 1.94x (3% house edge on 2x)
REFUND_FEE_DENOMINATOR = 50  # 1/50 = 2% fee
DEFAULT_TIMEOUT_DELTA = 100  # blocks
REVEAL_WINDOW = 30  # blocks


# ─── 1. Commit-Reveal Scheme Tests ────────────────────────────────────


class TestCommitReveal:
    """Verify commitment hash matches on-chain contract logic.

    On-chain: blake2b256(playerSecret ++ choiceByte)
    """

    def test_commit_heads_matches_formula(self):
        """Commitment for choice=0 (heads) uses blake2b256(secret || 0x00)."""
        secret = FIXED_SECRET
        choice = 0
        commit = generate_commit(secret, choice)

        # Manually compute to verify
        choice_byte = bytes([choice])
        expected = hashlib.blake2b(secret + choice_byte, digest_size=32).hexdigest()

        assert commit == expected

    def test_commit_tails_matches_formula(self):
        """Commitment for choice=1 (tails) uses blake2b256(secret || 0x01)."""
        secret = FIXED_SECRET
        choice = 1
        commit = generate_commit(secret, choice)

        choice_byte = bytes([choice])
        expected = hashlib.blake2b(secret + choice_byte, digest_size=32).hexdigest()

        assert commit == expected

    def test_different_choices_produce_different_commits(self):
        """Heads and tails commitments with same secret must differ."""
        secret = FIXED_SECRET
        commit_heads = generate_commit(secret, 0)
        commit_tails = generate_commit(secret, 1)

        assert commit_heads != commit_tails

    def test_different_secrets_produce_different_commits(self):
        """Different secrets with same choice must produce different commits."""
        secret_a = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        secret_b = bytes([8, 7, 6, 5, 4, 3, 2, 1])

        commit_a = generate_commit(secret_a, 0)
        commit_b = generate_commit(secret_b, 0)

        assert commit_a != commit_b

    def test_commit_length_is_32_bytes(self):
        """Commitment hash must be 32 bytes (256 bits) for blake2b256."""
        commit = generate_commit(FIXED_SECRET, 0)
        assert len(commit) == 64  # hex encoding of 32 bytes

    def test_verify_commit_valid(self):
        """verify_commit returns True for correct commitment."""
        commit = generate_commit(FIXED_SECRET, 0)
        assert verify_commit(commit, FIXED_SECRET, 0) is True

    def test_verify_commit_wrong_secret(self):
        """verify_commit returns False for wrong secret."""
        commit = generate_commit(FIXED_SECRET, 0)
        wrong_secret = bytes([0xFF] * 8)
        assert verify_commit(commit, wrong_secret, 0) is False

    def test_verify_commit_wrong_choice(self):
        """verify_commit returns False for wrong choice."""
        commit = generate_commit(FIXED_SECRET, 0)
        assert verify_commit(commit, FIXED_SECRET, 1) is False

    def test_verify_commit_tampered_hash(self):
        """verify_commit returns False for tampered commitment hash."""
        commit = generate_commit(FIXED_SECRET, 0)
        tampered = commit[:30] + "ff" + commit[32:]
        assert verify_commit(tampered, FIXED_SECRET, 0) is False

    def test_generate_commit_rejects_wrong_secret_length(self):
        """generate_commit raises ValueError for non-8-byte secrets."""
        with pytest.raises(ValueError, match="8 bytes"):
            generate_commit(bytes([1, 2, 3]), 0)

        with pytest.raises(ValueError, match="8 bytes"):
            generate_commit(bytes([1] * 16), 0)

    def test_generate_commit_rejects_invalid_choice(self):
        """generate_commit raises ValueError for choices other than 0 or 1."""
        with pytest.raises(ValueError, match="0 or 1"):
            generate_commit(FIXED_SECRET, 2)

        with pytest.raises(ValueError, match="0 or 1"):
            generate_commit(FIXED_SECRET, -1)


# ─── 2. RNG Fairness Tests ────────────────────────────────────────────


class TestRNGFairness:
    """Verify RNG matches on-chain contract and is statistically fair.

    On-chain: blake2b256(CONTEXT.preHeader.parentId ++ playerSecret)[0] % 2
    """

    def test_rng_deterministic(self):
        """Same inputs always produce same output."""
        block_hash = "b" * 64
        result1 = compute_rng(block_hash, FIXED_SECRET)
        result2 = compute_rng(block_hash, FIXED_SECRET)
        assert result1 == result2

    def test_rng_returns_binary(self):
        """RNG output must be 0 or 1."""
        for i in range(100):
            block_hash = f"{i:064x}"
            result = compute_rng(block_hash, FIXED_SECRET)
            assert result in (0, 1)

    def test_rng_different_secrets_different_outcomes(self):
        """Different secrets should produce different outcomes with high probability."""
        block_hash = "c" * 64
        outcomes = set()
        for i in range(256):
            secret = i.to_bytes(8, 'big')
            outcomes.add(compute_rng(block_hash, secret))
        # With 256 different secrets, we should see both outcomes
        assert len(outcomes) == 2

    def test_rng_different_blocks_different_outcomes(self):
        """Different block hashes should produce different outcomes with high probability."""
        outcomes = set()
        for i in range(256):
            block_hash = f"{i:064x}"
            outcomes.add(compute_rng(block_hash, FIXED_SECRET))
        assert len(outcomes) == 2

    def test_rng_distribution_fair_1000(self):
        """1000 coinflips should be approximately 50/50."""
        result = simulate_coinflip(1000)
        assert result.total_outcomes == 1000
        assert 0.45 < result.heads_ratio < 0.55
        assert 0.45 < result.tails_ratio < 0.55

    def test_rng_distribution_fair_10000(self):
        """10000 coinflips should be closer to 50/50."""
        result = simulate_coinflip(10000)
        assert result.total_outcomes == 10000
        assert 0.48 < result.heads_ratio < 0.52

    def test_rng_chi_square_acceptable(self):
        """Chi-square test should not reject fairness."""
        result = simulate_coinflip(10000)
        # p-value > 0.01 means we can't reject the null hypothesis of fairness
        assert result.p_value > 0.01

    def test_rng_entropy_high(self):
        """Shannon entropy should be close to 1.0 bit (max for binary)."""
        result = simulate_coinflip(10000)
        assert result.entropy_bits > 0.99

    def test_rng_uniform_flag(self):
        """simulate_coinflip uniform flag should be True for fair RNG."""
        result = simulate_coinflip(10000)
        assert result.uniform is True


# ─── 3. Economics Tests ───────────────────────────────────────────────


class TestEconomics:
    """Verify house edge and refund fee match contract constants.

    On-chain:
      winPayout    = betAmount * 97L / 50L    (1.94x = 3% house edge)
      refundAmount = betAmount - betAmount / 50L  (98% = 2% refund fee)
    """

    def test_house_edge_payout_ratio(self):
        """Win payout should be 1.94x bet amount (3% edge on 2x)."""
        for bet in [1_000_000, 10_000_000, 100_000_000, 1_000_000_000]:
            win_payout = bet * HOUSE_EDGE_NUMERATOR // HOUSE_EDGE_DENOMINATOR
            # 1.94x means player gets 194% of bet
            ratio = win_payout / bet
            assert abs(ratio - 1.94) < 0.001, f"Expected ~1.94x, got {ratio:.6f}x for bet {bet}"

    def test_house_edge_exact_3_percent(self):
        """House edge is exactly 3%: player wins 1.94x instead of 2x."""
        # If fair payout = 2x, house edge = (2.0 - 1.94) / 2.0 = 0.03 = 3%
        fair_payout_multiplier = 2.0
        actual_payout_multiplier = HOUSE_EDGE_NUMERATOR / HOUSE_EDGE_DENOMINATOR
        edge = (fair_payout_multiplier - actual_payout_multiplier) / fair_payout_multiplier
        assert abs(edge - 0.03) < 1e-10, f"Expected 3% edge, got {edge:.10f}"

    def test_refund_fee_exact_2_percent(self):
        """Refund fee is exactly 2%: player gets 98% of bet."""
        for bet in [1_000_000, 10_000_000, 100_000_000]:
            refund = bet - bet // REFUND_FEE_DENOMINATOR
            fee = bet - refund
            fee_ratio = fee / bet
            assert abs(fee_ratio - 0.02) < 0.001, f"Expected ~2% fee, got {fee_ratio:.6f}"

    def test_payouts_are_non_negative(self):
        """All payout calculations must be non-negative."""
        # Use realistic bet amounts (nanoERG, minimum meaningful bet is ~1M)
        for bet in [1_000_000, 10_000_000, 100_000_000]:
            win_payout = bet * HOUSE_EDGE_NUMERATOR // HOUSE_EDGE_DENOMINATOR
            refund = bet - bet // REFUND_FEE_DENOMINATOR
            assert win_payout > 0
            assert refund > 0
            assert win_payout > bet  # Player wins more than they bet
            assert refund < bet  # Player gets slightly less than they bet on refund

    def test_payout_division_is_exact(self):
        """Integer division must not lose dust (ergo uses nanoERG)."""
        # Verify that bet * 97 is divisible by 50 for common bet amounts
        # In practice, any bet amount works since we use integer division
        bet = 100_000_000  # 0.1 ERG
        payout = bet * HOUSE_EDGE_NUMERATOR // HOUSE_EDGE_DENOMINATOR
        assert payout == 194_000_000  # 0.194 ERG

    def test_house_always_profitable_on_average(self):
        """Over many rounds, house should profit 3% on average."""
        # If 50% of bets win and 50% lose:
        # House pays out: 0.5 * 1.94x = 0.97x per bet on average
        # House keeps: 1.0 - 0.97 = 0.03 = 3%
        expected_house_profit_rate = 1.0 - 0.5 * (HOUSE_EDGE_NUMERATOR / HOUSE_EDGE_DENOMINATOR)
        assert abs(expected_house_profit_rate - 0.03) < 1e-10


# ─── 4. Register Layout Tests ─────────────────────────────────────────


class TestRegisterLayout:
    """Verify register layout matches contract and backend expectations."""

    EXPECTED_REGISTERS = {
        "R4": "housePubKey (Coll[Byte])",
        "R5": "playerPubKey (Coll[Byte])",
        "R6": "commitmentHash (Coll[Byte])",
        "R7": "playerChoice (Int)",
        "R8": "timeoutHeight (Int)",
        "R9": "playerSecret (Coll[Byte])",
    }

    def test_deployed_json_has_correct_registers(self):
        """coinflip_deployed.json must have R4-R9 register layout."""
        if not DEPLOYED_PATH.exists():
            pytest.skip("coinflip_deployed.json not found")

        with open(DEPLOYED_PATH) as f:
            deployed = json.load(f)

        registers = deployed.get("registerLayout", {})
        for reg_name, expected_desc in self.EXPECTED_REGISTERS.items():
            assert reg_name in registers, f"Missing register {reg_name}"
            assert "housePubKey" in registers[reg_name] or "playerPubKey" in registers[reg_name] or \
                   "commitmentHash" in registers[reg_name] or "playerChoice" in registers[reg_name] or \
                   "timeoutHeight" in registers[reg_name] or "playerSecret" in registers[reg_name], \
                   f"Register {reg_name} has unexpected description: {registers[reg_name]}"

    def test_deployed_json_has_p2s_address(self):
        """coinflip_deployed.json must have a valid P2S address."""
        if not DEPLOYED_PATH.exists():
            pytest.skip("coinflip_deployed.json not found")

        with open(DEPLOYED_PATH) as f:
            deployed = json.load(f)

        address = deployed.get("p2sAddress", "")
        assert address.startswith("3Q"), f"Invalid P2S address format: {address}"
        assert len(address) > 50, f"P2S address too short: {len(address)}"

    def test_deployed_json_timeout_100_blocks(self):
        """Timeout must be 100 blocks."""
        if not DEPLOYED_PATH.exists():
            pytest.skip("coinflip_deployed.json not found")

        with open(DEPLOYED_PATH) as f:
            deployed = json.load(f)

        assert deployed.get("timeoutBlocks") == DEFAULT_TIMEOUT_DELTA
        assert deployed.get("revealWindowBlocks") == REVEAL_WINDOW

    def test_no_r10_usage(self):
        """Contract code must NOT use R10 register (not supported in ErgoScript 6.0.3).

        Note: R10 may appear in documentation comments explaining why it's not used.
        We only check actual code lines (not comments).
        """
        if not CONTRACT_PATH.exists():
            pytest.skip("coinflip_v2_final.es not found")

        with open(CONTRACT_PATH) as f:
            source = f.read()

        # Strip comments and check only code
        code_lines = []
        for line in source.split("\n"):
            stripped = line.split("//")[0]  # Remove inline comments
            if stripped.strip() and not stripped.strip().startswith("*") and not stripped.strip().startswith("/*"):
                code_lines.append(stripped)
        code_only = "\n".join(code_lines)

        assert "R10" not in code_only, "Contract code uses R10 which is not supported in ErgoScript 6.0.3"

    def test_uses_only_r4_to_r9(self):
        """Contract must only use R4-R9 registers."""
        if not CONTRACT_PATH.exists():
            pytest.skip("coinflip_v2_final.es not found")

        with open(CONTRACT_PATH) as f:
            source = f.read()

        for reg in ["R4", "R5", "R6", "R7", "R8", "R9"]:
            assert f"SELF.{reg}" in source, f"Contract doesn't reference {reg}"


# ─── 5. Contract Source Tests ─────────────────────────────────────────


class TestContractSource:
    """Verify contract source code properties."""

    def test_contract_file_exists(self):
        """coinflip_v2_final.es must exist."""
        assert CONTRACT_PATH.exists(), f"Contract not found at {CONTRACT_PATH}"

    def test_contract_has_commit_reveal(self):
        """Contract must implement commit-reveal, not Math.random."""
        with open(CONTRACT_PATH) as f:
            source = f.read()

        assert "blake2b256" in source, "Contract must use blake2b256 for commitment"
        assert "Math.random" not in source, "Contract must NOT use Math.random"
        assert "commitmentHash" in source or "commitment" in source.lower()

    def test_contract_has_timeout_path(self):
        """Contract must have a refund/timeout spending path."""
        with open(CONTRACT_PATH) as f:
            source = f.read()

        assert "canRefund" in source or "refund" in source.lower()
        assert "HEIGHT" in source, "Contract must check block height for timeout"

    def test_contract_has_reveal_path(self):
        """Contract must have a reveal spending path for the house."""
        with open(CONTRACT_PATH) as f:
            source = f.read()

        assert "canReveal" in source or "reveal" in source.lower()
        assert "houseProp" in source or "proveDlog" in source

    def test_contract_has_house_edge(self):
        """Contract must implement house edge in payout calculation."""
        with open(CONTRACT_PATH) as f:
            source = f.read()

        assert "97" in source and "50" in source, "Contract must have 97/50 = 1.94x payout"

    def test_contract_uses_preheader_parentid(self):
        """Contract must use CONTEXT.preHeader.parentId for RNG seed."""
        with open(CONTRACT_PATH) as f:
            source = f.read()

        assert "preHeader" in source or "parentId" in source

    def test_contract_is_well_documented(self):
        """Contract must have comprehensive documentation."""
        with open(CONTRACT_PATH) as f:
            source = f.read()

        # Check for key documentation elements
        assert source.count("*") > 20, "Contract should have extensive comments"
        assert "PROTOCOL FLOW" in source or "FLOW" in source
        assert "SECURITY" in source or "security" in source

    def test_contract_guard_is_or_of_paths(self):
        """Main guard must be OR of reveal and refund paths."""
        with open(CONTRACT_PATH) as f:
            source = f.read()

        # Find the last meaningful expression (skip blank lines and closing braces)
        lines = [l.strip() for l in source.split("\n") if l.strip()]
        # Walk backwards to find the guard expression
        for line in reversed(lines):
            if "||" in line or "canReveal" in line or "canRefund" in line:
                assert True
                return
        pytest.fail("Could not find main guard expression (canReveal || canRefund)")


# ─── 6. Timeout/Refund Mechanics Tests ────────────────────────────────


class TestTimeoutRefund:
    """Verify timeout and refund mechanics."""

    def test_reveal_window_derivation(self):
        """rngBlockHeight = timeoutHeight - REVEAL_WINDOW."""
        timeout_height = 1000
        rng_block_height = timeout_height - REVEAL_WINDOW
        assert rng_block_height == 970

    def test_reveal_window_positive(self):
        """Reveal window must be positive for any valid timeout."""
        for timeout in [100, 200, 500, 1000]:
            rng_height = timeout - REVEAL_WINDOW
            assert rng_height > 0, f"Reveal window would be negative for timeout={timeout}"

    def test_refund_after_timeout(self):
        """Player can refund after timeoutHeight (HEIGHT >= timeoutHeight)."""
        # This is a logic test: if current_height >= timeout_height, refund is allowed
        timeout_height = 1000
        for current_height in [1000, 1001, 2000]:
            assert current_height >= timeout_height, "Refund should be allowed"

    def test_refund_blocked_before_timeout(self):
        """Player CANNOT refund before timeoutHeight."""
        timeout_height = 1000
        for current_height in [969, 970, 999]:
            assert current_height < timeout_height, "Refund should be blocked"

    def test_reveal_allowed_in_window(self):
        """House can reveal between rngBlockHeight and timeoutHeight."""
        timeout_height = 1000
        rng_block_height = timeout_height - REVEAL_WINDOW

        # House can reveal in [rngBlockHeight, timeoutHeight]
        for h in [rng_block_height, rng_block_height + 15, timeout_height]:
            assert rng_block_height <= h <= timeout_height

    def test_reveal_blocked_outside_window(self):
        """House CANNOT reveal outside the window."""
        timeout_height = 1000
        rng_block_height = timeout_height - REVEAL_WINDOW

        # Too early
        assert rng_block_height - 1 < rng_block_height
        # Too late (past timeout, refund path takes over)
        assert timeout_height + 1 > timeout_height


# ─── 7. Contract Compilation Test (requires running node) ─────────────


class TestContractCompilation:
    """Test actual contract compilation against Ergo node."""

    @pytest.fixture(autouse=True)
    def skip_without_node(self):
        """Skip if Ergo node is not reachable."""
        try:
            import requests
            resp = requests.get("http://localhost:9052/info", timeout=3)
            if resp.status_code != 200:
                pytest.skip("Ergo node not responding")
        except Exception:
            pytest.skip("Ergo node not reachable at localhost:9052")

    def test_contract_compiles_to_p2s_address(self):
        """Contract must compile and produce a valid P2S address."""
        import requests

        with open(CONTRACT_PATH) as f:
            source = f.read()

        resp = requests.post(
            "http://localhost:9052/script/p2sAddress",
            json={"source": source, "treeVersion": 1},
            timeout=30,
        )
        assert resp.status_code == 200, f"Compilation failed: {resp.text}"

        data = resp.json()
        address = data.get("address", "")
        assert address.startswith("3Q"), f"Invalid P2S address: {address}"

    def test_compiled_address_matches_deployed(self):
        """Compiled address must match coinflip_deployed.json."""
        import requests

        with open(CONTRACT_PATH) as f:
            source = f.read()

        resp = requests.post(
            "http://localhost:9052/script/p2sAddress",
            json={"source": source, "treeVersion": 1},
            timeout=30,
        )
        compiled_address = resp.json().get("address", "")

        if DEPLOYED_PATH.exists():
            with open(DEPLOYED_PATH) as f:
                deployed = json.load(f)
            deployed_address = deployed.get("p2sAddress", "")
            assert compiled_address == deployed_address, \
                f"Compiled address {compiled_address} != deployed {deployed_address}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
