"""
Phase 7 — E2E Integration Test Fixtures

Shared infrastructure for full-stack integration tests.
Provides a testable FastAPI app with mocked Ergo node, test
wallets, and helpers for the commit-reveal flow.
"""

import asyncio
import hashlib
import os
import secrets
from typing import Any, Dict, Generator

# CRITICAL: Set env vars BEFORE any backend imports.
# api_server.py calls sys.exit(1) if NODE_API_KEY is missing at import time.
os.environ.setdefault("NODE_API_KEY", "test-api-key")
os.environ.setdefault("NODE_URL", "http://localhost:9052")
os.environ.setdefault("CORS_ORIGINS_STR", "http://localhost:3000")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure backend is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "e2e: End-to-end integration test")
    config.addinivalue_line("markers", "slow: Tests that take > 1s")
    config.addinivalue_line("markers", "concurrent: Tests involving concurrent requests")

# ─── Mock Ergo Node ──────────────────────────────────────────────────

class MockErgoNode:
    """In-process mock of the Ergo node REST API for testing."""

    def __init__(self):
        self._boxes: Dict[str, Dict] = {}  # boxId -> box data
        self._txs: list = []
        self._height = 100_000
        self._block_hashes: Dict[int, str] = {}  # height -> hash
        self._wallet_balance = 10_000_000_000  # 10,000 ERG in nanoERG

    def info(self) -> Dict[str, Any]:
        return {"fullHeight": self._height, "bestHeaderId": "mock_header"}

    def wallet_status(self) -> Dict[str, Any]:
        return {"isInitialized": True, "isUnlocked": True}

    def wallet_balance(self) -> Dict[str, Any]:
        return {
            "nanoERGs": self._wallet_balance,
            "tokens": [],
        }

    def generate_block_hash(self, height: int) -> str:
        """Deterministic-ish hash per height for RNG tests."""
        if height not in self._block_hashes:
            self._block_hashes[height] = hashlib.sha256(
                f"block-{height}-{secrets.token_hex(4)}".encode()
            ).hexdigest()
        return self._block_hashes[height]

    def advance_blocks(self, n: int = 1):
        """Advance chain height by n blocks."""
        for i in range(1, n + 1):
            self._height += 1
            self.generate_block_hash(self._height)

    def register_box(self, box_id: str, box_data: Dict):
        self._boxes[box_id] = box_data

    def spend_box(self, box_id: str) -> Dict:
        return self._boxes.pop(box_id, None)

    def submit_tx(self, tx: Dict) -> str:
        tx_id = hashlib.sha256(str(tx).encode()).hexdigest()[:64]
        self._txs.append(tx)
        return tx_id


# ─── Test Wallets ────────────────────────────────────────────────────

TEST_PLAYER_ADDRESS = "9iUk8HPLX4RMRt2xXN1CzqZvE5W5B4YxZ7Xj8N9W5E8RjK4Q9Z"
TEST_HOUSE_ADDRESS = "3WyrB3D5AMpyEc88UJ7FdsBMXAZKwzQzkKeDbAQVfXytDPgxF26"
TEST_HOUSE_PUBKEY = (
    "02a1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1"
)
TEST_PLAYER_PUBKEY = (
    "03b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"
)


# ─── Commit-Reveal Helpers ───────────────────────────────────────────

def generate_commitment(secret: bytes, choice: int) -> str:
    """
    Generate a blake2b256 commitment hash for commit-reveal scheme.
    Mirrors the on-chain contract: blake2b256(secret || choice_byte)
    """
    choice_byte = bytes([choice])
    preimage = secret + choice_byte
    return hashlib.blake2b(preimage, digest_size=32).hexdigest()


def generate_player_secret(n: int = 32) -> bytes:
    """Generate n random bytes for player secret."""
    return secrets.token_bytes(n)


def make_place_bet_payload(
    address: str = TEST_PLAYER_ADDRESS,
    amount_nanoerg: int = 100_000_000,  # 0.1 ERG
    choice: int = 0,
    bet_id: str = None,
) -> Dict[str, Any]:
    """Build a valid /place-bet request payload."""
    secret = generate_player_secret()
    commitment = generate_commitment(secret, choice)
    return {
        "address": address,
        "amount": str(amount_nanoerg),
        "choice": choice,
        "commitment": commitment,
        "betId": bet_id or f"test-bet-{secrets.token_hex(8)}",
    }


# ─── App Fixture (TestClient against real FastAPI app) ───────────────

@pytest.fixture(scope="session")
def mock_node():
    """Shared mock Ergo node for the session."""
    return MockErgoNode()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def app_client(mock_node) -> Generator[AsyncClient, None, None]:
    """
    Session-scoped AsyncClient wired to the real FastAPI app.
    """
    # Env vars are set at module level (above) to prevent sys.exit in api_server
    from api_server import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def reset_bets():
    """
    Reset the in-memory bet store between tests.
    game_routes._bets is a module-level list; we clear it.
    """
    yield
    try:
        import game_routes
        game_routes._bets.clear()
        game_routes._pool_stats["totalBets"] = 0
        game_routes._pool_stats["totalFees"] = "0"
    except ImportError:
        pass


@pytest_asyncio.fixture
async def player_client(app_client) -> AsyncClient:
    """AsyncClient pre-configured for a test player."""
    return app_client


@pytest_asyncio.fixture
def unique_bet_id() -> str:
    """Generate a unique bet ID for each test."""
    return f"e2e-bet-{secrets.token_hex(12)}"
