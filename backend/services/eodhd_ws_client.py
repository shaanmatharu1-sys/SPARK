"""
services/eodhd_ws_client.py — Real-time US equity trades AND top-of-book
quotes via EODHD's WebSocket feeds.

Why this exists: the previously-wired live-tick feed (services/
finnhub_ws_client.py) is dead — verified directly against the live API,
both Finnhub's REST (`/api/v1/quote`) and WS (`wss://ws.finnhub.io`) return
straight "Invalid API key." / HTTP 401 with the FINNHUB_API_KEY currently
configured. Separately, Polygon (this project's other paid data source) has
NO quote/NBBO entitlement at all on its current plan — verified directly:
its stocks snapshot has no `lastQuote` field, `/v3/quotes/{ticker}` and the
WS `Q.*` quotes channel both return NOT_AUTHORIZED/"not authorized". That's
why equities previously had neither live ticks nor any real bid/ask.

EODHD's WS auth succeeds with the EODHD_API_KEY already configured (verified
directly), and it exposes two separate real-time feeds for US equities:
  - wss://ws.eodhistoricaldata.com/ws/us        — trade ticks
  - wss://ws.eodhistoricaldata.com/ws/us-quote  — top-of-book bid/ask ticks
Confirmed live message shapes (2026-07-28):
  trade: {"s":"AAPL","p":316.9603,"c":[14,37,41],"v":48,"dp":false,"ms":"extended-hours","t":1784115290873}
  quote: {"s":"AAPL","ap":317.297,"as":160,"bp":316.988,"bs":40,"t":1784115291977}
Note EODHD does NOT offer order-book/Level-2 depth for equities either (no
vendor at this price point does — real equity depth is an enterprise-tier
product). This module gives real top-of-book bid/ask, which is the honest
ceiling for equities here; crypto's genuine full depth stays on Coinbase
(see services/orderbook_client.py).

EODHDStocksWS publishes to the exact same Redis sinks the Finnhub feed used
(hset_quote + the "quotes" channel, `type: "trade"` / `type: "bar"` shaped
identically) so MarketMonitor/PriceChart need zero changes — pure producer
swap, same as when Polygon's stocks feed was swapped for Finnhub's.
EODHDQuotesWS keeps its own in-memory best-bid/ask store, read by
services/orderbook_client.py's fetch_equity_top_of_book().
"""
import asyncio
import json
import logging
import os
import time

import websockets

from cache.redis_client import hset_quote, publish
from config import WS_RECV_TIMEOUT
from services.polygon_client import _WSFeedBase
from services.finnhub_ws_client import _us_equities_session_open, _STALL_TIMEOUT_OPEN, _STALL_TIMEOUT_CLOSED

logger = logging.getLogger(__name__)

EODHD_API_KEY = os.getenv("EODHD_API_KEY", "")
EODHD_TRADES_WS_URL = "wss://ws.eodhistoricaldata.com/ws/us"
EODHD_QUOTES_WS_URL = "wss://ws.eodhistoricaldata.com/ws/us-quote"


