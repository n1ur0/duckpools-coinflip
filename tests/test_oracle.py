"""
Tests for Oracle Service

MAT-31: Oracle health monitoring and failover
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from pydantic import ValidationError

from backend.oracle_service import (
    OracleConfig,
    OracleService,
    OracleStatus,
    OracleEndpoint,
    OracleHealth,
)


class TestOracleConfig:
    """Tests for OracleConfig validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = OracleConfig()

        assert config.primary_oracle_url == "https://api.oraclepool.xyz"
        assert config.backup_oracle_urls == []
        assert config.stale_threshold_seconds == 300
        assert config.health_check_interval_seconds == 30
        assert config.request_timeout_seconds == 10
        assert config.max_retries == 3
        assert config.enable_failover is True
        assert config.alert_on_stale is True
        assert config.alert_on_failure is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = OracleConfig(
            primary_oracle_url="https://custom.oracle.com",
            backup_oracle_urls=["https://backup1.oracle.com", "https://backup2.oracle.com"],
            stale_threshold_seconds=600,
            health_check_interval_seconds=60,
            enable_failover=False,
        )

        assert config.primary_oracle_url == "https://custom.oracle.com"
        assert len(config.backup_oracle_urls) == 2
        assert config.stale_threshold_seconds == 600
        assert config.health_check_interval_seconds == 60
        assert config.enable_failover is False


