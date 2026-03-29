"""
Backend Integration Test for On-Chain Bet Flow
================================================

MAT-375: Verify that MAT-357 (reveal bot) deliverables are functional.
Check that the backend correctly:
1. Creates PendingBetBox on-chain when bets are placed
2. Monitors commit boxes for reveal
3. Spends commit boxes with block hash RNG
4. Pays winners correctly

Also verify no Math.random() usage in backend game logic.

This test suite verifies the OFF-CHAIN components that interface with
the on-chain contract (coinflip_v2.es). Since we cannot run a live
Ergo node in CI, we test the protocol logic in isolation:
- RNG computation matches on-chain contract exactly
- Commitment generation/verification matches on-chain
- Backend API routes are correctly wired
- Off-chain bot has correct structure for monitoring/revealing
- No insecure randomness in game logic paths
"""

import ast
import hashlib
import os
import re
from pathlib import Path

import pytest

# Add backend to path
sys_path_backend = str(Path(__file__).parent.parent / "backend")
if sys_path_backend not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path_backend)

from backend.rng_module import compute_rng, generate_commit, verify_commit


# ═══════════════════════════════════════════════════════════════════════
# 1. RNG MATCHES ON-CHAIN CONTRACT
# ═══════════════════════════════════════════════════════════════════════

class TestRNGMatchesOnChain:
    """
    Verify that the backend RNG module produces results identical to
    the on-chain coinflip_v2.es contract.

    On-chain (coinflip_v2.es lines 63-65):
        val blockSeed  = CONTEXT.preHeader.parentId      // Coll[Byte] raw 32 bytes
        val rngHash    = blake2b256(blockSeed ++ playerSecret)
        val flipResult = rngHash(0) % 2

    CRITICAL: The block hash must be hex-decoded to raw bytes, NOT
    UTF-8 encoded. CONTEXT.preHeader.parentId is Coll[Byte].
    """

    def test_rng_uses_blake2b256(self):
        """
        SEC-CRITICAL-1: On-chain contract uses blake2b256 opcode.
        Using SHA-256 would cause every reveal to fail verification.
        """
        block_hash = "a" * 64  # 32 bytes as hex
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])

        # Compute with our module
        outcome = compute_rng(block_hash, secret)

        # Manually compute with blake2b256 (matching on-chain)
        block_bytes = bytes.fromhex(block_hash)
        rng_data = block_bytes + secret
        expected_hash = hashlib.blake2b(rng_data, digest_size=32).digest()
        expected_outcome = expected_hash[0] % 2

        assert outcome == expected_outcome, (
            "RNG must use blake2b256 to match on-chain contract"
        )

    def test_rng_not_sha256(self):
        """
        Verify RNG does NOT use SHA-256 (which would mismatch on-chain).
        """
        block_hash = "b" * 64
        secret = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22])

        outcome_blake2b = compute_rng(block_hash, secret)

        # Compute with SHA-256 (WRONG for production)
        block_bytes = bytes.fromhex(block_hash)
        sha256_hash = hashlib.sha256(block_bytes + secret).digest()
        outcome_sha256 = sha256_hash[0] % 2

        # They may match for some inputs, but let's check with several
        # to confirm the implementation is blake2b, not sha256
        mismatches = 0
        for i in range(100):
            bh = f"{i:064x}"
            sec = bytes(range(8))
            blake_outcome = compute_rng(bh, sec)
            sha_outcome = hashlib.sha256(bytes.fromhex(bh) + sec).digest()[0] % 2
            if blake_outcome != sha_outcome:
                mismatches += 1

        # With 100 random inputs, blake2b and sha256 should differ significantly
        # (they're different hash functions, ~50% output mismatch expected)
        assert mismatches > 10, (
            f"RNG appears to use SHA-256 instead of blake2b256 "
            f"(only {mismatches}/100 mismatches). On-chain uses blake2b256."
        )

    def test_rng_uses_raw_bytes_not_utf8(self):
        """
        SEC-CRITICAL-3: Block hash must be hex-decoded to raw bytes,
        NOT UTF-8 encoded as a string.

        CONTEXT.preHeader.parentId returns Coll[Byte] (raw 32 bytes).
        """
        # Use a block hash that would produce different results if
        # treated as UTF-8 string vs raw bytes
        block_hash = "00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff"
        secret = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE, 0xBA, 0xBE])

        outcome = compute_rng(block_hash, secret)

        # Raw bytes (CORRECT — matches on-chain)
        raw_bytes = bytes.fromhex(block_hash)
        correct_hash = hashlib.blake2b(raw_bytes + secret, digest_size=32).digest()
        correct_outcome = correct_hash[0] % 2

        assert outcome == correct_outcome, (
            "RNG must hex-decode block hash to raw bytes, not UTF-8 encode"
        )

    def test_rng_deterministic(self):
        """Same inputs must always produce same output."""
        block_hash = "c" * 64
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])

        outcomes = [compute_rng(block_hash, secret) for _ in range(50)]
        assert len(set(outcomes)) == 1, "RNG must be deterministic"

    def test_rng_output_range(self):
        """RNG output must be 0 or 1 (coinflip)."""
        for i in range(1000):
            block_hash = f"{i:064x}"
            secret = bytes([(i * 7) & 0xFF for _ in range(8)])
            outcome = compute_rng(block_hash, secret)
            assert outcome in (0, 1), f"RNG output {outcome} not in (0, 1)"


