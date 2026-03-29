"""
Tests for MAT-350: Bet deduplication (replay attack prevention).

Verifies that:
1. Duplicate betIds are rejected
2. Different betIds are accepted
3. The dedup check is case-sensitive on betId
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))


VALID_ADDRESS = "3WxRf1bQWfSVDkFh7sQxkBPjZKZDrA3cLZqPbRKEJFNAouXo2FVq"
VALID_COMMITMENT = "a" * 64  # 64-char hex blake2b256 hash


def _create_app():
    from fastapi import FastAPI
    import game_routes
    import ws_routes
    from ws_manager import ConnectionManager

    app = FastAPI()
    app.include_router(game_routes.router)
    app.include_router(ws_routes.router)
    app.state.ws_manager = ConnectionManager()
    return app


@pytest.fixture
def bet_payload():
    return {
        "address": VALID_ADDRESS,
        "amount": "10000000",  # 0.01 ERG in nanoERG
        "choice": 0,
        "commitment": VALID_COMMITMENT,
        "betId": "unique-bet-id-001",
    }


@pytest.mark.asyncio
async def test_reject_duplicate_bet_id(bet_payload):
    """Submitting the same betId twice should be rejected on the second attempt."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First submission: should succeed
        resp1 = await client.post("/place-bet", json=bet_payload)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["success"] is True
        assert data1["betId"] == "unique-bet-id-001"

        # Second submission with same betId: should be rejected
        resp2 = await client.post("/place-bet", json=bet_payload)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["success"] is False
        assert "duplicate" in data2["message"].lower()
        assert data2["betId"] == "unique-bet-id-001"


@pytest.mark.asyncio
async def test_accept_different_bet_ids():
    """Two different betIds should both be accepted."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload1 = {
            "address": VALID_ADDRESS,
            "amount": "10000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": "bet-aaa-001",
        }
        payload2 = {
            "address": VALID_ADDRESS,
            "amount": "20000000",
            "choice": 1,
            "commitment": "b" * 64,
            "betId": "bet-bbb-002",
        }

        resp1 = await client.post("/place-bet", json=payload1)
        resp2 = await client.post("/place-bet", json=payload2)

        assert resp1.status_code == 200
        assert resp1.json()["success"] is True

        assert resp2.status_code == 200
        assert resp2.json()["success"] is True


@pytest.mark.asyncio
async def test_bet_dedup_is_case_sensitive():
    """BetId deduplication should be case-sensitive."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload1 = {
            "address": VALID_ADDRESS,
            "amount": "10000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": "MyBetId-001",
        }
        payload2 = {
            "address": VALID_ADDRESS,
            "amount": "10000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": "mybetid-001",  # Different case
        }

        resp1 = await client.post("/place-bet", json=payload1)
        resp2 = await client.post("/place-bet", json=payload2)

        assert resp1.json()["success"] is True
        assert resp2.json()["success"] is True


@pytest.mark.asyncio
async def test_duplicate_after_different_address():
    """Same betId from a different address should still be rejected."""
    app = _create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload1 = {
            "address": VALID_ADDRESS,
            "amount": "10000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": "shared-bet-id",
        }
        payload2 = {
            "address": "3WxRf1bQWfSVDkFh7sQxkBPjZKZDrA3cLZqPbRKEJFNAouXo2FVq",
            "amount": "10000000",
            "choice": 1,
            "commitment": VALID_COMMITMENT,
            "betId": "shared-bet-id",
        }

        resp1 = await client.post("/place-bet", json=payload1)
        resp2 = await client.post("/place-bet", json=payload2)

        assert resp1.json()["success"] is True
        assert resp2.json()["success"] is False
        assert "duplicate" in resp2.json()["message"].lower()
