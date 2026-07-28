"""
services/orderbook_client.py — Live, top-50-depth crypto order books via
Coinbase's public Exchange WebSocket `level2_batch` channel (no key, no
auth — same free feed family as coinbase_ws_client.py's `ticker`
subscription, but a SEPARATE connection: this module owns its own
`_WSFeedBase` instance so a bug or disconnect here can never take down the
existing live crypto ticker already wired into main.py).

NOTE: Coinbase's true full-depth `level2` (and `level3`/`full`) channels now
require authentication — verified directly against the live feed: subscribing
to `level2` returns `{"type":"error","message":"Failed to
subscribe","reason":"level2, level3, and full channels now require
authentication. https://docs.cloud.coinbase.com/exchange/docs/websocket-auth"}`.
That's a Coinbase policy change since this module was first written, not a
bug in this code — first found the hard way (the WS feed sat in
`circuit_open` with that exact error). `level2_batch` is the channel that's
still public/unauthenticated; Coinbase auto-remaps it server-side to
`level2_50` (confirmed via the `subscriptions` ack), i.e. top-50-levels
snapshot + incremental updates, batched roughly once/second rather than on
every single order-book change. Plenty of real depth for a research UI, and
still genuinely live market data — just top-50 instead of the full book.

`level2_batch`'s snapshot message can exceed `websockets`' default 1MiB
frame-size limit (an initial BTC-USD snapshot alone got close to it), so the
connection below raises `max_size` — without that it silently disconnects
with "message too big" the first time a snapshot arrives.

Coinbase's `level2_batch` channel sends, per product:
  1. one `snapshot` message — top-50 `bids`/`asks` arrays of [price, size]
  2. a stream of `l2update` messages — `changes`: list of [side, price,
     size] tuples, where size "0" means "remove this price level entirely"
     (not "size is zero, keep the level").

This module maintains the resulting order book in memory (per product,
`{"bids": {price: size}, "asks": {price: size}}`), and exposes:

  - `get_book_snapshot(product_id, depth)` — synchronous, reads the
    in-memory book directly (used by the WS feed's own throttled publish).
  - `fetch_rest_snapshot(product_id, depth)` — async REST fallback via
    Coinbase's public `GET /products/{id}/book?level=2` endpoint, used by
    routers/orderbook.py when neither the in-memory book nor the Redis
    cache has anything yet (e.g. right after a fresh deploy, before this
    WS has received its first snapshot).
  - `fetch_equity_top_of_book(symbol)` — best-effort equity NBBO. Tries
    Alpaca's free Market Data API first (services/alpaca_client.py, IEX
    feed, real-time bid/ask), then falls back to Polygon's REST snapshot
    `lastQuote` field (P=bid, p=ask) — that field is only populated when
    the Polygon plan carries quote/NBBO entitlement, which this project's
    plan does NOT have (confirmed: `/v3/quotes` -> 403 NOT_AUTHORIZED), so
    Alpaca is what actually serves this in practice. If neither source has
    a usable quote, this returns nulls with an explicit `"depth_limited"` /
    unavailable note rather than fabricating a bid/ask. Equities NEVER get
    synthetic order book levels here — only a real top-of-book quote, or
    nothing.
"""
import asyncio
import json
import logging
import time

import aiohttp
import websockets

from cache.redis_client import cache_get, cache_set, publish
from config import WS_RECV_TIMEOUT, TTL_ORDERBOOK
from services.polygon_client import _WSFeedBase, fetch_snapshot
from services.alpaca_client import fetch_top_of_book as fetch_alpaca_quote

logger = logging.getLogger(__name__)

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"
COINBASE_REST_BOOK_URL = "https://api.exchange.coinbase.com/products/{}/book"

# symbol (no-dash form, matches coinbase_ws_client's DEFAULT_PRODUCTS keys)
# -> Coinbase product ID. Duplicated here (rather than imported) so this
# module has zero coupling to coinbase_ws_client.py's ticker feed — they
# are independent WS connections that happen to describe the same coins.
PRODUCTS = {
    "BTCUSD":  "BTC-USD",
    "ETHUSD":  "ETH-USD",
    "SOLUSD":  "SOL-USD",
    "DOGEUSD": "DOGE-USD",
}
_PRODUCT_IDS = list(PRODUCTS.values())

# In-memory order books, keyed by Coinbase product_id (e.g. "BTC-USD"):
#   {"BTC-USD": {"bids": {price: size}, "asks": {price: size}}}
_books: dict[str, dict] = {}

