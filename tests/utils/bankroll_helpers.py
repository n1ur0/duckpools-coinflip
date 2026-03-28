"""
Bankroll Monitoring Test Utilities

Helper functions for testing the bankroll monitoring service.
"""

import asyncio
import httpx
from typing import Dict, List, Optional
from decimal import Decimal


# Currency constants
NANO_ERG_PER_ERG = 1_000_000_000


def nanoerg_to_erg(nanoerg: int) -> float:
    """Convert nanoERG to ERG."""
    return nanoerg / NANO_ERG_PER_ERG


def erg_to_nanoerg(erg: float) -> int:
    """Convert ERG to nanoERG."""
    return int(erg * NANO_ERG_PER_ERG)


async def fetch_bankroll_status(
    backend_url: str,
    api_key: str
) -> Dict:
    """
    Fetch bankroll status from backend API.

    Args:
        backend_url: Backend API URL
        api_key: API authentication key

    Returns:
        Dictionary with bankroll metrics

    Raises:
        httpx.HTTPError: If request fails
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{backend_url}/bankroll/status",
            headers={"api_key": api_key},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()


async def fetch_house_wallet_balance(
    node_url: str,
    wallet_address: Optional[str] = None,
    api_key: str = "***"
) -> int:
    """
    Fetch house wallet balance from Ergo node.

    Args:
        node_url: Ergo node URL
        wallet_address: House wallet address (optional, if not provided uses default)
        api_key: API key for node authentication

    Returns:
        Balance in nanoERG

    Raises:
        httpx.HTTPError: If request fails
    """
    async with httpx.AsyncClient() as client:
        # If address provided, use UTXO by address endpoint
        # Otherwise use wallet balances endpoint
        if wallet_address:
            response = await client.get(
                f"{node_url}/utxo/byAddress/{wallet_address}",
                headers={"api_key": api_key}
            )
            response.raise_for_status()
            boxes = response.json()
            return sum(box["value"] for box in boxes)
        else:
            response = await client.get(
                f"{node_url}/wallet/balances",
                headers={"api_key": api_key}
            )
            response.raise_for_status()
            data = response.json()
            return data[0]["balance"]


async def fetch_unspent_boxes_by_token(
    node_url: str,
    token_id: str,
    api_key: str = "***"
) -> List[Dict]:
    """
    Fetch all unspent boxes containing a specific token.

    Args:
        node_url: Ergo node URL
        token_id: Token ID (NFT or LP token)
        api_key: API key for node authentication

    Returns:
        List of unspent box dictionaries

    Raises:
        httpx.HTTPError: If request fails
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{node_url}/blockchain/box/unspent/byTokenId/{token_id}"
        )
        response.raise_for_status()
        return response.json()


async def fetch_box_by_id(
    box_id: str,
    node_url: str,
    api_key: str = "***"
) -> Optional[Dict]:
    """
    Fetch a box by its ID.

    Args:
        box_id: Box ID (base64 or hex string)
        node_url: Ergo node URL
        api_key: API key for node authentication

    Returns:
        Box dictionary or None if not found

    Raises:
        httpx.HTTPError: If request fails (except 404)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{node_url}/blockchain/box/byId/{box_id}",
            headers={"api_key": api_key}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def calculate_exposure_from_boxes(boxes: List[Dict]) -> int:
    """
    Calculate total exposure from PendingBet box values.

    Args:
        boxes: List of box dictionaries

    Returns:
        Total exposure in nanoERG
    """
    return sum(box["value"] for box in boxes)


def calculate_available_balance(balance: int, exposure: int) -> int:
    """
    Calculate available balance.

    Args:
        balance: Total balance in nanoERG
        exposure: Total exposure in nanoERG

    Returns:
        Available balance in nanoERG
    """
    return balance - exposure


async def verify_balance_accuracy(
    backend_url: str,
    node_url: str,
    api_key: str
) -> tuple[bool, str]:
    """
    Verify that backend balance matches node balance.

    Args:
        backend_url: Backend API URL
        node_url: Ergo node URL
        api_key: API key

    Returns:
        Tuple of (is_accurate, message)
    """
    try:
        bankroll_data = await fetch_bankroll_status(backend_url, api_key)
        node_balance = await fetch_house_wallet_balance(node_url, api_key=api_key)

        backend_balance = bankroll_data["balance"]

        if backend_balance == node_balance:
            return True, (
                f"Balance accurate: {nanoerg_to_erg(backend_balance)} ERG"
            )
        else:
            diff = abs(backend_balance - node_balance)
            return False, (
                f"Balance mismatch: Backend={nanoerg_to_erg(backend_balance)} ERG, "
                f"Node={nanoerg_to_erg(node_balance)} ERG, "
                f"Diff={nanoerg_to_erg(diff)} ERG"
            )
    except Exception as e:
        return False, f"Balance verification failed: {str(e)}"


async def verify_exposure_accuracy(
    backend_url: str,
    node_url: str,
    token_id: str,
    api_key: str
) -> tuple[bool, str]:
    """
    Verify that backend exposure matches on-chain exposure.

    Args:
        backend_url: Backend API URL
        node_url: Ergo node URL
        token_id: Coinflip NFT ID
        api_key: API key

    Returns:
        Tuple of (is_accurate, message)
    """
    try:
        bankroll_data = await fetch_bankroll_status(backend_url, api_key)
        boxes = await fetch_unspent_boxes_by_token(node_url, token_id, api_key)
        on_chain_exposure = calculate_exposure_from_boxes(boxes)

        backend_exposure = bankroll_data["exposure"]
        backend_pending = bankroll_data["pendingBets"]

        if backend_exposure == on_chain_exposure:
            if len(boxes) == backend_pending:
                return True, (
                    f"Exposure accurate: {nanoerg_to_erg(backend_exposure)} ERG "
                    f"({backend_pending} bets)"
                )
            else:
                return False, (
                    f"Exposure matches but count mismatch: "
                    f"Backend pending={backend_pending}, "
                    f"Node boxes={len(boxes)}"
                )
        else:
            diff = abs(backend_exposure - on_chain_exposure)
            return False, (
                f"Exposure mismatch: Backend={nanoerg_to_erg(backend_exposure)} ERG, "
                f"Node={nanoerg_to_erg(on_chain_exposure)} ERG, "
                f"Diff={nanoerg_to_erg(diff)} ERG"
            )
    except Exception as e:
        return False, f"Exposure verification failed: {str(e)}"


async def get_bankroll_alerts(
    backend_url: str,
    api_key: str
) -> List[Dict]:
    """
    Get current bankroll alerts.

    Args:
        backend_url: Backend API URL
        api_key: API key

    Returns:
        List of active alerts

    Raises:
        httpx.HTTPError: If request fails
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{backend_url}/bankroll/alerts",
            headers={"api_key": api_key},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()


