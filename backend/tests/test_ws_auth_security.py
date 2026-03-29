"""
Tests for MAT-335: WebSocket auth signature verification.

Verifies that:
1. The /ws/challenge endpoint issues valid nonces
2. The /ws/auth endpoint REJECTS requests without a valid challenge
3. The /ws/auth endpoint REJECTS requests when the Ergo node is unreachable
4. The /ws/auth endpoint REJECTS requests with invalid signatures
5. The /ws/auth endpoint ACCEPTS requests with valid node-verified signatures
6. Challenge nonces are single-use (replay protection)
7. Challenge nonces expire after TTL
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

# Import the app and modules under test
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def valid_address():
    """A valid Ergo mainnet P2PK address (for testing only, not a real keypair)."""
    return "3WxRf1bQWfSVDkFh7sQxkBPjZKZDrA3cLZqPbRKEJFNAouXo2FVq"


@pytest.fixture
def valid_challenge_hex():
    """A valid 64-char hex challenge nonce."""
    return "a" * 64


@pytest.fixture
def mock_node_verify_success():
    """Mock the Ergo node to return a successful signature verification."""
    return {
        "result": True,
    }


@pytest.fixture
def mock_node_verify_failure():
    """Mock the Ergo node to return a failed signature verification."""
    return {
        "result": False,
    }


# ─── Helper to create app ──────────────────────────────────────

def _create_app():
    """Create a minimal FastAPI app with the ws_routes router."""
    from fastapi import FastAPI
    import ws_routes

    app = FastAPI()
    app.include_router(ws_routes.router)

    # Initialize ws_manager on app state (needed by WebSocket endpoint)
    from ws_manager import ConnectionManager
    app.state.ws_manager = ConnectionManager()

    return app


# ─── Test: Challenge Endpoint ──────────────────────────────────

@pytest.mark.asyncio
async def test_challenge_returns_valid_nonce(valid_address):
    """POST /ws/challenge should return a 64-char hex nonce."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/ws/challenge", json={
            "address": valid_address,
        })

    assert response.status_code == 200
    data = response.json()
    assert "challenge" in data
    assert "address" in data
    assert "expires_at" in data

    # Challenge should be 64-char hex
    challenge = data["challenge"]
    assert len(challenge) == 64
    int(challenge, 16)  # Should not raise

    # Address should be lowercased
    assert data["address"] == valid_address.lower()

    # Expiry should be in the future
    assert data["expires_at"] > time.time()


@pytest.mark.asyncio
async def test_challenge_rejects_invalid_address():
    """POST /ws/challenge should reject addresses with wrong prefix."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/ws/challenge", json={
            "address": "1Aaaaaaaaaaaaaaaaaaaaaaaaaa",  # Wrong prefix
        })

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_challenge_rejects_short_address():
    """POST /ws/challenge should reject addresses that are too short."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/ws/challenge", json={
            "address": "3short",
        })

    assert response.status_code == 422


# ─── Test: Auth Endpoint - Challenge Required ──────────────────

