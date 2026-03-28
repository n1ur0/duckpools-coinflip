"""
DuckPools - Main API Server

FastAPI application serving both the coinflip game endpoints and the
LP liquidity pool endpoints, plus real-time WebSocket bet updates.

MAT-15: Tokenized bankroll and liquidity pool
MAT-30: Real-time game history with WebSocket updates
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add backend directory to Python path so pool_manager imports work
sys.path.insert(0, str(Path(__file__).parent))

from pool_manager import PoolConfig, PoolStateManager
from lp_routes import router as lp_router
from ws_manager import ConnectionManager
from ws_routes import router as ws_router
from oracle_service import OracleService, OracleConfig
from oracle_routes import router as oracle_router


# ─── Environment ────────────────────────────────────────────────────

NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
API_KEY = os.getenv("API_KEY", "hello")
POOL_NFT_ID = os.getenv("POOL_NFT_ID", "")
LP_TOKEN_ID = os.getenv("LP_TOKEN_ID", "")
HOUSE_ADDRESS = os.getenv("HOUSE_ADDRESS", "")
BANKROLL_TREE_HEX = os.getenv("BANKROLL_TREE_HEX", "")
WITHDRAW_REQUEST_TREE_HEX = os.getenv("WITHDRAW_REQUEST_TREE_HEX", "")
HOUSE_EDGE_BPS = int(os.getenv("HOUSE_EDGE_BPS", "300"))
COOLDOWN_BLOCKS = int(os.getenv("COOLDOWN_BLOCKS", "60"))
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS_STR", "http://localhost:3000")

# Oracle configuration
ORACLE_PRIMARY_URL = os.getenv("ORACLE_PRIMARY_URL", "https://api.oraclepool.xyz")
ORACLE_BACKUP_URLS = [u.strip() for u in os.getenv("ORACLE_BACKUP_URLS", "").split(",") if u.strip()]
ORACLE_STALE_THRESHOLD_SECONDS = int(os.getenv("ORACLE_STALE_THRESHOLD_SECONDS", "300"))
ORACLE_HEALTH_CHECK_INTERVAL_SECONDS = int(os.getenv("ORACLE_HEALTH_CHECK_INTERVAL_SECONDS", "30"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize pool manager, WebSocket manager, and oracle service on startup."""
    # WebSocket connection manager
    app.state.ws_manager = ConnectionManager()

    # Pool manager
    config = PoolConfig(
        pool_nft_id=POOL_NFT_ID or None,
        lp_token_id=LP_TOKEN_ID or None,
        bankroll_tree_hex=BANKROLL_TREE_HEX or None,
        withdraw_request_tree_hex=WITHDRAW_REQUEST_TREE_HEX or None,
        house_edge_bps=HOUSE_EDGE_BPS,
        cooldown_blocks=COOLDOWN_BLOCKS,
    )
    app.state.pool_manager = PoolStateManager(
        node_url=NODE_URL,
        api_key=API_KEY,
        config=config,
    )

    # Oracle service
    oracle_config = OracleConfig(
        primary_oracle_url=ORACLE_PRIMARY_URL,
        backup_oracle_urls=ORACLE_BACKUP_URLS,
        stale_threshold_seconds=ORACLE_STALE_THRESHOLD_SECONDS,
        health_check_interval_seconds=ORACLE_HEALTH_CHECK_INTERVAL_SECONDS,
    )
    app.state.oracle_service = OracleService(config=oracle_config)
    await app.state.oracle_service.start()

    yield

    # Cleanup on shutdown
    app.state.pool_manager = None
    app.state.ws_manager = None
    if app.state.oracle_service:
        await app.state.oracle_service.stop()
        app.state.oracle_service = None


# ─── App ────────────────────────────────────────────────────────────

app = FastAPI(
    title="DuckPools API",
    description="DuckPools Coinflip + LP Liquidity Pool API",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS
cors_origins = [o.strip() for o in CORS_ORIGINS_STR.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(lp_router, prefix="/api")
app.include_router(ws_router)
app.include_router(oracle_router)


# ─── Root Endpoints ─────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "DuckPools API",
        "version": "0.2.0",
        "endpoints": {
            "pool": "/api/lp/pool",
            "price": "/api/lp/price",
            "apy": "/api/lp/apy",
            "balance": "/api/lp/balance/{address}",
            "estimate_deposit": "/api/lp/estimate/deposit",
            "estimate_withdraw": "/api/lp/estimate/withdraw",
            "deposit": "POST /api/lp/deposit",
            "request_withdraw": "POST /api/lp/request-withdraw",
            "execute_withdraw": "POST /api/lp/execute-withdraw",
            "cancel_withdraw": "POST /api/lp/cancel-withdraw",
            "oracle_health": "/api/oracle/health",
            "oracle_status": "/api/oracle/status",
            "oracle_endpoints": "/api/oracle/endpoints",
            "oracle_data": "POST /api/oracle/data/{oracle_box_id}",
            "oracle_switch": "POST /api/oracle/switch",
        },
        "websocket": {
            "bet_updates": "ws://host/ws/bets/{address}",
            "stats": "/ws/stats",
        },
    }


@app.get("/health")
async def health():
    """Health check: verify node connectivity, pool state, and oracle status."""
    import httpx

    health_data = {"status": "ok", "node": NODE_URL, "pool_configured": bool(POOL_NFT_ID)}

    # Check node connectivity
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{NODE_URL}/info", headers={"api_key": API_KEY})
            resp.raise_for_status()
            info = resp.json()
            health_data["node_height"] = info.get("fullHeight")
    except Exception as e:
        health_data["status"] = "degraded"
        health_data["node_error"] = str(e)

    # Check pool state if configured
    if POOL_NFT_ID:
        try:
            mgr = app.state.pool_manager
            if mgr:
                state = await mgr.get_pool_state(force_refresh=True)
                health_data["pool_bankroll"] = str(state.bankroll)
                health_data["pool_supply"] = str(state.total_supply)
        except Exception as e:
            health_data["pool_error"] = str(e)

    # Check oracle status if configured
    try:
        oracle_svc = getattr(app.state, "oracle_service", None)
        if oracle_svc:
            oracle_status = oracle_svc.get_service_status()
            health_data["oracle_status"] = oracle_status["status"]
            health_data["oracle_endpoint"] = oracle_status["current_endpoint"]
            if oracle_status["status"] in ["stale", "degraded", "no_endpoints"]:
                health_data["status"] = "degraded"
    except Exception as e:
        health_data["oracle_error"] = str(e)

    return health_data


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