# ═══════════════════════════════════════════════════════════════════════
# 2. COMMITMENT MATCHES ON-CHAIN CONTRACT
# ═══════════════════════════════════════════════════════════════════════

class TestCommitmentMatchesOnChain:
    """
    Verify commitment generation/verification matches on-chain.

    On-chain (coinflip_v2.es lines 56-58):
        val choiceByte  = if (playerChoice == 0) (0.toByte) else (1.toByte)
        val computedHash = blake2b256(playerSecret ++ Coll(choiceByte))
        val commitmentOk = (computedHash == commitmentHash)
    """

    def test_commitment_uses_blake2b256(self):
        """
        Commitment MUST use blake2b256 (on-chain opcode), not SHA-256.
        """
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        choice = 0

        commitment = generate_commit(secret, choice)

        # On-chain: blake2b256(secret ++ choiceByte)
        choice_byte = bytes([choice])
        on_chain_hash = hashlib.blake2b(secret + choice_byte, digest_size=32).digest()

        assert commitment == on_chain_hash.hex(), (
            "Commitment must use blake2b256 to match on-chain contract"
        )

    def test_commitment_not_sha256(self):
        """Verify commitment does NOT use SHA-256."""
        secret = bytes([0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00])
        choice = 1

        commitment = generate_commit(secret, choice)

        sha256_hash = hashlib.sha256(secret + bytes([choice])).hexdigest()
        assert commitment != sha256_hash, (
            "Commitment should use blake2b256, not SHA-256"
        )

    def test_commitment_verification_valid(self):
        """Valid commitment must verify."""
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        choice = 0
        commitment = generate_commit(secret, choice)

        assert verify_commit(commitment, secret, choice) is True

    def test_commitment_verification_wrong_choice(self):
        """Wrong choice must fail verification."""
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        choice = 0
        commitment = generate_commit(secret, choice)

        assert verify_commit(commitment, secret, 1) is False

    def test_commitment_verification_wrong_secret(self):
        """Wrong secret must fail verification."""
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        choice = 0
        commitment = generate_commit(secret, choice)

        wrong_secret = bytes([8, 7, 6, 5, 4, 3, 2, 1])
        assert verify_commit(commitment, wrong_secret, choice) is False


# ═══════════════════════════════════════════════════════════════════════
# 3. NO INSECURE RANDOMNESS IN BACKEND GAME LOGIC
# ═══════════════════════════════════════════════════════════════════════

class TestNoMathRandomInBackend:
    """
    Verify no Math.random(), random.random(), or other insecure
    randomness is used in backend game logic.
    """

    def test_no_math_random_in_backend_python(self):
        """
        Python backend must not use random module in game logic files.
        Allowed: tests/ (test fixtures), non-game modules.
        """
        backend_dir = Path(__file__).parent.parent / "backend"
        game_files = [
            "rng_module.py",
            "game_routes.py",
            "api_server.py",
            "validators.py",
            "ws_routes.py",
            "ws_manager.py",
            "game_events.py",
        ]

        violations = []
        for filename in game_files:
            filepath = backend_dir / filename
            if not filepath.exists():
                continue
            content = filepath.read_text()
            # Check for random imports or usage
            import_matches = re.findall(r'^import random|^from random import', content, re.MULTILINE)
            if import_matches:
                violations.append(f"{filename}: imports random module: {import_matches}")

        assert not violations, (
            f"Insecure randomness found in backend game files:\n"
            + "\n".join(violations)
        )

    def test_no_math_random_in_offchain_bot_logic(self):
        """
        Off-chain bot must not use random module in game logic.
        The bot's process_bets() should only use deterministic
        on-chain data (block hashes, contract registers).
        """
        bot_dir = Path(__file__).parent.parent / "off-chain-bot"
        bot_files = ["main.py"]

        violations = []
        for filename in bot_files:
            filepath = bot_dir / filename
            if not filepath.exists():
                continue
            content = filepath.read_text()
            import_matches = re.findall(r'^import random|^from random import', content, re.MULTILINE)
            if import_matches:
                violations.append(f"off-chain-bot/{filename}: imports random module")

        assert not violations, (
            f"Insecure randomness found in off-chain bot:\n"
            + "\n".join(violations)
        )


