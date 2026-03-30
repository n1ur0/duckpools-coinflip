"""
DuckPools CoinFlip - Main API Server

FastAPI application serving the coinflip game endpoints and
real-time WebSocket bet updates.

PoC scope: ONE game (coinflip). No LP, bankroll, oracle, or other games.
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from ws_manager import ConnectionManager
from ws_routes import router as ws_router
from game_routes import router as game_router
from bankroll_routes import router as bankroll_router

# Import and initialize rate limited client for external API calls
# Define logger early for rate_limited_client init
logger = logging.getLogger(__name__)

from rate_limited_client import rate_limited_client, make_rate_limited_request

# Initialize rate limited client with configured providers
try:
    # The client is already initialized in rate_limited_client.py
    logger.info("Rate limited client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize rate limited client: {str(e)}")
    logger.warning("Rate limited client not available. External API calls may be rate limited.")

# ─── Logging Setup ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("duckpools")


# ─── Environment ────────────────────────────────────────────────────

NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")
HOUSE_EDGE_BPS = int(os.getenv("HOUSE_EDGE_BPS", "300"))
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS_STR", "http://localhost:3000")

# ─── BE-8: NODE_API_KEY is required — fail-fast if missing.
if not NODE_API_KEY:
    print("FATAL: NODE_API_KEY environment variable is required.", file=sys.stderr)
    sys.exit(1)


# ─── Security Headers Middleware ────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject standard security headers on all responses.

    Headers applied:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: restrictive settings
    - Content-Security-Policy: comprehensive policy
    - Strict-Transport-Security: HSTS (production only)
    - Feature-Policy: restrict powerful features
    - X-Download-Options: noopen
    - X-Permitted-Cross-Domain-Policies: none
    - Cache-Control: no-store (sensitive data)
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Apply security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), midi=(), sync-xhr=()"
        )
        response.headers["X-Download-Options"] = "noopen"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        # Content Security Policy - prevent XSS and data injection
        # NOTE: unsafe-inline needed for Vite dev server (HMR).
        #       For production:
        #       1. Remove `unsafe-eval` 
        #       2. Use nonces instead of `unsafe-inline` for scripts
        #       3. Update `connect-src` to include WebSocket and API origins
        #       4. Remove debug headers

        # Production CSP Hardening Requirements:
        # - Remove `unsafe-eval` entirely
        # - Replace `unsafe-inline` with nonce-based CSP for scripts
        # - Update `connect-src` to include production WebSocket and API origins
        # - Consider adding `script-src-elem` and `script-src-attr` with appropriate policies
        # - Add `frame-ancestors` to allow trusted domains if needed
        # - Set appropriate `max-age` for HSTS (e.g., 31536000 for 1 year)
        # 
        # See: docs/SECURITY.md for complete production hardening guidelines
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' ws://localhost:8000 http://localhost:3000 http://localhost:3001; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "font-src 'self'; "
            "media-src 'self'; "
            "manifest-src 'self'"
        )

        # Strict Transport Security - max-age=0 for development, longer for production
        # In production, this should be set to a longer duration (e.g., 31536000 for 1 year)
        response.headers["Strict-Transport-Security"] = "max-age=0; includeSubDomains"

        return response


# ─── Request Body Size Limiter (MAT-396/5.1) ──────────────────────

MAX_REQUEST_BODY_SIZE = 1_000_000  # 1 MB max request body

class RequestBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests with oversized bodies to prevent DoS via large payloads."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > MAX_REQUEST_BODY_SIZE:
                    from starlette.responses import JSONResponse as _JR
                    return _JR(
                        status_code=413,
                        content={"error": {"code": 413, "message": "Request body too large", "path": str(request.url.path)}},
                    )
            except (ValueError, TypeError):
                pass
        return await call_next(request)


# ─── Request/Response Logging Middleware (MAT-228) ──────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests with method, path, status, and duration."""

    # Paths to skip logging (health checks, etc.)
    SKIP_PATHS = {"/health", "/"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "%s %s -> 500 (%.1fms) error=%s",
                method, path, duration_ms, exc,
            )
            raise

        if path not in self.SKIP_PATHS:
            logger.info(
                "%s %s -> %d (%.1fms)",
                method, path, response.status_code, duration_ms,
            )

        return response


