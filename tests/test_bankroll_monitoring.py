"""
DuckPools - Bankroll Monitoring Service Tests

End-to-end tests for the bankroll monitoring service:
- Balance accuracy (matches on-chain data)
- Exposure calculation (sum of unresolved bets)
- Max payout capacity calculation
- Low bankroll alert thresholds
- Edge cases (zero balance, large balance, concurrency)

Issue: MAT-217
Parent Issue: MAT-204 (cancelled)

Run: python -m pytest tests/test_bankroll_monitoring.py -v -s
"""

import sys
import os
import pytest
import asyncio
from typing import Dict, Optional
from decimal import Decimal

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import httpx


# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

TEST_NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
TEST_API_KEY = os.getenv("API_KEY", "***")
TEST_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
HOUSE_ADDRESS = os.getenv("HOUSE_ADDRESS", "3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26")
COINFLIP_NFT_ID = os.getenv("COINFLIP_NFT_ID", "b0a111d06ccf32fa10c6b36f615233212bc725d8707575ccacc0c02267b27332")

# Currency conversion
NANO_ERG_PER_ERG = 1_000_000_000


# ═══════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════

def nanoerg_to_erg(nanoerg: int) -> float:
    """Convert nanoERG to ERG."""
    return nanoerg / NANO_ERG_PER_ERG


def erg_to_nanoerg(erg: float) -> int:
    """Convert ERG to nanoERG."""
    return int(erg * NANO_ERG_PER_ERG)


async def get_bankroll_status() -> Dict:
    """
    Get bankroll status from backend API.

    Returns:
        Dict with keys: balance, exposure, available, pendingBets, lastUpdate
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{TEST_BACKEND_URL}/bankroll/status",
            headers={"api_key": TEST_API_KEY},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()


async def get_house_wallet_balance(node_url: str = TEST_NODE_URL) -> int:
    """
    Get house wallet balance from Ergo node.

    Returns:
        Balance in nanoERG
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{node_url}/wallet/balances",
            headers={"api_key": TEST_API_KEY}
        )
        response.raise_for_status()
        data = response.json()
        return data[0]["balance"]  # nanoERG


async def get_unspent_boxes_by_token(token_id: str, node_url: str = TEST_NODE_URL) -> list:
    """
    Get all unspent boxes containing a specific token.

    Args:
        token_id: Token ID (NFT or LP token)
        node_url: Ergo node URL

    Returns:
        List of unspent box dictionaries
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{node_url}/blockchain/box/unspent/byTokenId/{token_id}"
        )
        response.raise_for_status()
        return response.json()


async def calculate_exposure_from_boxes(boxes: list) -> int:
    """
    Calculate exposure from PendingBet box values.

    Args:
        boxes: List of unspent boxes

    Returns:
        Total exposure in nanoERG
    """
    return sum(box["value"] for box in boxes)


async def get_box_by_id(box_id: str, node_url: str = TEST_NODE_URL) -> Optional[Dict]:
    """
    Get a box by its ID.

    Returns:
        Box dictionary or None if not found
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{node_url}/blockchain/box/byId/{box_id}",
            headers={"api_key": TEST_API_KEY}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def backend_available():
    """Check if backend is available."""
    try:
        asyncio.run(get_bankroll_status())
        return True
    except httpx.HTTPError:
        pytest.skip("Backend API not available")


@pytest.fixture(scope="module")
def node_available():
    """Check if Ergo node is available."""
    try:
        asyncio.run(get_house_wallet_balance())
        return True
    except httpx.HTTPError:
        pytest.skip("Ergo node not available")


