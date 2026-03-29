"""
DuckPools Off-Chain Bot - Health Server

Lightweight HTTP health endpoint for backend monitoring.

MAT-224: Add bot heartbeat/health endpoint for backend monitoring
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from aiohttp import web
import aiohttp_cors

from logger import get_logger

logger = get_logger(__name__)


class HealthServer:
    """HTTP health endpoint for bot monitoring."""

    def __init__(self, port: int = 8001):
        self.port = port
        self.app = web.Application()
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._start_time = time.time()
        self._bets_processed = 0
        self._last_processed_at: Optional[datetime] = None
        
        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.add_routes([
            web.get('/health', self.health_handler),
        ])

        # Enable CORS for health endpoint with explicit origin allowlist.
        # SEC-MEDIUM-4: Wildcard ("*") + allow_credentials=True is a
        # misconfiguration per OWASP. Read origins from env var, same
        # pattern as backend/api_server.py CORS_ORIGINS_STR.
        cors_allowed_origins_str = os.getenv(
            "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
        )
        cors_origins = [o.strip() for o in cors_allowed_origins_str.split(",") if o.strip()]

        cors_config = {
            origin: aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
            for origin in cors_origins
        }
        cors = aiohttp_cors.setup(self.app, defaults=cors_config)
        
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def start(self):
        """Start the health server."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        
        self._site = web.TCPSite(self._runner, '0.0.0.0', self.port)
        await self._site.start()
        
        logger.info(
            "health_server_started",
            port=self.port
        )

    async def stop(self):
        """Stop the health server."""
        if self._site:
            await self._site.stop()
            self._site = None
            
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            
        logger.info("health_server_stopped")

    def increment_bets_processed(self):
        """Increment the bets processed counter and update timestamp."""
        self._bets_processed += 1
        self._last_processed_at = datetime.now(timezone.utc)

    async def health_handler(self, request: web.Request) -> web.Response:
        """Handle GET /health requests."""
        uptime_seconds = int(time.time() - self._start_time)
        
        health_data: Dict[str, Any] = {
            "status": "alive",
            "uptime_seconds": uptime_seconds,
            "bets_processed": self._bets_processed,
        }
        
        if self._last_processed_at:
            health_data["last_processed_at"] = self._last_processed_at.isoformat()
        
        return web.json_response(health_data)