class TestOracleService:
    """Tests for OracleService functionality."""

    @pytest.fixture
    def config(self):
        """Create a test oracle configuration."""
        return OracleConfig(
            primary_oracle_url="https://primary.oracle.com",
            backup_oracle_urls=["https://backup1.oracle.com", "https://backup2.oracle.com"],
            stale_threshold_seconds=300,
            health_check_interval_seconds=30,
        )

    @pytest.fixture
    async def oracle_service(self, config):
        """Create an oracle service instance."""
        service = OracleService(config=config)
        # Mock the httpx client to avoid actual network calls
        with patch.object(service, "_client", AsyncMock()):
            yield service
        # Cleanup
        if service._health_check_task:
            service._health_check_task.cancel()

    def test_service_initialization(self, config):
        """Test service initializes with correct configuration."""
        service = OracleService(config=config)

        assert len(service.all_endpoints) == 3
        assert service.all_endpoints[0].name == "primary"
        assert service.all_endpoints[0].is_primary is True
        assert service.all_endpoints[0].priority == 1
        assert service.all_endpoints[1].name == "backup-2"
        assert service.all_endpoints[1].priority == 2
        assert service.current_endpoint.name == "primary"

    @pytest.mark.asyncio
    async def test_service_start_and_stop(self, config):
        """Test starting and stopping the service."""
        service = OracleService(config=config)

        # Mock the httpx AsyncClient
        with patch("backend.oracle_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            await service.start()
            assert service._client is not None
            assert service._health_check_task is not None
            mock_client_class.assert_called_once_with(timeout=config.request_timeout_seconds)

            await service.stop()
            mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_oracle_data_success(self, oracle_service):
        """Test successful oracle data fetch."""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": "1.23"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        oracle_service._client = mock_client

        data = await oracle_service.get_oracle_data(oracle_box_id="test-box-id")

        assert data == {"price": "1.23"}
        assert oracle_service._last_feed_update is not None

    @pytest.mark.asyncio
    async def test_get_oracle_data_failover(self, oracle_service):
        """Test automatic failover when primary fails."""
        # Mock primary failure, backup success
        mock_response_primary = AsyncMock()
        mock_response_primary.status_code = 500
        mock_response_primary.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=mock_response_primary
        )

        mock_response_backup = AsyncMock()
        mock_response_backup.status_code = 200
        mock_response_backup.json.return_value = {"price": "1.23"}

        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            mock_response_primary,
            mock_response_backup,
        ]
        oracle_service._client = mock_client

        data = await oracle_service.get_oracle_data(oracle_box_id="test-box-id")

        assert data == {"price": "1.23"}
        assert oracle_service.current_endpoint.name != "primary"

    @pytest.mark.asyncio
    async def test_get_oracle_data_all_fail(self, oracle_service):
        """Test handling when all endpoints fail."""
        # Mock all endpoints failing
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        oracle_service._client = mock_client

        data = await oracle_service.get_oracle_data(oracle_box_id="test-box-id")

        assert data is None

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, oracle_service):
        """Test endpoint health check."""
        # Mock successful health check
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        oracle_service._client = mock_client

        endpoint = oracle_service.all_endpoints[0]
        await oracle_service._check_endpoint(endpoint)

        health = oracle_service._health_status.get(endpoint.url)
        assert health is not None
        assert health.status == OracleStatus.HEALTHY
        assert health.latency_ms is not None

    @pytest.mark.asyncio
    async def test_health_check_endpoint_failure(self, oracle_service):
        """Test endpoint health check on failure."""
        # Mock failed health check
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        oracle_service._client = mock_client

        endpoint = oracle_service.all_endpoints[0]
        await oracle_service._check_endpoint(endpoint)

        health = oracle_service._health_status.get(endpoint.url)
        assert health is not None
        assert health.status == OracleStatus.UNREACHABLE
        assert health.latency_ms is None
        assert health.error is not None

    @pytest.mark.asyncio
    async def test_stale_feed_detection(self, oracle_service, config):
        """Test stale feed detection."""
        # Set last feed update to before threshold
        oracle_service._last_feed_update = datetime.now(timezone.utc) - timedelta(
            seconds=config.stale_threshold_seconds + 10
        )

        await oracle_service._check_all_endpoints()

        health = oracle_service._health_status.get(oracle_service.current_endpoint.url)
        assert health is not None
        assert health.status == OracleStatus.STALE

    def test_get_health_status(self, oracle_service):
        """Test getting health status for all endpoints."""
        # Mock health data
        endpoint = oracle_service.all_endpoints[0]
        oracle_service._health_status[endpoint.url] = OracleHealth(
            url=endpoint.url,
            status=OracleStatus.HEALTHY,
            last_updated=datetime.now(timezone.utc),
            latency_ms=123.45,
            error=None,
        )

        status = oracle_service.get_health_status()

        assert "primary" in status
        assert status["primary"]["status"] == "healthy"
        assert status["primary"]["latency_ms"] == 123.45
        assert status["primary"]["is_primary"] is True

    def test_get_service_status_ok(self, oracle_service):
        """Test getting overall service status when healthy."""
        # Mock healthy status
        endpoint = oracle_service.current_endpoint
        oracle_service._health_status[endpoint.url] = OracleHealth(
            url=endpoint.url,
            status=OracleStatus.HEALTHY,
            last_updated=datetime.now(timezone.utc),
            latency_ms=100.0,
            error=None,
        )

        status = oracle_service.get_service_status()

        assert status["status"] == "ok"
        assert status["current_endpoint"] == "primary"
        assert status["total_endpoints"] == 3

    def test_get_service_status_stale(self, oracle_service):
        """Test getting overall service status when stale."""
        # Mock stale status
        endpoint = oracle_service.current_endpoint
        oracle_service._health_status[endpoint.url] = OracleHealth(
            url=endpoint.url,
            status=OracleStatus.STALE,
            last_updated=datetime.now(timezone.utc),
            latency_ms=100.0,
            error=None,
        )

        status = oracle_service.get_service_status()

        assert status["status"] == "stale"
        assert status["current_endpoint"] == "primary"

    def test_get_service_status_degraded(self, oracle_service):
        """Test getting overall service status when degraded."""
        # Mock degraded status
        endpoint = oracle_service.current_endpoint
        oracle_service._health_status[endpoint.url] = OracleHealth(
            url=endpoint.url,
            status=OracleStatus.UNREACHABLE,
            last_updated=datetime.now(timezone.utc),
            latency_ms=None,
            error="Connection failed",
        )

        status = oracle_service.get_service_status()

        assert status["status"] == "degraded"
        assert status["current_endpoint"] == "primary"


class TestOracleRoutes:
    """Tests for oracle API routes."""

    @pytest.mark.asyncio
    async def test_get_oracle_health(self):
        """Test GET /api/oracle/health endpoint."""
        from backend.oracle_routes import router, get_oracle_service

        # Mock oracle service
        mock_service = MagicMock()
        mock_service.get_health_status.return_value = {
            "primary": {"status": "healthy", "latency_ms": 100.0}
        }

        # Create mock request with app state
        mock_request = MagicMock()
        mock_request.app.state.oracle_service = mock_service

        # Call endpoint
        result = await router.routes[0].endpoint(oracle_service=mock_service)
        assert result["primary"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_oracle_status(self):
        """Test GET /api/oracle/status endpoint."""
        from backend.oracle_routes import router

        # Mock oracle service
        mock_service = MagicMock()
        mock_service.get_service_status.return_value = {
            "status": "ok",
            "current_endpoint": "primary",
            "total_endpoints": 1,
        }

        # Find the status endpoint
        for route in router.routes:
            if hasattr(route, "path") and route.path.endswith("/status"):
                result = await route.endpoint(oracle_service=mock_service)
                assert result["status"] == "ok"
                break
