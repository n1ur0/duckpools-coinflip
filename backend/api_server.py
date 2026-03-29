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
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
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


# ─── Rate Limiting (MAT-195) ──────────────────────────────────────

from rate_limits import limiter


# ─── Security Headers Middleware ────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject standard security headers on all responses.

    Headers applied:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: restrictive settings
    - Content-Security-Policy: default restrictive policy
    - Strict-Transport-Security: HSTS (production only)
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Apply security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # Content Security Policy - prevent XSS and data injection
        # NOTE: unsafe-inline/unsafe-eval needed for Vite dev server (HMR).
        #       For production, use nonces instead.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'"
        )

        # Strict Transport Security - max-age=0 for development
        response.headers["Strict-Transport-Security"] = "max-age=0; includeSubDomains"

        return response


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

# Rate limiting — state + exception handler (MAT-195)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — Explicit allowlist for methods and headers.
CORS_ALLOW_METHODS = os.getenv(
    "CORS_ALLOW_METHODS",
    "GET,POST,OPTIONS",
)
CORS_ALLOW_HEADERS = os.getenv(
    "CORS_ALLOW_HEADERS",
    "Content-Type,Authorization,X-Api-Key,Accept,Origin",
)
cors_origins = [o.strip() for o in CORS_ORIGINS_STR.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=[m.strip() for m in CORS_ALLOW_METHODS.split(",") if m.strip()],
    allow_headers=[h.strip() for h in CORS_ALLOW_HEADERS.split(",") if h.strip()],
)

# Security headers — registered after CORS so headers are always applied
app.add_middleware(SecurityHeadersMiddleware)

# Request/response logging (MAT-228)
app.add_middleware(RequestLoggingMiddleware)

# Register routers — coinflip only
app.include_router(ws_router)
app.include_router(game_router)


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
        "version": "0.2.0",
        "endpoints": {
            "place_bet": "POST /place-bet",
            "leaderboard": "/leaderboard",
            "history": "/history/{address}",
            "player_stats": "/player/stats/{address}",
            "player_comp": "/player/comp/{address}",
            "health": "/health",
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
