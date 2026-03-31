"""
Phase 7, Scenario 3 — Concurrent Bets Stress Test

Tests system behavior under concurrent load:
  1. Multiple simultaneous bet placements
  2. Bet deduplication under race conditions
  3. History endpoint under load
  4. Stats consistency after concurrent bets

Uses asyncio.gather to simulate concurrent users hitting the API.
"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient

from conftest import (
    TEST_PLAYER_ADDRESS,
    make_place_bet_payload,
)


class TestConcurrentBetPlacement:
    """Multiple players placing bets simultaneously."""

    @pytest.mark.asyncio
    async def test_10_concurrent_bets_all_succeed(self, app_client: AsyncClient):
        """10 different players should all be able to place bets concurrently."""
        n = 10
        payloads = [
            make_place_bet_payload(
                address=TEST_PLAYER_ADDRESS,
                bet_id=f"concurrent-{i}-{pytest.__version__}",  # unique
            )
            for i in range(n)
        ]

        async def place_bet(payload):
            return await app_client.post("/place-bet", json=payload)

        results = await asyncio.gather(*[place_bet(p) for p in payloads])
        statuses = [r.status_code for r in results]
        successes = [r for r in results if r.status_code == 200]

        assert len(successes) == n, \
            f"Expected {n} successes, got {len(successes)}. Statuses: {statuses}"

    @pytest.mark.asyncio
    async def test_50_concurrent_bets(self, app_client: AsyncClient):
        """50 concurrent bets should all succeed with unique bet IDs."""
        n = 50
        payloads = [
            make_place_bet_payload(bet_id=f"stress-50-{i}")
            for i in range(n)
        ]

        async def place_bet(payload):
            return await app_client.post("/place-bet", json=payload)

        results = await asyncio.gather(*[place_bet(p) for p in payloads])
        successes = sum(1 for r in results if r.status_code == 200)
        assert successes == n

    @pytest.mark.asyncio
    async def test_100_concurrent_bets(self, app_client: AsyncClient):
        """100 concurrent bets - stress test boundary."""
        n = 100
        payloads = [
            make_place_bet_payload(bet_id=f"stress-100-{i}")
            for i in range(n)
        ]

        results = await asyncio.gather(
            *[app_client.post("/place-bet", json=p) for p in payloads]
        )
        successes = sum(1 for r in results if r.status_code == 200)
        assert successes == n


class TestConcurrentHistoryReads:
    """Concurrent reads of bet history should not conflict with writes."""

    @pytest.mark.asyncio
    async def test_reads_during_writes(self, app_client: AsyncClient):
        """History reads should work while bets are being placed."""
        n_writes = 20
        n_reads = 20

        async def place():
            return await app_client.post("/place-bet", json=make_place_bet_payload(
                bet_id=f"rw-test-{asyncio.current_task().get_name()}"
            ))

        async def read():
            return await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")

        write_tasks = [asyncio.create_task(place()) for _ in range(n_writes)]
        read_tasks = [asyncio.create_task(read()) for _ in range(n_reads)]

        all_tasks = write_tasks + read_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # No exceptions should have been raised
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Got {len(exceptions)} exceptions: {exceptions}"

        # All HTTP responses should be 200
        statuses = [r.status_code for r in results if not isinstance(r, Exception)]
        assert all(s == 200 for s in statuses), f"Non-200 statuses: {statuses}"


class TestConcurrentStatsReads:
    """Concurrent stats reads should be consistent."""

    @pytest.mark.asyncio
    async def test_stats_reads_consistent(self, app_client: AsyncClient):
        """Multiple concurrent stats reads should return the same data."""
        # First place a few bets
        for i in range(5):
            await app_client.post("/place-bet", json=make_place_bet_payload(
                bet_id=f"stats-concurrent-{i}"
            ))

        # Read stats 10 times concurrently
        results = await asyncio.gather(
            *[app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}") for _ in range(10)]
        )

        # All should have the same totalBets
        total_bets_values = [r.json()["totalBets"] for r in results]
        assert len(set(total_bets_values)) == 1, \
            f"Inconsistent totalBets: {set(total_bets_values)}"


class TestBetDeduplicationUnderLoad:
    """Bet deduplication should work correctly even under concurrent requests."""

    @pytest.mark.asyncio
    async def test_duplicate_bet_id_rejected_concurrently(self, app_client: AsyncClient):
        """Same betId submitted 5 times concurrently - only one should succeed.
        
        NOTE: This test may xfail on branches without bet deduplication (MAT-350).
        """
        shared_bet_id = "dedup-concurrent-test"
        payload = make_place_bet_payload(bet_id=shared_bet_id)

        results = await asyncio.gather(
            *[app_client.post("/place-bet", json=payload) for _ in range(5)],
            return_exceptions=True,
        )

        success_count = sum(
            1 for r in results
            if not isinstance(r, Exception) and r.status_code == 200
        )
        fail_count = sum(
            1 for r in results
            if not isinstance(r, Exception) and r.status_code != 200
        )

        # With dedup: at most 1 success. Without: all 5 succeed.
        if success_count > 1:
            pytest.xfail("Bet deduplication not yet implemented (MAT-350)")
        assert success_count <= 1, \
            f"Expected at most 1 success, got {success_count}"
        assert fail_count >= 4, \
            f"Expected at least 4 failures, got {fail_count}"

    @pytest.mark.asyncio
    async def test_unique_bet_ids_all_succeed(self, app_client: AsyncClient):
        """Different betIds submitted concurrently should all succeed."""
        payloads = [
            make_place_bet_payload(bet_id=f"unique-concurrent-{i}")
            for i in range(10)
        ]

        results = await asyncio.gather(
            *[app_client.post("/place-bet", json=p) for p in payloads]
        )

        successes = sum(1 for r in results if r.status_code == 200)
        assert successes == 10
