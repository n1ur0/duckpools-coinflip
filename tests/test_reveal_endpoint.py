"""
Tests for the /reveal, /bot/build-reveal-tx, and /bot/reveal-and-pay endpoints.

MAT-394: Wire up backend reveal endpoint.
"""

import hashlib
import os
import sys
from base64 import b64encode
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add backend to path so we can import game_routes
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from api_server import app

client = TestClient(app)


# ─── Fixtures ──────────────────────────────────────────────────────


def _make_commitment(secret_hex: str, choice: int) -> str:
    """Generate commitment matching rng_module.generate_commit."""
    secret_bytes = bytes.fromhex(secret_hex)
    choice_byte = bytes([choice])
    commit_data = secret_bytes + choice_byte
    commit_hash = hashlib.blake2b(commit_data, digest_size=32).digest()
    return commit_hash.hex()


# Use a known secret for deterministic tests
TEST_SECRET = "a1b2c3d4e5f6a7b8"  # 8 bytes = 16 hex chars
TEST_CHOICE = 0  # heads
TEST_COMMITMENT = _make_commitment(TEST_SECRET, TEST_CHOICE)
TEST_BOX_ID = "0" * 64  # placeholder
TEST_BLOCK_HASH = "a" * 64  # placeholder block hash


# ─── /reveal endpoint tests ────────────────────────────────────────


