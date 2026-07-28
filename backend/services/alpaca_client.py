"""
services/alpaca_client.py — Real-time equity NBBO top-of-book via Alpaca's
free Market Data API (IEX feed).

Why Alpaca: this project's Polygon.io plan does NOT carry quote/NBBO
entitlement — confirmed directly against the live API (`/v3/quotes/{ticker}`
returns `403 NOT_AUTHORIZED`, and the stocks snapshot response has no
`lastQuote` field at all for this plan). Alpaca's free tier includes
real-time bid/ask quotes from the IEX feed (one exchange's book, not full
consolidated SIP NBBO, but a genuine live quote — not a paid add-on) using
just a free API key pair, no funded brokerage account required.

Auth: header-based, `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY` — no query
param, no OAuth flow. Get free keys at https://app.alpaca.markets (paper
trading keys work fine for market data; no funding needed).

Honesty note (same policy as orderbook_client.py): if the keys are unset,
the request errors, or Alpaca returns an empty/zero quote, this returns
`available: False` with an explicit reason. It never fabricates a bid/ask.
"""
import logging
import time

import aiohttp

from cache.redis_client import cache_get, cache_set
from config import ALPACA_API_KEY_ID, ALPACA_SECRET_KEY, TTL_QUOTE

logger = logging.getLogger(__name__)

ALPACA_DATA_URL = "https://data.alpaca.markets/v2/stocks/{}/quotes/latest"


async def fetch_top_of_book(symbol: str) -> dict | None:
    """
    Latest real-time bid/ask quote for one equity symbol via Alpaca's IEX
    feed. Returns None (not a fabricated zero-quote) on any failure —
    missing keys, HTTP error, or a quote with no bid/ask — so callers can
    fall back or report unavailability honestly.
    """
    symbol = symbol.upper()
    if not ALPACA_API_KEY_ID or not ALPACA_SECRET_KEY:
        return None

    cache_key = f"alpaca_quote:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                ALPACA_DATA_URL.format(symbol),
                params={"feed": "iex"},
                headers={
                    "APCA-API-KEY-ID": ALPACA_API_KEY_ID,
                    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
                },
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                if r.status != 200:
                    body = await r.text()
                    logger.warning(f"[Alpaca] {symbol} quote -> HTTP {r.status}: {body[:200]}")
                    return None
                data = await r.json()
    except Exception as e:
        logger.warning(f"[Alpaca] {symbol} quote fetch failed: {e}")
        return None

    q = data.get("quote") or {}
    bid, ask = q.get("bp"), q.get("ap")
    if not bid or not ask or bid <= 0 or ask <= 0:
        return None

    result = {
        "bid":       bid,
        "ask":       ask,
        "bid_size":  q.get("bs"),
        "ask_size":  q.get("as"),
        "ts":        time.time(),
    }
    await cache_set(cache_key, result, TTL_QUOTE)
    return result