# ─── Global Error Handlers (MAT-227) ──────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize WebSocket manager on startup."""
    app.state.ws_manager = ConnectionManager()
    yield
    app.state.ws_manager = None


# ─── App ────────────────────────────────────────────────────────────

app = FastAPI(
    title="DuckPools CoinFlip API",
    description="DuckPools CoinFlip PoC API",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — Explicit allowlist for methods and headers.
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS_STR", "http://localhost:3000")
cors_origins = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

CORS_ALLOW_METHODS = os.getenv(
    "CORS_ALLOW_METHODS",
    "GET,POST,OPTIONS",
)
CORS_ALLOW_HEADERS = os.getenv(
    "CORS_ALLOW_HEADERS",
    "Content-Type,Authorization,X-Api-Key,Accept,Origin",
)

# CORS middleware (MAT-228)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=[m.strip() for m in CORS_ALLOW_METHODS.split(",") if m.strip()],
    allow_headers=[h.strip() for h in CORS_ALLOW_HEADERS.split(",") if h.strip()],
)
# Security headers — registered after CORS so headers are always applied
app.add_middleware(SecurityHeadersMiddleware)

# Request body size limiter — reject oversized payloads early
app.add_middleware(RequestBodySizeMiddleware)

# Request/response logging (MAT-228)
app.add_middleware(RequestLoggingMiddleware)

# Register routers — coinflip only
app.include_router(ws_router)
app.include_router(game_router)
app.include_router(bankroll_router)  # MAT-231: Bankroll P&L tracking


# ─── Global Error Handlers (MAT-227) ─────────────────────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return structured JSON for all HTTP exceptions (4xx, 5xx)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "path": str(request.url.path),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled errors — return 500 with structured JSON."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "path": str(request.url.path),
            }
        },
    )


# ─── Root Endpoints ─────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "DuckPools CoinFlip API",
        "version": "0.3.0",
        "endpoints": {
            "place_bet": "POST /place-bet",
            "expired_bets": "GET /bets/expired",
            "bet_timeout": "GET /bets/{bet_id}/timeout",
            "build_refund_tx": "POST /bets/{bet_id}/build-refund-tx",
            "record_refund": "POST /bets/{bet_id}/refund-record",
            "pending_with_timeout": "GET /bets/pending-with-timeout",
            "build_reveal_tx": "POST /bot/build-reveal-tx",
            "reveal_and_pay": "POST /bot/reveal-and-pay",
            "ws_notify": "POST /ws/notify",
            "contract_info": "GET /contract-info",
            "pool_state": "GET /pool/state",
            "bankroll_status": "GET /bankroll/status",
            "bankroll_history": "GET /bankroll/history",
            "bankroll_metrics": "GET /bankroll/metrics",
            "bankroll_pnl_summary": "GET /bankroll/pnl/summary",
            "bankroll_pnl_rounds": "GET /bankroll/pnl/rounds",
            "bankroll_pnl_period": "GET /bankroll/pnl/period",
            "bankroll_pnl_player": "GET /bankroll/pnl/player/{address}",
            "leaderboard": "GET /leaderboard",
            "history": "GET /history/{address}",
            "player_stats": "GET /player/stats/{address}",
            "player_comp": "GET /player/comp/{address}",
            "health": "GET /health",
        },
    }


@app.get("/health")
async def health():
    """Health check: verify node connectivity."""
    import httpx

    health_data = {"status": "ok", "node": NODE_URL}

    # Check node connectivity
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{NODE_URL}/info", headers={"api_key": NODE_API_KEY})
            resp.raise_for_status()
            info = resp.json()
            health_data["node_height"] = info.get("fullHeight")
    except Exception as e:
        health_data["status"] = "degraded"
        health_data["node_error"] = str(e)

    return health_data


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
