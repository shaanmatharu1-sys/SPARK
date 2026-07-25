"""
services/finnhub_ws_client.py — Real-time US stock trades via Finnhub's
WebSocket, which is free even on Finnhub's no-cost tier (up to 50 symbols) —
unlike Polygon, where real-time is paywalled behind a paid plan. This is the
cost-motivated swap for the live-tick feed specifically; options chain/Greeks/
IV surface and everything else REST-based stays on Polygon (see
services/polygon_client.py) since Finnhub's options depth/reliability isn't
proven to match it.

Publishes to the exact same Redis sinks Polygon's stocks feed used
(hset_quote + the "quotes" pub/sub channel), so every existing consumer
(MarketMonitor's trade listener, PriceChart's bar listener, the REST
snapshot fallback) needs ZERO changes — this is purely a producer swap.

Finnhub's WS only streams raw trades, not pre-aggregated bars (Polygon's
`AM` event had no Finnhub equivalent) — PriceChart.jsx's live candle updates
key off `type: "bar"` messages, so this module rolls trades up into a
running current-minute OHLCV bar and publishes that alongside each trade,
synthesizing what Polygon provided natively.
"""
import asyncio
import datetime
import json
import logging
import os
import time
from zoneinfo import ZoneInfo

import websockets

from cache.redis_client import hset_quote, publish
from config import WS_RECV_TIMEOUT
from services.polygon_client import _WSFeedBase

logger = logging.getLogger(__name__)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
FINNHUB_WS_URL = "wss://ws.finnhub.io"

_ET = ZoneInfo("America/New_York")
_STALL_TIMEOUT_OPEN   = WS_RECV_TIMEOUT  # 25s — catches a genuinely dead connection fast during trading hours
_STALL_TIMEOUT_CLOSED = 1200             # 20 min — outside trading hours there's nothing to receive


def _us_equities_session_open() -> bool:
    """
    Best-effort trading-session check (regular + extended hours, no holiday
    calendar) — 4:00-20:00 ET on weekdays is the window US equity trades can
    actually occur. Outside it, "no trade in 25s" isn't a stalled connection,
    it's a market with nothing to report — treating that silence as a
    failure was tripping the circuit breaker roughly every 30s overnight
    (confirmed in prod logs: repeated stall/reconnect/circuit-open cycles
    around midnight ET, with the Finnhub auth+subscribe itself succeeding
    every single time — the key was never the problem).
    """
    now = datetime.datetime.now(_ET)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 4 * 60 <= minutes < 20 * 60


class FinnhubStocksWS(_WSFeedBase):
    """Real-time trade ticks (+ synthesized live minute bars) via Finnhub's free WS."""

    def __init__(self, symbols: list[str] = None):
        super().__init__("Finnhub WS Stocks")
        self.symbols = symbols or []
        self._current_bars: dict[str, dict] = {}  # symbol -> running OHLCV for the current minute

    async def start(self):
        if not FINNHUB_API_KEY:
            logger.warning(
                "[Finnhub WS Stocks] FINNHUB_API_KEY not set — real-time stock feed disabled. "
                "Sign up for a free key at finnhub.io and set FINNHUB_API_KEY to enable it."
            )
            self.last_status = "unconfigured"
            self.last_error = "FINNHUB_API_KEY not configured"
            return
        await super().start()

    async def _connect(self) -> bool:
        url = f"{FINNHUB_WS_URL}?token={FINNHUB_API_KEY}"
        logger.info(f"[{self.name}] Connecting -> {FINNHUB_WS_URL}")
        async with websockets.connect(url, ping_interval=20) as ws:
            self._ws = ws
            for sym in self.symbols:
                await ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
            logger.info(f"[{self.name}] Subscribed to {len(self.symbols)} symbols")

            session_open = _us_equities_session_open()
            stall_timeout = _STALL_TIMEOUT_OPEN if session_open else _STALL_TIMEOUT_CLOSED

            reached_live_data = False
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=stall_timeout)
                except asyncio.TimeoutError:
                    if session_open:
                        logger.warning(f"[{self.name}] No message received in {stall_timeout}s — treating as stalled")
                        return reached_live_data
                    logger.info(f"[{self.name}] Quiet for {stall_timeout}s (outside equities trading hours) — reconnecting, not a failure")
                    return True

                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "ping":
                    continue
                elif mtype == "error":
                    self.last_error = msg.get("msg")
                    logger.error(f"[{self.name}] Error from Finnhub: {msg.get('msg')}")
                    return reached_live_data
                elif mtype == "trade":
                    for tick in msg.get("data", []) or []:
                        reached_live_data = True
                        self.last_message_ts = time.time()
                        self.last_status = "subscribed"
                        await self._handle_trade(tick)

    async def _handle_trade(self, tick: dict):
        symbol = tick.get("s")
        price = tick.get("p")
        size = tick.get("v")
        ts = tick.get("t")  # epoch ms
        if not symbol or price is None:
            return

        trade_quote = {
            "type": "trade", "symbol": symbol, "price": price,
            "size": size, "ts": ts, "cond": tick.get("c", []),
        }
        await hset_quote(symbol, trade_quote)
        await publish("quotes", trade_quote)

        # Roll the tick into a running current-minute bar (Finnhub has no
        # native aggregate stream) so PriceChart.jsx's live candle keeps
        # updating exactly as it did off Polygon's AM events.
        minute_ts = (ts // 60000) * 60000 if ts else None
        bar = self._current_bars.get(symbol)
        if not bar or bar["minute_ts"] != minute_ts:
            bar = {"minute_ts": minute_ts, "open": price, "high": price, "low": price, "close": price, "volume": 0}
            self._current_bars[symbol] = bar
        bar["high"] = max(bar["high"], price)
        bar["low"] = min(bar["low"], price)
        bar["close"] = price
        bar["volume"] += size or 0

        bar_quote = {
            "type": "bar", "symbol": symbol,
            "open": bar["open"], "high": bar["high"], "low": bar["low"], "close": bar["close"],
            "volume": bar["volume"], "vwap": None, "ts": minute_ts,
        }
        await hset_quote(symbol, bar_quote)
        await publish("quotes", bar_quote)