@pytest.mark.asyncio
async def test_auth_rejects_without_challenge(valid_address, valid_challenge_hex):
    """POST /ws/auth should reject requests where the challenge was never issued."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/ws/auth", json={
            "address": valid_address,
            "challenge": valid_challenge_hex,
            "signature": "any_signature_valid",
        })

    assert response.status_code == 401
    assert "challenge" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_rejects_reused_challenge(valid_address):
    """POST /ws/auth should reject replayed challenge nonces."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Get a challenge
        challenge_resp = await client.post("/ws/challenge", json={
            "address": valid_address,
        })
        challenge = challenge_resp.json()["challenge"]

        # Step 2: Mock node to verify successfully
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": True}

        with patch("ws_routes.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            # First use: should succeed
            auth_resp = await client.post("/ws/auth", json={
                "address": valid_address,
                "challenge": challenge,
                "signature": "valid_provedlog_signature_hex",
            })
            assert auth_resp.status_code == 200

        # Step 3: Replay the same challenge — should be rejected
        auth_resp2 = await client.post("/ws/auth", json={
            "address": valid_address,
            "challenge": challenge,
            "signature": "valid_provedlog_signature_hex",
        })
        assert auth_resp2.status_code == 401


# ─── Test: Auth Endpoint - Node Verification ───────────────────

@pytest.mark.asyncio
async def test_auth_rejects_when_node_unreachable(valid_address):
    """POST /ws/auth should fail-closed when the Ergo node is unreachable."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get a valid challenge
        challenge_resp = await client.post("/ws/challenge", json={
            "address": valid_address,
        })
        challenge = challenge_resp.json()["challenge"]

        # Mock node to be unreachable (ConnectError)
        with patch("ws_routes.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            mock_client_cls.return_value = mock_client

            auth_resp = await client.post("/ws/auth", json={
                "address": valid_address,
                "challenge": challenge,
                "signature": "some_provedlog_sig_hex",
            })

    assert auth_resp.status_code == 401
    assert "verification failed" in auth_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_rejects_invalid_signature(valid_address):
    """POST /ws/auth should reject when the node says signature is invalid."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get a valid challenge
        challenge_resp = await client.post("/ws/challenge", json={
            "address": valid_address,
        })
        challenge = challenge_resp.json()["challenge"]

        # Mock node to say signature is INVALID
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": False}

        with patch("ws_routes.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            auth_resp = await client.post("/ws/auth", json={
                "address": valid_address,
                "challenge": challenge,
                "signature": "bad_provedlog_signature_hex",
            })

    assert auth_resp.status_code == 401
    assert "verification failed" in auth_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_accepts_valid_signature(valid_address):
    """POST /ws/auth should accept when the node confirms the signature."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get a valid challenge
        challenge_resp = await client.post("/ws/challenge", json={
            "address": valid_address,
        })
        challenge = challenge_resp.json()["challenge"]

        # Mock node to say signature is VALID
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": True}

        with patch("ws_routes.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            auth_resp = await client.post("/ws/auth", json={
                "address": valid_address,
                "challenge": challenge,
                "signature": "valid_provedlog_signature_hex",
            })

    assert auth_resp.status_code == 200
    data = auth_resp.json()
    assert "token" in data
    assert "expires_at" in data
    assert data["expires_at"] > time.time()


# ─── Test: Challenge Expiry ────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_rejects_expired_challenge(valid_address):
    """POST /ws/auth should reject challenges that have expired."""
    import ws_routes

    app = _create_app()

    # Inject a pre-expired challenge directly
    old_ttl = ws_routes.CHALLENGE_TTL_SECONDS
    try:
        ws_routes.CHALLENGE_TTL_SECONDS = 0  # Expire immediately

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            challenge_resp = await client.post("/ws/challenge", json={
                "address": valid_address,
            })
            challenge = challenge_resp.json()["challenge"]

            # Wait a tiny bit to ensure expiry
            await asyncio.sleep(0.1)

            auth_resp = await client.post("/ws/auth", json={
                "address": valid_address,
                "challenge": challenge,
                "signature": "sig_valid_length_ok",
            })

        assert auth_resp.status_code == 401
    finally:
        ws_routes.CHALLENGE_TTL_SECONDS = old_ttl


# ─── Test: Address Mismatch on Challenge ───────────────────────

@pytest.mark.asyncio
async def test_auth_rejects_address_mismatch(valid_address):
    """POST /ws/auth should reject when challenge was issued for a different address."""
    other_address = "9iDwN2wExYuBu7VEGJwRnTGjDwRhrSe5cJCt4wKAWbVEmNgcSmV"

    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get challenge for address A
        challenge_resp = await client.post("/ws/challenge", json={
            "address": valid_address,
        })
        challenge = challenge_resp.json()["challenge"]

        # Try to auth as address B with A's challenge
        auth_resp = await client.post("/ws/auth", json={
            "address": other_address,
            "challenge": challenge,
            "signature": "sig_valid_length_ok",
        })

    assert auth_resp.status_code == 401


# ─── Test: Input Validation ────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_rejects_empty_signature(valid_address, valid_challenge_hex):
    """POST /ws/auth should reject empty signatures."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/ws/auth", json={
            "address": valid_address,
            "challenge": valid_challenge_hex,
            "signature": "",
        })

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_rejects_invalid_challenge_format(valid_address):
    """POST /ws/auth should reject non-hex challenges."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/ws/auth", json={
            "address": valid_address,
            "challenge": "not-hex-at-all!!!!!",
            "signature": "somesig_valid_length",
        })

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_rejects_wrong_challenge_length(valid_address):
    """POST /ws/auth should reject challenges with wrong length."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/ws/auth", json={
            "address": valid_address,
            "challenge": "abcdef",  # Too short
            "signature": "somesig_valid_length",
        })

    assert response.status_code == 422


# ─── Test: Old API (message field) is removed ──────────────────

@pytest.mark.asyncio
async def test_auth_rejects_old_message_field(valid_address):
    """The old API with 'message' field should no longer work."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Old API: used 'message' instead of 'challenge'
        response = await client.post("/ws/auth", json={
            "address": valid_address,
            "message": "sign this",
            "signature": "any_signature_valid",
        })

    # Should get 422 because 'challenge' is now required and 'message' is not accepted
    assert response.status_code == 422
