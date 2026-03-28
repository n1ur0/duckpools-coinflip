"""
Pytest configuration and fixtures for DuckPools tests.
"""

import os
import pytest


# Test environment configuration
TEST_NODE_URL = os.getenv("TEST_NODE_URL", "http://localhost:9052")
TEST_API_KEY = os.getenv("TEST_API_KEY", "hello")
HOUSE_ADDRESS = os.getenv("HOUSE_ADDRESS", "3WyrB3D5AMpyEc88UJ7FdsBMXAZKwzQzkKeDbAQVfXytDPgxF26")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def node_url():
    """Test Ergo node URL."""
    return TEST_NODE_URL


@pytest.fixture(scope="session")
def api_key():
    """Test API key."""
    return TEST_API_KEY


@pytest.fixture(scope="session")
def house_address():
    """House wallet address."""
    return HOUSE_ADDRESS


@pytest.fixture(scope="session")
def backend_url():
    """Backend API URL."""
    return BACKEND_URL


@pytest.fixture(scope="session")
def frontend_url():
    """Frontend URL."""
    return FRONTEND_URL


# Async fixtures
@pytest.fixture
async def http_client():
    """Async HTTP client for API tests."""
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        yield client
