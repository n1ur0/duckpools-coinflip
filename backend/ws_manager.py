"""
DuckPools - WebSocket Connection Manager

Manages per-address WebSocket channels for real-time bet status updates.
Clients subscribe by connecting to ws://host/ws/bets/{address} and receive
JSON events whenever a bet involving their address changes state.

MAT-30: Real-time game history with WebSocket updates
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("duckpools.ws")


class ConnectionManager:
    """
    Bidirectional WebSocket connection manager.

    - Clients connect and subscribe to one or more Ergo addresses.
    - When a bet event occurs, the backend calls broadcast() with the event.
    - All clients subscribed to the relevant address(es) receive the event.
    """

    def __init__(self) -> None:
        # address -> set of (websocket, connection_id)
        self._subscriptions: Dict[str, Set[tuple]] = defaultdict(set)
        # connection_id -> set of subscribed addresses (for cleanup)
        self._conn_addresses: Dict[int, Set[str]] = {}
        self._next_id: int = 0
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> int:
        """Accept a WebSocket connection and return a connection ID."""
        await websocket.accept()
        async with self._lock:
            conn_id = self._next_id
            self._next_id += 1
            self._conn_addresses[conn_id] = set()
        return conn_id

    async def subscribe(self, conn_id: int, address: str, websocket: WebSocket) -> None:
        """Subscribe a connection to events for a specific address."""
        address = address.lower()
        async with self._lock:
            self._subscriptions[address].add((websocket, conn_id))
            self._conn_addresses[conn_id].add(address)
        logger.info("WS conn %d subscribed to %s", conn_id, address)

    async def unsubscribe(self, conn_id: int, address: str) -> None:
        """Unsubscribe a connection from a specific address."""
        address = address.lower()
        async with self._lock:
            self._subscriptions[address].discard(
                (None, conn_id)  # we don't have ws ref here, match by conn_id only
            )
            # Actually we need to filter properly
            to_remove = set()
            for ws, cid in self._subscriptions[address]:
                if cid == conn_id:
                    to_remove.add((ws, cid))
            self._subscriptions[address] -= to_remove
            if not self._subscriptions[address]:
                del self._subscriptions[address]
            if conn_id in self._conn_addresses:
                self._conn_addresses[conn_id].discard(address)

    async def disconnect(self, conn_id: int) -> None:
        """Remove a connection and all its subscriptions."""
        async with self._lock:
            addresses = self._conn_addresses.pop(conn_id, set())
            for addr in addresses:
                to_remove = set()
                for ws, cid in self._subscriptions.get(addr, set()):
                    if cid == conn_id:
                        to_remove.add((ws, cid))
                self._subscriptions[addr] -= to_remove
                if not self._subscriptions[addr]:
                    del self._subscriptions[addr]
        logger.info("WS conn %d disconnected (was on %d addresses)", conn_id, len(addresses))

    async def broadcast_to_address(self, address: str, event: dict) -> int:
        """
        Broadcast an event to all connections subscribed to an address.
        Returns the number of connections that received the event.
        """
        address = address.lower()
        sent = 0
        dead = []

        async with self._lock:
            subscribers = list(self._subscriptions.get(address, set()))

        for ws, conn_id in subscribers:
            try:
                await ws.send_json(event)
                sent += 1
            except Exception:
                dead.append((ws, conn_id))

        # Clean up dead connections
        if dead:
            async with self._lock:
                for ws, conn_id in dead:
                    self._subscriptions[address].discard((ws, conn_id))
                    if conn_id in self._conn_addresses:
                        self._conn_addresses[conn_id].discard(address)
                if address in self._subscriptions and not self._subscriptions[address]:
                    del self._subscriptions[address]
            logger.warning(
                "WS cleaned up %d dead connections for %s", len(dead), address
            )

        return sent

    async def broadcast_global(self, event: dict) -> int:
        """
        Broadcast an event to ALL connected clients regardless of subscription.
        Useful for system-wide events (pool state changes, maintenance notices).
        """
        sent = 0
        seen: set = set()

        async with self._lock:
            for addr, subscribers in self._subscriptions.items():
                for ws, conn_id in subscribers:
                    if conn_id not in seen:
                        seen.add(conn_id)
                        try:
                            await ws.send_json(event)
                            sent += 1
                        except Exception:
                            pass

        return sent

    @property
    def active_connections(self) -> int:
        """Total number of active WebSocket connections."""
        return len(self._conn_addresses)

    @property
    def subscriptions_count(self) -> int:
        """Total number of address subscriptions."""
        return sum(len(v) for v in self._subscriptions.values())

    def get_stats(self) -> dict:
        """Get connection manager statistics."""
        return {
            "active_connections": self.active_connections,
            "subscriptions_count": self.subscriptions_count,
            "tracked_addresses": len(self._subscriptions),
        }
