"""
websocket/manager.py — Manages all frontend WebSocket connections and broadcasts
"""
import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Tracks active WebSocket connections per channel.
    Channels: "quotes", "options", "unusual", "news", "macro"
    """

    def __init__(self):
        # channel -> set of active WebSocket connections
        self.channels: Dict[str, Set[WebSocket]] = {
            "quotes":  set(),
            "options": set(),
            "unusual": set(),
            "news":    set(),
            "macro":   set(),
            "sectors": set(),
        }

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.channels:
            self.channels[channel] = set()
        self.channels[channel].add(websocket)
        logger.info(f"[WS] Client connected to channel '{channel}' — "
                    f"{len(self.channels[channel])} total")

    def disconnect(self, websocket: WebSocket, channel: str):
        self.channels.get(channel, set()).discard(websocket)
        logger.info(f"[WS] Client disconnected from channel '{channel}'")

    async def broadcast(self, channel: str, data: dict):
        """Send a message to all clients on a channel. Drop dead connections."""
        if channel not in self.channels:
            return
        dead: Set[WebSocket] = set()
        message = json.dumps(data)
        for ws in self.channels[channel].copy():
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.channels[channel].discard(ws)

    async def broadcast_all(self, data: dict):
        """Broadcast to every channel (e.g. system announcements)."""
        for channel in self.channels:
            await self.broadcast(channel, data)

    def client_count(self, channel: str) -> int:
        return len(self.channels.get(channel, set()))


# ── Module-level singleton ───────────────────────────────────────
manager = ConnectionManager()
