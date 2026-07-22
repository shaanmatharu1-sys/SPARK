"""
services/coinbase_ws_client.py — Live crypto prices via Coinbase's public
Exchange WebSocket (no key, no auth, market-data channels are unauthenticated
and unlimited). Crypto trades 24/7, so this is what makes the terminal's
"LIVE" badge actually mean something around the clock instead of just during
US equity hours — unlike the stock feed (finnhub_ws_client.py), which
necessarily goes quiet nights/weekends because no equity trades exist to
stream then.

Binance's public WS was tried first, but it returns HTTP 451 (geo-blocked)
from US-based hosts — Binance.com blocks US IPs outright. Coinbase is a
US-domiciled exchange with no such block, verified reachable directly
(subscribed to BTC-USD's ticker channel and received live ticks). Its
product IDs (BTC-USD, ETH-USD, ...) also map straight onto the "*USD"
symbols fetch_crypto_snapshot() already returns, no USDT-as-USD-proxy
conversion needed.

The `ticker` channel pushes on every trade (not a fixed interval) and
carries last price + 24h open/high/low/volume — the same shape the REST
snapshot exposes, so this is a drop-in live overlay on it.
"""
import asyncio
import json
import logging
import time

import websockets

from cache.redis_client import hset_quote, publish
from config import WS_RECV_TIMEOUT
from services.polygon_client import _WSFeedBase

logger = logging.getLogger(__name__)

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

# symbol (matches fetch_crypto_snapshot's "X:BTCUSD" -> "BTCUSD" convention)
# -> Coinbase product ID, so the WS overlay and REST snapshot describe the
# same coins under the same keys.
DEFAULT_PRODUCTS = {
    "BTCUSD":  "BTC-USD",
    "ETHUSD":  "ETH-USD",
    "SOLUSD":  "SOL-USD",
    "DOGEUSD": "DOGE-USD",
}


class CoinbaseCryptoWS(_WSFeedBase):
    """24/7 real-time crypto ticker stream — no API key required."""

    def __init__(self, products: dict[str, str] = None):
        super().__init__("Coinbase WS Crypto")
        self.products = products or DEFAULT_PRODUCTS
        self._product_to_symbol = {v: k for k, v in self.products.items()}

    async def _connect(self) -> bool:
        logger.info(f"[{self.name}] Connecting -> {len(self.products)} products")
        async with websockets.connect(COINBASE_WS_URL, ping_interval=20) as ws:
            self._ws = ws
            await ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": list(self.products.values()),
                "channels": ["ticker"],
            }))
            self.last_status = "subscribed"
            reached_live_data = False
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=WS_RECV_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.warning(f"[{self.name}] No message received in {WS_RECV_TIMEOUT}s — treating as stalled")
                    return reached_live_data

                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "error":
                    self.last_error = msg.get("message")
                    logger.error(f"[{self.name}] Error from Coinbase: {msg.get('message')}")
                    return reached_live_data
                if mtype != "ticker":
                    continue
                reached_live_data = True
                self.last_message_ts = time.time()
                await self._handle_ticker(msg)

    async def _handle_ticker(self, data: dict):
        symbol = self._product_to_symbol.get(data.get("product_id"))
        if not symbol:
            return
        try:
            price = float(data["price"])
            open_24h = float(data["open_24h"]) if data.get("open_24h") else None
            quote = {
                "type":       "crypto_ticker",
                "symbol":     symbol,
                "price":      price,
                "change_pct": round((price - open_24h) / open_24h * 100, 2) if open_24h else None,
                "high":       float(data["high_24h"]) if data.get("high_24h") else None,
                "low":        float(data["low_24h"]) if data.get("low_24h") else None,
                "volume":     float(data["volume_24h"]) if data.get("volume_24h") else None,
                "ts":         data.get("time"),
            }
        except (KeyError, ValueError, TypeError):
            return
        await hset_quote(f"CRYPTO:{symbol}", quote)
        await publish("crypto", quote)