# Throttle Redis publish/cache-write frequency per product — l2update
# messages can arrive many times a second on a busy book; broadcasting
# every single one would flood Redis pub/sub and every connected browser
# tab for no visible benefit at human scale. Cap to ~6/sec per product.
_PUBLISH_MIN_INTERVAL = 0.15
_last_publish: dict[str, float] = {}


def _resolve_product_id(raw: str) -> str | None:
    """Accepts 'BTC-USD', 'BTCUSD', 'btc-usd', etc. Returns the canonical
    dashed Coinbase product_id, or None if not a recognized crypto product."""
    if not raw:
        return None
    key = raw.upper().replace("-", "").replace("_", "").strip()
    return PRODUCTS.get(key)


def _compute_snapshot(product_id: str, depth: int = 25) -> dict | None:
    """Builds the top-N-levels-each-side response shape from the in-memory
    book: sorted correctly (bids descending, asks ascending), with
    cumulative depth totals, spread, and mid price."""
    book = _books.get(product_id)
    if not book or (not book["bids"] and not book["asks"]):
        return None

    bid_prices = sorted(book["bids"].keys(), reverse=True)[:depth]
    ask_prices = sorted(book["asks"].keys())[:depth]

    bid_levels, cum = [], 0.0
    for p in bid_prices:
        sz = book["bids"][p]
        cum += sz
        bid_levels.append({"price": p, "size": round(sz, 8), "total": round(cum, 8)})

    ask_levels, cum = [], 0.0
    for p in ask_prices:
        sz = book["asks"][p]
        cum += sz
        ask_levels.append({"price": p, "size": round(sz, 8), "total": round(cum, 8)})

    best_bid = bid_prices[0] if bid_prices else None
    best_ask = ask_prices[0] if ask_prices else None
    spread = round(best_ask - best_bid, 8) if (best_bid is not None and best_ask is not None) else None
    mid = round((best_ask + best_bid) / 2, 8) if spread is not None else None

    return {
        "type":            "orderbook",
        "symbol":          product_id,
        "crypto":          True,
        "depth_limited":   False,
        "note":            "Top-50 order book depth per side — live, unauthenticated public feed from Coinbase Exchange (their deeper level2/full channels now require API auth).",
        "bids":            bid_levels,
        "asks":            ask_levels,
        "best_bid":        best_bid,
        "best_ask":        best_ask,
        "spread":          spread,
        "mid":             mid,
        "bid_level_count": len(book["bids"]),
        "ask_level_count": len(book["asks"]),
        "ts":              time.time(),
    }


def get_book_snapshot(product_id: str, depth: int = 25) -> dict | None:
    """Synchronous read of the current in-memory book (no I/O) — used by
    the WS feed's own throttled publish path and available for any other
    in-process caller that doesn't want a Redis round-trip."""
    return _compute_snapshot(product_id, depth)


async def _maybe_publish(product_id: str, depth: int = 25):
    now = time.time()
    if now - _last_publish.get(product_id, 0) < _PUBLISH_MIN_INTERVAL:
        return
    snap = _compute_snapshot(product_id, depth)
    if not snap:
        return
    _last_publish[product_id] = now
    await cache_set(f"orderbook:{product_id}", snap, TTL_ORDERBOOK)
    await publish("orderbook", snap)


async def fetch_rest_snapshot(product_id: str, depth: int = 25) -> dict | None:
    """REST fallback: Coinbase's public (no-key) level-2 book endpoint.
    Used on a fresh page load / cold start before the WS feed below has
    received its first snapshot, or by clients that only poll. Also seeds
    the in-memory book so a REST hit before the WS connects isn't wasted."""
    cache_key = f"orderbook:{product_id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                COINBASE_REST_BOOK_URL.format(product_id),
                params={"level": 2},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                if r.status != 200:
                    logger.warning(f"[OrderBook REST] {product_id} -> HTTP {r.status}")
                    return None
                data = await r.json()
    except Exception as e:
        logger.warning(f"[OrderBook REST] {product_id} fetch failed: {e}")
        return None

    bids = {float(p): float(s) for p, s, *_ in data.get("bids", [])}
    asks = {float(p): float(s) for p, s, *_ in data.get("asks", [])}
    _books[product_id] = {"bids": bids, "asks": asks}

    snap = _compute_snapshot(product_id, depth)
    if snap:
        await cache_set(cache_key, snap, TTL_ORDERBOOK)
    return snap