class EODHDStocksWS(_WSFeedBase):
    """Real-time trade ticks (+ synthesized live minute bars) via EODHD's WS."""

    def __init__(self, symbols: list[str] = None):
        super().__init__("EODHD WS Stocks (trades)")
        self.symbols = list(symbols or [])
        self._current_bars: dict[str, dict] = {}

    async def start(self):
        if not EODHD_API_KEY:
            logger.warning("[EODHD WS Stocks] EODHD_API_KEY not set — real-time stock feed disabled.")
            self.last_status = "unconfigured"
            self.last_error = "EODHD_API_KEY not configured"
            return
        await super().start()

    async def _connect(self) -> bool:
        url = f"{EODHD_TRADES_WS_URL}?api_token={EODHD_API_KEY}"
        logger.info(f"[{self.name}] Connecting -> {EODHD_TRADES_WS_URL}")
        async with websockets.connect(url, ping_interval=20) as ws:
            self._ws = ws
            if self.symbols:
                await ws.send(json.dumps({"action": "subscribe", "symbols": ",".join(self.symbols)}))
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
                if "status_code" in msg:
                    if msg["status_code"] != 200:
                        self.last_error = msg.get("message")
                        logger.error(f"[{self.name}] Error from EODHD: {msg.get('message')}")
                        return reached_live_data
                    continue  # connection/auth ack, not a tick

                if msg.get("s") is None or msg.get("p") is None:
                    continue
                reached_live_data = True
                self.last_message_ts = time.time()
                self.last_status = "subscribed"
                await self._handle_trade(msg)

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

        # Roll into a running current-minute bar — EODHD's trade feed has no
        # native aggregate stream either, same gap Finnhub's feed had.
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


# In-memory top-of-book store: {symbol: {bid, bid_size, ask, ask_size, ts}}
_equity_quotes: dict[str, dict] = {}


def get_equity_quote(symbol: str) -> dict | None:
    """Synchronous read of the live top-of-book quote for one equity symbol,
    or None if no quote tick has arrived yet (not subscribed, or market closed
    since first subscribing)."""
    return _equity_quotes.get(symbol.upper())


class EODHDQuotesWS(_WSFeedBase):
    """
    Real-time top-of-book bid/ask via EODHD's dedicated quotes WS. This is
    the ONLY real bid/ask this app has for equities — Polygon's plan has no
    quote entitlement at all (verified directly). Still top-of-book only,
    not full depth: no vendor at this price point sells real equity Level 2.
    Supports subscribing to new symbols on demand (see ensure_subscribed),
    so a symbol typed into the Order Book tab that isn't in the startup
    watchlist still gets picked up live within moments.
    """

    def __init__(self, symbols: list[str] = None):
        super().__init__("EODHD WS Stocks (quotes)")
        self.symbols: set[str] = set(symbols or [])

    async def start(self):
        if not EODHD_API_KEY:
            logger.warning("[EODHD WS Quotes] EODHD_API_KEY not set — equity top-of-book feed disabled.")
            self.last_status = "unconfigured"
            self.last_error = "EODHD_API_KEY not configured"
            return
        await super().start()

    async def ensure_subscribed(self, symbol: str):
        """Add a symbol to the live quote feed on demand (e.g. a ticker
        someone types into the Order Book tab that isn't in the default
        watchlist). No-ops if already tracked."""
        symbol = symbol.upper()
        if symbol in self.symbols:
            return
        self.symbols.add(symbol)
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"action": "subscribe", "symbols": symbol}))
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to live-subscribe {symbol}: {e}")

    async def _connect(self) -> bool:
        url = f"{EODHD_QUOTES_WS_URL}?api_token={EODHD_API_KEY}"
        logger.info(f"[{self.name}] Connecting -> {EODHD_QUOTES_WS_URL}")
        async with websockets.connect(url, ping_interval=20) as ws:
            self._ws = ws
            if self.symbols:
                await ws.send(json.dumps({"action": "subscribe", "symbols": ",".join(self.symbols)}))
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
                if "status_code" in msg:
                    if msg["status_code"] != 200:
                        self.last_error = msg.get("message")
                        logger.error(f"[{self.name}] Error from EODHD: {msg.get('message')}")
                        return reached_live_data
                    continue

                symbol = msg.get("s")
                if not symbol or msg.get("bp") is None or msg.get("ap") is None:
                    continue
                reached_live_data = True
                self.last_message_ts = time.time()
                self.last_status = "subscribed"
                _equity_quotes[symbol.upper()] = {
                    "bid": msg.get("bp"), "bid_size": msg.get("bs"),
                    "ask": msg.get("ap"), "ask_size": msg.get("as"),
                    "ts": msg.get("t"),
                }
