"""
DuckPools - WebSocket Routes

FastAPI WebSocket endpoint for real-time bet status updates.

Endpoints:
  ws://host/ws/bets/{address}  -- Subscribe to bet events for an address
  GET /ws/stats                -- WebSocket connection stats

MAT-30: Real-time game history with WebSocket updates
"""

import logging
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel

from ws_manager import ConnectionManager
from game_events import BetEvent, BetEventType

logger = logging.getLogger("duckpools.ws.routes")

router = APIRouter(tags=["websocket"])


# ─── WebSocket Endpoint ───────────────────────────────────────────

@router.websocket("/ws/bets/{address}")
async def ws_bet_subscription(websocket: WebSocket, address: str):
    """
    WebSocket endpoint for real-time bet updates.

    Client connects with: ws://host/ws/bets/{ergo_address}
    
    The client will receive JSON events for all bets involving the given
    address. Events follow the BetEvent schema:

    {
        "type": "bet_placed|bet_revealed|bet_settled|bet_refunded|pool_state_update",
        "timestamp": 1711584000.0,
        "bet_id": "abc123...",
        "player_address": "3W...",
        "payload": { ... event-specific data ... }
    }

    The server sends periodic ping frames (every 30s). Clients should
    respond to keep the connection alive. If no pong is received, the
    connection will be closed after 60s.

    To subscribe to additional addresses after connecting, send a JSON message:
    {"action": "subscribe", "address": "3W..."}
    {"action": "unsubscribe", "address": "3W..."}
    """
    ws_manager: ConnectionManager = websocket.app.state.ws_manager

    # Validate address (basic sanity check - must start with 3 or 9 and be >20 chars)
    address = address.strip()
    if len(address) < 20:
        await websocket.close(code=4001, reason="Invalid address: too short")
        return

    conn_id = await ws_manager.connect(websocket)
    await ws_manager.subscribe(conn_id, address, websocket)

    logger.info("WS connection %d established for %s", conn_id, address)

    # Send confirmation
    await websocket.send_json({
        "type": "subscribed",
        "address": address,
        "conn_id": conn_id,
        "message": f"Subscribed to bet events for {address[:10]}...{address[-6:]}",
    })

    # Track active subscriptions for this connection
    subscribed_addresses = {address}

    try:
        # Background ping task
        async def ping_loop():
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

        ping_task = asyncio.create_task(ping_loop())

        try:
            while True:
                # Wait for messages from client (subscribe/unsubscribe commands)
                data = await websocket.receive_text()
                try:
                    import json
                    msg = json.loads(data)
                    action = msg.get("action", "")

                    if action == "subscribe":
                        new_addr = msg.get("address", "")
                        if new_addr and len(new_addr) >= 20:
                            await ws_manager.subscribe(conn_id, new_addr, websocket)
                            subscribed_addresses.add(new_addr)
                            await websocket.send_json({
                                "type": "subscribed",
                                "address": new_addr,
                                "message": f"Subscribed to {new_addr[:10]}...{new_addr[-6:]}",
                            })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Invalid address for subscription",
                            })

                    elif action == "unsubscribe":
                        old_addr = msg.get("address", "")
                        if old_addr:
                            await ws_manager.unsubscribe(conn_id, old_addr)
                            subscribed_addresses.discard(old_addr)
                            await websocket.send_json({
                                "type": "unsubscribed",
                                "address": old_addr,
                            })

                    elif action == "ping":
                        await websocket.send_json({"type": "pong"})

                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown action: {action}",
                        })

                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })

        finally:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info("WS client %d disconnected normally", conn_id)
    except Exception as e:
        logger.error("WS error for conn %d: %s", conn_id, e)
    finally:
        # Clean up all subscriptions for this connection
        for addr in subscribed_addresses:
            await ws_manager.unsubscribe(conn_id, addr)
        await ws_manager.disconnect(conn_id)


# ─── REST Stats Endpoint ─────────────────────────────────────────

class WSStatsResponse(BaseModel):
    active_connections: int
    subscriptions_count: int
    tracked_addresses: int


@router.get("/ws/stats", response_model=WSStatsResponse)
async def ws_stats(request: Request):
    """Get WebSocket connection manager statistics."""
    ws_manager: ConnectionManager = request.app.state.ws_manager
    stats = ws_manager.get_stats()
    return WSStatsResponse(**stats)