async def fetch_equity_top_of_book(symbol: str) -> dict:
    """
    Best-effort equity best-bid/ask — NOT full depth.

    Primary source: Alpaca's free Market Data API (IEX feed, real-time
    bid/ask — see services/alpaca_client.py). Falls back to Polygon's
    stock snapshot `lastQuote` field (P=bid price, p=ask price, S=bid
    size, s=ask size) if Alpaca is unavailable — that field is only
    populated when the Polygon plan carries NBBO/quote entitlement, which
    this project's plan does not (confirmed: `/v3/quotes` returns 403
    NOT_AUTHORIZED), so in practice Alpaca is what actually serves this.

    Honesty note: if neither source has a usable quote, this returns
    nulls with `depth_limited` and a clear unavailable note — it never
    invents a bid/ask spread.
    """
    symbol = symbol.upper()
    source = "alpaca"
    quote = await fetch_alpaca_quote(symbol)

    if quote:
        bid, ask = quote["bid"], quote["ask"]
        bid_size, ask_size = quote["bid_size"], quote["ask_size"]
    else:
        source = "polygon"
        snapshot = await fetch_snapshot([symbol])
        t = (snapshot or {}).get(symbol, {}) or {}
        last_quote = t.get("lastQuote") or {}
        bid = last_quote.get("P")
        ask = last_quote.get("p")
        bid_size = last_quote.get("S")
        ask_size = last_quote.get("s")

    available = bool(bid) and bool(ask) and bid > 0 and ask > 0

    return {
        "type":          "orderbook",
        "symbol":        symbol,
        "crypto":        False,
        "depth_limited": True,
        "available":     available,
        "source":        source if available else None,
        "note": (
            "Equities show best-bid/ask only (NBBO top-of-book), not full market depth — "
            "true Level 2 equity depth requires a paid data entitlement this terminal does "
            "not currently have. No synthetic order book levels are generated."
            if available else
            "Best bid/ask is unavailable for this symbol on the current data plan. "
            "No fabricated quote or depth is shown — this is a real limitation, not a bug."
        ),
        "bids":          [],
        "asks":          [],
        "best_bid":      bid if available else None,
        "best_ask":      ask if available else None,
        "best_bid_size": bid_size if available else None,
        "best_ask_size": ask_size if available else None,
        "spread":        round(ask - bid, 4) if available else None,
        "mid":           round((ask + bid) / 2, 4) if available else None,
        "ts":            time.time(),
    }


class CoinbaseOrderBookWS(_WSFeedBase):
    """24/7 real-time top-50-depth crypto order book stream (Coinbase
    `level2_batch` channel — see the module docstring for why this isn't
    the deeper `level2` channel: that one now requires auth) — no API key
    required. Independent connection from CoinbaseCryptoWS (ticker channel)
    in coinbase_ws_client.py."""

    def __init__(self, products: dict[str, str] = None):
        super().__init__("Coinbase WS OrderBook (L2)")
        self.products = products or PRODUCTS  # symbol -> product_id

    async def _connect(self) -> bool:
        product_ids = list(self.products.values())
        logger.info(f"[{self.name}] Connecting -> {len(product_ids)} products (level2_batch)")
        # max_size raised: a level2_batch snapshot can exceed the websockets
        # library's default 1MiB frame limit and otherwise disconnects with
        # "message too big" on the very first snapshot (verified directly).
        async with websockets.connect(COINBASE_WS_URL, ping_interval=20, max_size=2**23) as ws:
            self._ws = ws
            await ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": product_ids,
                "channels": [{"name": "level2_batch", "product_ids": product_ids}],
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

                product_id = msg.get("product_id")
                if not product_id or product_id not in self.products.values():
                    continue

                if mtype == "snapshot":
                    self._handle_snapshot(msg)
                elif mtype == "l2update":
                    self._handle_l2update(msg)
                else:
                    continue

                reached_live_data = True
                self.last_message_ts = time.time()
                self.last_status = "subscribed"
                await _maybe_publish(product_id)

    def _handle_snapshot(self, msg: dict):
        product_id = msg["product_id"]
        try:
            bids = {float(p): float(s) for p, s in msg.get("bids", [])}
            asks = {float(p): float(s) for p, s in msg.get("asks", [])}
        except (TypeError, ValueError):
            return
        _books[product_id] = {"bids": bids, "asks": asks}

    def _handle_l2update(self, msg: dict):
        product_id = msg["product_id"]
        book = _books.setdefault(product_id, {"bids": {}, "asks": {}})
        for change in msg.get("changes", []):
            try:
                side, price_str, size_str = change
                price = float(price_str)
                size = float(size_str)
            except (ValueError, TypeError):
                continue
            side_book = book["bids"] if side == "buy" else book["asks"]
            if size == 0:
                side_book.pop(price, None)
            else:
                side_book[price] = size