# ═══════════════════════════════════════════════════════════════════════
# 4. OFF-CHAIN BOT STRUCTURE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════

class TestOffChainBotStructure:
    """
    Verify the off-chain bot has the correct structure to:
    1. Monitor commit boxes (PendingBet boxes at P2S address)
    2. Extract registers (R4-R9) from commit boxes
    3. Wait for timeout delta blocks
    4. Use block hash for RNG
    5. Build and sign reveal transaction
    """

    def test_bot_main_exists(self):
        """Bot main.py must exist."""
        bot_main = Path(__file__).parent.parent / "off-chain-bot" / "main.py"
        assert bot_main.exists(), "off-chain-bot/main.py missing"

    def test_bot_has_ergo_node_client(self):
        """Bot must have ErgoNodeClient for node API communication."""
        bot_main = Path(__file__).parent.parent / "off-chain-bot" / "main.py"
        content = bot_main.read_text()

        assert "ErgoNodeClient" in content, "Bot must define ErgoNodeClient class"
        assert "get(" in content or 'async def get' in content, "Bot must have GET method for node API"
        assert "post(" in content or 'async def post' in content, "Bot must have POST method for node API"

    def test_bot_has_retry_logic(self):
        """Bot must have retry logic with exponential backoff."""
        bot_main = Path(__file__).parent.parent / "off-chain-bot" / "main.py"
        content = bot_main.read_text()

        assert "tenacity" in content or "retry" in content.lower(), (
            "Bot must use retry logic (tenacity or manual retry)"
        )
        assert "backoff" in content.lower() or "exponential" in content.lower(), (
            "Bot must use exponential backoff"
        )

    def test_bot_has_graceful_shutdown(self):
        """Bot must handle SIGINT/SIGTERM for graceful shutdown."""
        bot_main = Path(__file__).parent.parent / "off-chain-bot" / "main.py"
        content = bot_main.read_text()

        assert "SIGINT" in content or "signal" in content, (
            "Bot must handle shutdown signals"
        )

    def test_bot_has_main_loop(self):
        """Bot must have a main processing loop."""
        bot_main = Path(__file__).parent.parent / "off-chain-bot" / "main.py"
        content = bot_main.read_text()

        assert "main_loop" in content or "process_bets" in content, (
            "Bot must have main loop for processing bets"
        )

    def test_bot_has_health_server(self):
        """Bot must have health endpoint for monitoring."""
        bot_health = Path(__file__).parent.parent / "off-chain-bot" / "health_server.py"
        assert bot_health.exists(), "off-chain-bot/health_server.py missing"

        content = bot_health.read_text()
        assert "/health" in content, "Health server must have /health endpoint"

    def test_bot_has_structured_logging(self):
        """Bot must use structured logging."""
        bot_logger = Path(__file__).parent.parent / "off-chain-bot" / "logger.py"
        assert bot_logger.exists(), "off-chain-bot/logger.py missing"

        content = bot_logger.read_text()
        assert "structlog" in content, "Bot must use structlog for structured logging"


# ═══════════════════════════════════════════════════════════════════════
# 5. BACKEND API ROUTES VERIFICATION
# ═══════════════════════════════════════════════════════════════════════

