"""
DuckPools - WebSocket Connection Manager

Manages per-address WebSocket channels for real-time bet status updates.
Clients subscribe by connecting to ws://host/ws/bets/{address} and receive
JSON events whenever a bet involving their address changes state.

SEC-A2: Connection limits — per-IP, global, and per-address subscription caps
        prevent DoS and unauthorized bulk monitoring.

MAT-30: Real-time game history with WebSocket updates
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("duckpools.ws")


class ConnectionLimitExceeded(Exception):
    """Raised when a connection would exceed configured limits."""
    pass


class ConnectionManager:
    """
    Bidirectional WebSocket connection manager with security limits.

    Limits enforced (SEC-A2):
    - MAX_CONNECTIONS_GLOBAL: Total concurrent connections across all IPs
    - MAX_CONNECTIONS_PER_IP: Concurrent connections from a single IP
    - MAX_SUBS_PER_ADDRESS: Connections subscribed to a single address
    - MAX_ADDRESSES_PER_CONN: Address subscriptions per single connection
    - MAX_SUBS_PER_CONN_GLOBAL: Hard cap on total subscriptions per connection

    - Clients connect and subscribe to one or more Ergo addresses.
    - When a bet event occurs, the backend calls broadcast() with the event.
    - All clients subscribed to the relevant address(es) receive the event.
    """

    # ─── Tunable limits (SEC-A2) ──────────────────────────────────
    MAX_CONNECTIONS_GLOBAL = 200
    MAX_CONNECTIONS_PER_IP = 5
    MAX_SUBS_PER_ADDRESS = 10
    MAX_ADDRESSES_PER_CONN = 5
    MAX_SUBS_PER_CONN_GLOBAL = 10

    def __init__(self) -> None:
        # address -> set of (websocket, connection_id)
        self._subscriptions: Dict[str, Set[tuple]] = defaultdict(set)
        # connection_id -> set of subscribed addresses (for cleanup)
        self._conn_addresses: Dict[int, Set[str]] = {}
        # connection_id -> client IP (for per-IP tracking)
        self._conn_ips: Dict[int, str] = {}
        # ip -> set of connection_ids (for per-IP limits)
        self._ip_connections: Dict[str, Set[int]] = defaultdict(set)
        # connection_id -> authenticated address (SEC-A1: locked to owner)
        self._conn_owner: Dict[int, str] = {}
        self._next_id: int = 0
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_ip: str) -> int:
        """
        Accept a WebSocket connection and return a connection ID.

        Enforces SEC-A2 limits:
        - Global connection cap
        - Per-IP connection cap

        Raises:
            ConnectionLimitExceeded: If limits would be exceeded.
        """
        async with self._lock:
            # SEC-A2: Global connection limit
            if len(self._conn_addresses) >= self.MAX_CONNECTIONS_GLOBAL:
                raise ConnectionLimitExceeded(
                    f"Global connection limit reached ({self.MAX_CONNECTIONS_GLOBAL})"
                )

            # SEC-A2: Per-IP connection limit
            ip_count = len(self._ip_connections.get(client_ip, set()))
            if ip_count >= self.MAX_CONNECTIONS_PER_IP:
                raise ConnectionLimitExceeded(
                    f"Per-IP connection limit reached ({self.MAX_CONNECTIONS_PER_IP}) "
                    f"for {client_ip}"
                )

            await websocket.accept()
            conn_id = self._next_id
            self._next_id += 1
            self._conn_addresses[conn_id] = set()
            self._conn_ips[conn_id] = client_ip
            self._ip_connections[client_ip].add(conn_id)

        logger.info("WS conn %d accepted from %s", conn_id, client_ip)
        return conn_id

    async def subscribe(self, conn_id: int, address: str, websocket: WebSocket) -> None:
        """
        Subscribe a connection to events for a specific address.

        Enforces SEC-A2 limits:
        - Per-address subscription cap (prevents bulk monitoring)
        - Per-connection address cap

        Raises:
            ConnectionLimitExceeded: If limits would be exceeded.
        """
        address = address.lower()
        async with self._lock:
            # SEC-A2: Per-address subscription limit
            addr_sub_count = len(self._subscriptions.get(address, set()))
            if addr_sub_count >= self.MAX_SUBS_PER_ADDRESS:
                raise ConnectionLimitExceeded(
                    f"Per-address subscription limit reached ({self.MAX_SUBS_PER_ADDRESS}) "
                    f"for {address}"
                )

            # SEC-A2: Per-connection address limit
            if conn_id in self._conn_addresses:
                conn_addr_count = len(self._conn_addresses[conn_id])
                if conn_addr_count >= self.MAX_ADDRESSES_PER_CONN:
                    raise ConnectionLimitExceeded(
                        f"Per-connection address limit reached "
                        f"({self.MAX_ADDRESSES_PER_CONN})"
                    )

            self._subscriptions[address].add((websocket, conn_id))
            self._conn_addresses[conn_id].add(address)
        logger.info("WS conn %d subscribed to %s", conn_id, address)

    async def unsubscribe(self, conn_id: int, address: str) -> None:
        """Unsubscribe a connection from a specific address."""
        address = address.lower()
        async with self._lock:
            to_remove = set()
            for ws, cid in self._subscriptions.get(address, set()):
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
            client_ip = self._conn_ips.pop(conn_id, None)
            if client_ip:
                self._ip_connections[client_ip].discard(conn_id)
                if not self._ip_connections[client_ip]:
                    del self._ip_connections[client_ip]

            self._conn_owner.pop(conn_id, None)

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

    def set_owner(self, conn_id: int, address: str) -> None:
        """
        SEC-A1: Lock a connection to a specific authenticated address.
        Once set, this connection can only subscribe to events for this address.
        Must be called before any subscribe() calls.
        """
        self._conn_owner[conn_id] = address.lower()

    def get_owner(self, conn_id: int) -> Optional[str]:
        """Get the authenticated owner address for a connection."""
        return self._conn_owner.get(conn_id)

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
        """Get connection manager statistics including limit info."""
        return {
            "active_connections": self.active_connections,
            "subscriptions_count": self.subscriptions_count,
            "tracked_addresses": len(self._subscriptions),
            "limits": {
                "max_connections_global": self.MAX_CONNECTIONS_GLOBAL,
                "max_connections_per_ip": self.MAX_CONNECTIONS_PER_IP,
                "max_subs_per_address": self.MAX_SUBS_PER_ADDRESS,
                "max_addresses_per_conn": self.MAX_ADDRESSES_PER_CONN,
            },
            "unique_ips": len(self._ip_connections),
        }