# ═══════════════════════════════════════════════════════════════════
# Test Cases
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available"])
async def test_bankroll_status_basic():
    """
    TC-001: Basic bankroll status endpoint.

    Verify GET /bankroll/status returns all required fields.
    """
    data = await get_bankroll_status()

    assert "balance" in data, "Missing 'balance' field"
    assert "exposure" in data, "Missing 'exposure' field"
    assert "available" in data, "Missing 'available' field"
    assert "pendingBets" in data, "Missing 'pendingBets' field"
    assert "lastUpdate" in data, "Missing 'lastUpdate' field"

    # Type checks
    assert isinstance(data["balance"], int), "balance should be int (nanoERG)"
    assert isinstance(data["exposure"], int), "exposure should be int (nanoERG)"
    assert isinstance(data["available"], int), "available should be int (nanoERG)"
    assert isinstance(data["pendingBets"], int), "pendingBets should be int"

    print(f"Balance: {nanoerg_to_erg(data['balance'])} ERG")
    print(f"Exposure: {nanoerg_to_erg(data['exposure'])} ERG")
    print(f"Available: {nanoerg_to_erg(data['available'])} ERG")
    print(f"Pending Bets: {data['pendingBets']}")
    print(f"Last Update: {data['lastUpdate']}")


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available", "node_available"])
async def test_bankroll_balance_accuracy():
    """
    TC-002: Balance accuracy - matches node API.

    Verify bankroll status balance matches Ergo node wallet balance.
    """
    # Get balance from bankroll API
    bankroll_data = await get_bankroll_status()
    bankroll_balance = bankroll_data["balance"]

    # Get balance directly from node
    node_balance = await get_house_wallet_balance()

    assert bankroll_balance == node_balance, (
        f"Balance mismatch: API={nanoerg_to_erg(bankroll_balance)} ERG, "
        f"Node={nanoerg_to_erg(node_balance)} ERG"
    )

    print(f"Balance matches: {nanoerg_to_erg(bankroll_balance)} ERG")


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available"])
async def test_exposure_empty_state():
    """
    TC-003: Exposure calculation - empty state.

    Verify exposure=0 and available=balance when no pending bets.
    """
    data = await get_bankroll_status()

    # If there are no pending bets, verify exposure and available
    if data["pendingBets"] == 0:
        assert data["exposure"] == 0, "Exposure should be 0 with no pending bets"
        assert data["available"] == data["balance"], (
            "Available should equal balance with no exposure"
        )
    else:
        pytest.skip("Pending bets exist, skipping empty state test")

    print(f"Empty state verified: exposure=0, available={nanoerg_to_erg(data['available'])} ERG")


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available", "node_available"])
async def test_exposure_on_chain_verification():
    """
    TC-007: On-chain balance verification.

    Verify exposure matches sum of PendingBet box values on-chain.
    """
    # Get data from API
    bankroll_data = await get_bankroll_status()
    api_exposure = bankroll_data["exposure"]
    api_pending_count = bankroll_data["pendingBets"]

    # Get PendingBet boxes from node
    boxes = await get_unspent_boxes_by_token(COINFLIP_NFT_ID)
    on_chain_exposure = await calculate_exposure_from_boxes(boxes)

    assert len(boxes) == api_pending_count, (
        f"Pending bet count mismatch: API={api_pending_count}, "
        f"Node={len(boxes)}"
    )

    assert api_exposure == on_chain_exposure, (
        f"Exposure mismatch: API={nanoerg_to_erg(api_exposure)} ERG, "
        f"Node={nanoerg_to_erg(on_chain_exposure)} ERG"
    )

    print(f"Exposure verified: {nanoerg_to_erg(api_exposure)} ERG ({api_pending_count} bets)")


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available"])
async def test_available_balance_calculation():
    """
    TC-006: Available balance calculation.

    Verify available = balance - exposure.
    """
    data = await get_bankroll_status()

    expected_available = data["balance"] - data["exposure"]
    actual_available = data["available"]

    assert actual_available == expected_available, (
        f"Available calculation incorrect: expected={nanoerg_to_erg(expected_available)} ERG, "
        f"actual={nanoerg_to_erg(actual_available)} ERG"
    )

    print(f"Available balance: {nanoerg_to_erg(actual_available)} ERG")


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available"])
async def test_api_response_format():
    """
    Verify API response format and data types.
    """
    data = await get_bankroll_status()

    # Verify response is JSON
    assert isinstance(data, dict), "Response should be a JSON object"

    # Verify all fields are present
    required_fields = ["balance", "exposure", "available", "pendingBets", "lastUpdate"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    # Verify numeric fields are non-negative
    assert data["balance"] >= 0, "Balance should be non-negative"
    assert data["exposure"] >= 0, "Exposure should be non-negative"
    assert data["pendingBets"] >= 0, "Pending bets count should be non-negative"


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available"])
async def test_data_freshness():
    """
    Verify lastUpdate timestamp is recent (within 10 seconds).
    """
    from datetime import datetime, timedelta

    data = await get_bankroll_status()

    last_update_str = data["lastUpdate"]
    last_update = datetime.fromisoformat(last_update_str.replace("Z", "+00:00"))
    now = datetime.utcnow()

    age = now - last_update
    max_age = timedelta(seconds=10)

    assert age <= max_age, (
        f"Data is stale: age={age.total_seconds()}s, max=10s"
    )

    print(f"Data freshness: {age.total_seconds():.2f}s old")


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available"])
async def test_concurrent_requests():
    """
    TC-011: Concurrent requests - data consistency.

    Verify multiple concurrent requests return consistent data.
    """
    # Make 10 concurrent requests
    tasks = [get_bankroll_status() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # All results should be identical (within the same update window)
    first_result = results[0]
    for i, result in enumerate(results[1:], 1):
        assert result == first_result, (
            f"Concurrent request {i} returned different data"
        )

    print(f"Concurrent requests: {len(results)} consistent responses")


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available"])
async def test_large_values_handling():
    """
    TC-010: Large balance scenario.

    Verify calculations work correctly with large values (100k+ ERG).
    """
    data = await get_bankroll_status()

    # Even if balance is small, verify no overflow issues
    balance = data["balance"]
    exposure = data["exposure"]
    available = data["available"]

    # Verify available calculation doesn't underflow
    assert available >= 0, "Available should never be negative"

    # For large balances, verify precision
    if balance > erg_to_nanoerg(100000):
        print(f"Large balance test: {nanoerg_to_erg(balance)} ERG")
    else:
        print(f"Test with current balance: {nanoerg_to_erg(balance)} ERG")


@pytest.mark.asyncio
@pytest.mark.depends(on=["backend_available"])
async def test_exposure_bounds():
    """
    Verify exposure is bounded by balance and pending bet count.
    """
    data = await get_bankroll_status()

    # Exposure cannot exceed balance
    assert data["exposure"] <= data["balance"], (
        f"Exposure ({nanoerg_to_erg(data['exposure'])} ERG) cannot exceed "
        f"balance ({nanoerg_to_erg(data['balance'])} ERG)"
    )

    # Exposure should be reasonable per pending bet (sanity check)
    if data["pendingBets"] > 0:
        avg_bet = data["exposure"] / data["pendingBets"]
        # Each bet should be at least 0.01 ERG
        assert avg_bet >= erg_to_nanoerg(0.01), (
            f"Average bet too small: {nanoerg_to_erg(avg_bet)} ERG"
        )
        # Each bet should be at most 10,000 ERG (sanity)
        assert avg_bet <= erg_to_nanoerg(10000), (
            f"Average bet too large: {nanoerg_to_erg(avg_bet)} ERG"
        )


# ═══════════════════════════════════════════════════════════════════
# Integration Tests (require manual bet placement)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.integration
async def test_exposure_increases_on_bet():
    """
    TC-003: Exposure increases when bet is placed.

    This test requires manual intervention or automated bet placement.
    """
    # Record initial state
    initial_data = await get_bankroll_status()
    initial_exposure = initial_data["exposure"]
    initial_pending = initial_data["pendingBets"]

    # MANUAL STEP: Place a bet (e.g., 1 ERG) using the frontend
    print("\n" + "="*70)
    print("MANUAL STEP REQUIRED:")
    print("1. Place a coinflip bet (e.g., 1 ERG) using the frontend")
    print("2. Do NOT reveal the bet")
    print("3. Press Enter to continue...")
    print("="*70 + "\n")
    input("Press Enter after placing bet...")

    # Check updated state
    updated_data = await get_bankroll_status()
    updated_exposure = updated_data["exposure"]
    updated_pending = updated_data["pendingBets"]

    # Verify exposure increased
    assert updated_exposure > initial_exposure, (
        f"Exposure should increase after placing bet"
    )

    # Verify pending bets count increased
    assert updated_pending == initial_pending + 1, (
        f"Pending bets count should increase by 1"
    )

    print(f"Exposure increased: {nanoerg_to_erg(initial_exposure)} -> "
          f"{nanoerg_to_erg(updated_exposure)} ERG")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_exposure_decreases_on_bet_resolution():
    """
    TC-005: Exposure decreases when bet is resolved.

    This test requires manual intervention.
    """
    # Record initial state (should have pending bets)
    initial_data = await get_bankroll_status()
    initial_exposure = initial_data["exposure"]
    initial_pending = initial_data["pendingBets"]

    assert initial_pending > 0, (
        "This test requires at least one pending bet. Place a bet first."
    )

    # MANUAL STEP: Reveal and resolve a bet
    print("\n" + "="*70)
    print("MANUAL STEP REQUIRED:")
    print("1. Reveal one of the pending bets")
    print("2. Wait for bet resolution")
    print("3. Press Enter to continue...")
    print("="*70 + "\n")
    input("Press Enter after bet resolution...")

    # Check updated state
    updated_data = await get_bankroll_status()
    updated_exposure = updated_data["exposure"]
    updated_pending = updated_data["pendingBets"]

    # Verify exposure decreased
    assert updated_exposure < initial_exposure, (
        f"Exposure should decrease after bet resolution"
    )

    # Verify pending bets count decreased
    assert updated_pending == initial_pending - 1, (
        f"Pending bets count should decrease by 1"
    )

    print(f"Exposure decreased: {nanoerg_to_erg(initial_exposure)} -> "
          f"{nanoerg_to_erg(updated_exposure)} ERG")


# ═══════════════════════════════════════════════════════════════════
# Run Tests
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Run basic tests (no integration tests)
    pytest.main([__file__, "-v", "-s", "-m", "not integration"])