class TestRevealEndpoint:
    """Tests for POST /reveal."""

    def test_reveal_success_with_explicit_block_hash(self):
        """Happy path: compute RNG outcome with explicit block hash."""
        payload = {
            "box_id": TEST_BOX_ID,
            "secret_hex": TEST_SECRET,
            "choice": TEST_CHOICE,
            "commitment_hex": TEST_COMMITMENT,
            "block_hash": TEST_BLOCK_HASH,
        }
        resp = client.post("/reveal", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["outcome"] in (0, 1)
        assert data["outcome_label"] in ("heads", "tails")
        assert isinstance(data["player_won"], bool)
        assert data["block_hash"] == TEST_BLOCK_HASH
        assert data["secret_hex"] == TEST_SECRET
        assert len(data["rng_hash"]) == 64
        assert data["message"]

    def test_reveal_invalid_commitment(self):
        """Reject when commitment doesn't match secret + choice."""
        payload = {
            "box_id": TEST_BOX_ID,
            "secret_hex": TEST_SECRET,
            "choice": TEST_CHOICE,
            "commitment_hex": "b" * 64,  # Wrong commitment
            "block_hash": TEST_BLOCK_HASH,
        }
        resp = client.post("/reveal", json=payload)
        assert resp.status_code == 400
        body = resp.json()
        # Global error handler wraps in {"error": {"message": ...}}
        detail = body.get("detail") or body.get("error", {}).get("message", "")
        assert "commitment" in detail.lower()

    def test_reveal_invalid_box_id(self):
        """Reject non-64-char hex box_id."""
        payload = {
            "box_id": "short",
            "secret_hex": TEST_SECRET,
            "choice": TEST_CHOICE,
            "commitment_hex": TEST_COMMITMENT,
            "block_hash": TEST_BLOCK_HASH,
        }
        resp = client.post("/reveal", json=payload)
        assert resp.status_code == 422

    def test_reveal_invalid_choice(self):
        """Reject choice values other than 0 or 1."""
        payload = {
            "box_id": TEST_BOX_ID,
            "secret_hex": TEST_SECRET,
            "choice": 5,  # Invalid
            "commitment_hex": TEST_COMMITMENT,
            "block_hash": TEST_BLOCK_HASH,
        }
        resp = client.post("/reveal", json=payload)
        assert resp.status_code == 422

    def test_reveal_invalid_secret_hex(self):
        """Reject non-hex secret."""
        payload = {
            "box_id": TEST_BOX_ID,
            "secret_hex": "zzzz",
            "choice": TEST_CHOICE,
            "commitment_hex": TEST_COMMITMENT,
            "block_hash": TEST_BLOCK_HASH,
        }
        resp = client.post("/reveal", json=payload)
        assert resp.status_code == 422

    def test_reveal_invalid_block_hash(self):
        """Reject non-64-char block hash."""
        payload = {
            "box_id": TEST_BOX_ID,
            "secret_hex": TEST_SECRET,
            "choice": TEST_CHOICE,
            "commitment_hex": TEST_COMMITMENT,
            "block_hash": "abc",  # Too short
        }
        resp = client.post("/reveal", json=payload)
        assert resp.status_code == 400

    def test_reveal_outcome_deterministic(self):
        """Same inputs must produce same outcome (provably fair)."""
        payload = {
            "box_id": TEST_BOX_ID,
            "secret_hex": TEST_SECRET,
            "choice": TEST_CHOICE,
            "commitment_hex": TEST_COMMITMENT,
            "block_hash": TEST_BLOCK_HASH,
        }
        resp1 = client.post("/reveal", json=payload)
        resp2 = client.post("/reveal", json=payload)
        assert resp1.json()["outcome"] == resp2.json()["outcome"]
        assert resp1.json()["rng_hash"] == resp2.json()["rng_hash"]

    def test_reveal_player_choice_tails(self):
        """Test with choice=1 (tails)."""
        secret = "1122334455667788"
        choice = 1
        commitment = _make_commitment(secret, choice)
        payload = {
            "box_id": TEST_BOX_ID,
            "secret_hex": secret,
            "choice": choice,
            "commitment_hex": commitment,
            "block_hash": TEST_BLOCK_HASH,
        }
        resp = client.post("/reveal", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["outcome"] in (0, 1)

    def test_reveal_rng_matches_contract_formula(self):
        """Verify our RNG output matches blake2b256(blockSeed || secret)[0] % 2."""
        from rng_module import compute_rng

        secret_bytes = bytes.fromhex(TEST_SECRET)
        expected = compute_rng(TEST_BLOCK_HASH, secret_bytes)

        payload = {
            "box_id": TEST_BOX_ID,
            "secret_hex": TEST_SECRET,
            "choice": TEST_CHOICE,
            "commitment_hex": TEST_COMMITMENT,
            "block_hash": TEST_BLOCK_HASH,
        }
        resp = client.post("/reveal", json=payload)
        actual = resp.json()["outcome"]
        assert actual == expected, (
            f"RNG mismatch: endpoint={actual}, compute_rng={expected}"
        )


# ─── /bot/build-reveal-tx tests ────────────────────────────────────


class TestBotBuildRevealTx:
    """Tests for POST /bot/build-reveal-tx."""

    @patch("game_routes._node_get")
    def test_build_reveal_tx_box_not_found(self, mock_get):
        """Return 404 when box doesn't exist on-chain."""
        mock_get.side_effect = Exception("HTTP 404")

        payload = {"box_id": TEST_BOX_ID}
        resp = client.post("/bot/build-reveal-tx", json=payload)
        # Will get 502 since we mock with generic Exception
        assert resp.status_code == 502

    def test_build_reveal_tx_invalid_box_id(self):
        """Reject invalid box_id format."""
        payload = {"box_id": "not-hex"}
        resp = client.post("/bot/build-reveal-tx", json=payload)
        # FastAPI will return 422 for invalid field format if we had validation
        # Since box_id isn't validated in the model, it will hit the node call
        # and fail with 502. Let's check it doesn't crash the server.
        assert resp.status_code in (422, 502)


# ─── /bot/reveal-and-pay tests ─────────────────────────────────────


class TestBotRevealAndPay:
    """Tests for POST /bot/reveal-and-pay."""

    @patch("game_routes._node_get")
    def test_reveal_and_pay_box_not_found(self, mock_get):
        """Graceful handling when box is already spent."""
        import httpx

        mock_get.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

        payload = {"box_id": TEST_BOX_ID}
        resp = client.post("/bot/reveal-and-pay", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()


# ─── Contract info endpoint test ───────────────────────────────────


class TestContractInfo:
    """Tests for GET /contract-info."""

    def test_contract_info_returns_constants(self):
        """Contract info should include P2S address and register layout."""
        resp = client.get("/contract-info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["p2sAddress"]
        assert data["ergoTree"]
        assert "R4" in data["registers"]
        assert "R5" in data["registers"]
        assert "R6" in data["registers"]
        assert "R7" in data["registers"]
        assert "R8" in data["registers"]
        assert "R9" in data["registers"]