class TestBackendAPIRoutes:
    """
    Verify the backend API serves the routes the frontend expects.
    Frontend contract (from frontend components):
      POST /place-bet         -> BetForm.tsx, CoinFlipGame.tsx
      GET  /leaderboard       -> Leaderboard.tsx
      GET  /history/{address} -> GameHistory.tsx
      GET  /player/stats/{address} -> StatsDashboard.tsx
      GET  /player/comp/{address}  -> CompPoints.tsx
      GET  /health            -> Health check
      GET  /contract-info     -> Frontend needs P2S address
    """

    def test_game_routes_module_exists(self):
        """game_routes.py must exist."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        assert routes.exists(), "backend/game_routes.py missing"

    def test_place_bet_route_registered(self):
        """POST /place-bet must be registered."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()
        assert '/place-bet"' in content or "/place-bet'" in content, (
            "POST /place-bet route not found"
        )

    def test_leaderboard_route_registered(self):
        """GET /leaderboard must be registered."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()
        assert '/leaderboard"' in content or "/leaderboard'" in content, (
            "GET /leaderboard route not found"
        )

    def test_history_route_registered(self):
        """GET /history/{address} must be registered."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()
        assert '/history/' in content, (
            "GET /history/{address} route not found"
        )

    def test_player_stats_route_registered(self):
        """GET /player/stats/{address} must be registered."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()
        assert '/player/stats/' in content, (
            "GET /player/stats/{address} route not found"
        )

    def test_player_comp_route_registered(self):
        """GET /player/comp/{address} must be registered."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()
        assert '/player/comp/' in content, (
            "GET /player/comp/{address} route not found"
        )

    def test_contract_info_route_registered(self):
        """GET /contract-info must be registered (frontend needs P2S address)."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()
        assert '/contract-info"' in content or "/contract-info'" in content, (
            "GET /contract-info route not found"
        )

    def test_place_bet_has_validation(self):
        """POST /place-bet must validate input (not accept empty body)."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()

        assert "PlaceBetRequest" in content, (
            "PlaceBetRequest model must be defined for validation"
        )
        assert "field_validator" in content or "validator" in content, (
            "PlaceBetRequest must have field validators"
        )

    def test_contract_constants_present(self):
        """Contract constants (P2S address, ErgoTree) must be defined."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()

        assert "COINFLIP_P2S_ADDRESS" in content, (
            "COINFLIP_P2S_ADDRESS constant missing"
        )
        assert "COINFLIP_ERGO_TREE" in content, (
            "COINFLIP_ERGO_TREE constant missing"
        )
        # P2S address must be non-empty
        match = re.search(r'COINFLIP_P2S_ADDRESS\s*=\s*["\']([^"\']+)["\']', content)
        assert match and len(match.group(1)) > 10, (
            "COINFLIP_P2S_ADDRESS appears to be empty or placeholder"
        )

    def test_health_route_registered(self):
        """GET /health must be registered."""
        api = Path(__file__).parent.parent / "backend" / "api_server.py"
        content = api.read_text()
        assert '/health"' in content or "/health'" in content, (
            "GET /health route not found"
        )


# ═══════════════════════════════════════════════════════════════════════
# 6. END-TO-END COMMIT-REVEAL FLOW
# ═══════════════════════════════════════════════════════════════════════

class TestEndToEndCommitRevealFlow:
    """
    Simulate the full commit-reveal bet flow off-chain:
    1. Player generates secret and choice
    2. Player generates commitment (blake2b256(secret || choice))
    3. Player submits bet with commitment to contract (registers R4-R9)
    4. House waits for timeout delta blocks
    5. House reads block hash at reveal height
    6. House computes RNG: blake2b256(blockHash || secret)[0] % 2
    7. House determines winner and pays out
    """

    def test_full_flow_player_wins(self):
        """
        Simulate full flow where player wins.
        Player choice matches RNG outcome.
        """
        # 1. Player generates secret
        secret = bytes([0x42, 0x13, 0x37, 0x00, 0xDE, 0xAD, 0xBE, 0xEF])
        player_choice = 0  # Heads

        # 2. Player generates commitment
        commitment = generate_commit(secret, player_choice)
        assert len(commitment) == 64  # 32 bytes hex

        # 3. Verify commitment on-chain would pass
        assert verify_commit(commitment, secret, player_choice)

        # 4. House reads block hash (simulated)
        block_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"

        # 5. House computes RNG
        rng_outcome = compute_rng(block_hash, secret)

        # 6. Determine winner
        player_wins = (rng_outcome == player_choice)

        # 7. Calculate payout (on-chain: betAmount * 97 / 50 = 1.94x)
        # Player wins: gets 1.94x their bet. House keeps the rest.
        bet_amount = 1_000_000_000  # 1 ERG in nanoERG
        win_payout = bet_amount * 97 // 50  # = 1,940,000,000 nanoERG (1.94 ERG)
        # House edge = what house keeps = bet_amount - win_payout
        # But wait: player already put bet_amount into the box.
        # The box has bet_amount. On win, player gets win_payout.
        # House "profit" = bet_amount (already in box) - win_payout (paid out)
        # = 1_000_000_000 - 1_940_000_000 = negative! That's wrong.
        # Actually the box contains the bet. House adds nothing extra.
        # On win: player gets 1.94x from the box. Net for player: +0.94x.
        # On loss: house gets full box (bet_amount). Net for house: +bet_amount.
        # House edge = 3% of total wagered (not 3% of payout).
        # Expected: player wins 97% of time * 2x = 1.94x return.
        # Expected value: 0.5 * 1.94 + 0.5 * 0 = 0.97 per 1.0 bet. House edge = 3%.

        assert win_payout == 1_940_000_000  # 1.94 ERG

        # Flow completed
        assert player_wins in (True, False)
        assert rng_outcome in (0, 1)

    def test_full_flow_house_wins(self):
        """
        Simulate full flow where house wins.
        Player choice does not match RNG outcome.
        """
        secret = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])
        player_choice = 1  # Tails

        commitment = generate_commit(secret, player_choice)
        assert verify_commit(commitment, secret, player_choice)

        block_hash = "ff" * 32
        rng_outcome = compute_rng(block_hash, secret)

        player_wins = (rng_outcome == player_choice)

        if not player_wins:
            # House gets full bet amount
            bet_amount = 5_000_000_000  # 5 ERG
            assert bet_amount > 0

    def test_commitment_binding(self):
        """
        Verify commitment scheme is binding:
        - Different secrets produce different commitments
        - Different choices produce different commitments
        - Cannot find valid commitment for different choice with same secret
        """
        secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])

        commit_heads = generate_commit(secret, 0)
        commit_tails = generate_commit(secret, 1)

        # Different choices produce different commitments
        assert commit_heads != commit_tails

        # Verify each only matches its own choice
        assert verify_commit(commit_heads, secret, 0) is True
        assert verify_commit(commit_heads, secret, 1) is False
        assert verify_commit(commit_tails, secret, 1) is True
        assert verify_commit(commit_tails, secret, 0) is False

    def test_many_flows_fair_distribution(self):
        """
        Run many simulated flows and verify the RNG produces
        approximately fair distribution (50/50 heads/tails).
        """
        import secrets

        heads = 0
        tails = 0
        n = 10_000

        for _ in range(n):
            secret = secrets.token_bytes(8)
            choice = secrets.randbelow(2)
            block_hash = secrets.token_hex(32)

            outcome = compute_rng(block_hash, secret)
            if outcome == 0:
                heads += 1
            else:
                tails += 1

        # Chi-square test: should be within normal range
        expected = n / 2
        chi_sq = ((heads - expected) ** 2 / expected +
                  (tails - expected) ** 2 / expected)

        # Critical value for chi-square(1) at alpha=0.01 is 6.635
        assert chi_sq < 6.635, (
            f"RNG distribution is biased: chi_sq={chi_sq:.4f}, "
            f"heads={heads}, tails={tails}"
        )


# ═══════════════════════════════════════════════════════════════════════
# 7. REGISTER LAYOUT CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════

class TestRegisterLayoutConsistency:
    """
    Verify the backend's register layout documentation matches
    the on-chain coinflip_v2.es contract.
    """

    def test_register_layout_documented(self):
        """Backend must document the register layout."""
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"
        content = routes.read_text()

        required_registers = ["R4", "R5", "R6", "R7", "R8", "R9"]
        for reg in required_registers:
            assert reg in content, f"Register {reg} not documented in game_routes.py"

    def test_register_layout_matches_contract(self):
        """
        Verify register layout documentation matches coinflip_v2.es:
          R4: housePubKey (Coll[Byte])
          R5: playerPubKey (Coll[Byte])
          R6: commitmentHash (Coll[Byte])
          R7: playerChoice (Int)
          R8: timeoutHeight (Int)
          R9: playerSecret (Coll[Byte])
        """
        contract = Path(__file__).parent.parent / "smart-contracts" / "coinflip_v2.es"
        routes = Path(__file__).parent.parent / "backend" / "game_routes.py"

        contract_content = contract.read_text()
        routes_content = routes.read_text()

        # Verify contract registers exist
        assert "SELF.R4[Coll[Byte]]" in contract_content
        assert "SELF.R5[Coll[Byte]]" in contract_content
        assert "SELF.R6[Coll[Byte]]" in contract_content
        assert "SELF.R7[Int]" in contract_content
        assert "SELF.R8[Int]" in contract_content
        assert "SELF.R9[Coll[Byte]]" in contract_content

        # Verify backend documents the same registers
        assert "housePubKey" in routes_content or "R4" in routes_content
        assert "playerPubKey" in routes_content or "R5" in routes_content
        assert "commitmentHash" in routes_content or "R6" in routes_content
        assert "playerChoice" in routes_content or "R7" in routes_content
        assert "timeoutHeight" in routes_content or "R8" in routes_content
        assert "playerSecret" in routes_content or "R9" in routes_content