async def stress_test_bankroll_endpoint(
    backend_url: str,
    api_key: str,
    num_requests: int = 100
) -> Dict:
    """
    Stress test the bankroll status endpoint with concurrent requests.

    Args:
        backend_url: Backend API URL
        api_key: API key
        num_requests: Number of concurrent requests

    Returns:
        Dictionary with test results:
            - success_count: Number of successful requests
            - failure_count: Number of failed requests
            - avg_response_time: Average response time in ms
            - max_response_time: Max response time in ms
            - min_response_time: Min response time in ms
    """
    import time

    async def make_request():
        start = time.time()
        try:
            await fetch_bankroll_status(backend_url, api_key)
            return True, (time.time() - start) * 1000
        except Exception:
            return False, (time.time() - start) * 1000

    tasks = [make_request() for _ in range(num_requests)]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for success, _ in results if success)
    failure_count = num_requests - success_count

    response_times = [rt for _, rt in results if rt is not None]
    avg_response_time = sum(response_times) / len(response_times)
    max_response_time = max(response_times)
    min_response_time = min(response_times)

    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "avg_response_time": avg_response_time,
        "max_response_time": max_response_time,
        "min_response_time": min_response_time
    }


def format_erg_amount(nanoerg: int, decimals: int = 2) -> str:
    """
    Format nanoERG amount as a human-readable ERG string.

    Args:
        nanoerg: Amount in nanoERG
        decimals: Number of decimal places

    Returns:
        Formatted string (e.g., "1.23 ERG")
    """
    erg = nanoerg / NANO_ERG_PER_ERG
    return f"{erg:.{decimals}f} ERG"


def validate_bankroll_data(data: Dict) -> tuple[bool, str]:
    """
    Validate bankroll status data structure and values.

    Args:
        data: Bankroll status dictionary

    Returns:
        Tuple of (is_valid, message)
    """
    required_fields = ["balance", "exposure", "available", "pendingBets", "lastUpdate"]

    # Check all required fields present
    missing_fields = [f for f in required_fields if f not in data]
    if missing_fields:
        return False, f"Missing fields: {', '.join(missing_fields)}"

    # Check types
    if not isinstance(data["balance"], int):
        return False, "balance must be int"
    if not isinstance(data["exposure"], int):
        return False, "exposure must be int"
    if not isinstance(data["available"], int):
        return False, "available must be int"
    if not isinstance(data["pendingBets"], int):
        return False, "pendingBets must be int"

    # Check non-negative
    if data["balance"] < 0:
        return False, "balance must be non-negative"
    if data["exposure"] < 0:
        return False, "exposure must be non-negative"
    if data["available"] < 0:
        return False, "available must be non-negative"
    if data["pendingBets"] < 0:
        return False, "pendingBets must be non-negative"

    # Check calculations
    expected_available = data["balance"] - data["exposure"]
    if data["available"] != expected_available:
        return False, (
            f"available calculation incorrect: "
            f"expected={expected_available}, actual={data['available']}"
        )

    # Check bounds
    if data["exposure"] > data["balance"]:
        return False, "exposure cannot exceed balance"

    return True, "Bankroll data is valid"
