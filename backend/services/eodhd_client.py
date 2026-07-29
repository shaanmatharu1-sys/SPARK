"""
services/eodhd_client.py — EODHD (eodhistoricaldata.com) REST client.

EODHD's edge over what's already wired up (Polygon, Finnhub) is global
exchange coverage: world indices, and non-US-listed tickers generally.
Polygon/Finnhub here are US-market-only. Used first to give World Indices
(previously EOD-only via yfinance, see international_client.py) a real
live quote + an intraday chart.

Three endpoints, confirmed against the live API:
  - /api/real-time/{symbol}   — latest (delayed) quote, batchable via `s=`
  - /api/intraday/{symbol}    — 1m/5m/1h OHLCV history, ~last 100 days max
  - /api/eod/{symbol}         — daily OHLCV history, full range

EODHD tickers are CODE.EXCHANGE (e.g. AAPL.US, GSPC.INDX). Requires
EODHD_API_KEY; every function degrades to {"available": False} rather than
raising when the key is missing or a request fails, matching the pattern
in services/analyst_client.py.
"""
import os
import logging

import aiohttp

from cache.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)

EODHD_API_KEY = os.getenv("EODHD_API_KEY", "")
BASE = "https://eodhd.com/api"

TTL_REALTIME = 30    # 30s — quotes are "live" (15-20min delayed on most exchanges)
TTL_INTRADAY = 60    # 1 min — chart bars
TTL_EOD      = 3600  # 1h — daily history barely moves intraday


def _unavailable(reason: str = "EODHD_API_KEY not configured") -> dict:
    return {
        "available": False,
        "reason": reason,
        "note": "Set EODHD_API_KEY in the environment to enable EODHD-backed data.",
    }


async def _get(session: aiohttp.ClientSession, path: str, params: dict):
    params = {**params, "api_token": EODHD_API_KEY, "fmt": "json"}
    url = f"{BASE}{path}"
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                return await r.json()
            body = await r.text()
            logger.warning(f"[EODHD] {url} -> {r.status}: {body[:200]}")
            return None
    except Exception as e:
        logger.error(f"[EODHD] {url} error: {e}")
        return None


async def fetch_realtime_quotes(symbols: list[str]) -> dict:
    """
    Latest quote for one or more EODHD tickers (e.g. ["GSPC.INDX", "FTSE.INDX"]).
    EODHD batches via the primary symbol + `s=` comma-list of the rest.
    Returns {available, quotes: {symbol: {price, change, change_pct, ...}}}.
    """
    if not EODHD_API_KEY:
        return _unavailable()
    if not symbols:
        return {"available": True, "quotes": {}}

    cache_key = f"eodhd:rt:{','.join(sorted(symbols))}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    primary, rest = symbols[0], symbols[1:]
    params = {"s": ",".join(rest)} if rest else {}

    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"/real-time/{primary}", params)

    if data is None:
        return {"available": False, "reason": "EODHD request failed", "quotes": {}}

    # Single symbol -> dict; multi-symbol -> list of dicts
    rows = data if isinstance(data, list) else [data]
    quotes = {}
    for row in rows:
        code = row.get("code")
        if not code or row.get("close") is None:
            continue
        quotes[code] = {
            "price":          row.get("close"),
            "open":           row.get("open"),
            "high":           row.get("high"),
            "low":            row.get("low"),
            "prev_close":     row.get("previousClose"),
            "change":         row.get("change"),
            "change_pct":     row.get("change_p"),
            "volume":         row.get("volume"),
            "timestamp":      row.get("timestamp"),
        }

    out = {"available": True, "quotes": quotes}
    if quotes:
        await cache_set(cache_key, out, TTL_REALTIME)
    return out


async def fetch_intraday(symbol: str, interval: str = "5m") -> dict:
    """
    Intraday OHLCV bars for `symbol` (EODHD code, e.g. "GSPC.INDX").
    interval: one of "1m", "5m", "1h". EODHD caps how far back 1m/5m go
    (~100 days / ~7 days respectively) — no explicit from/to here, just
    whatever EODHD returns for the default window.
    """
    if not EODHD_API_KEY:
        return _unavailable()

    cache_key = f"eodhd:intraday:{symbol}:{interval}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"/intraday/{symbol}", {"interval": interval})

    if data is None:
        return {"available": False, "reason": "EODHD request failed", "bars": []}

    bars = [
        {
            "t": row.get("timestamp") * 1000 if row.get("timestamp") else None,
            "o": row.get("open"), "h": row.get("high"),
            "l": row.get("low"),  "c": row.get("close"),
            "v": row.get("volume"),
        }
        for row in (data or []) if row.get("close") is not None
    ]

    out = {"available": True, "symbol": symbol, "interval": interval, "bars": bars}
    if bars:
        await cache_set(cache_key, out, TTL_INTRADAY)
    return out


async def fetch_eod(symbol: str, period: str = "d", from_date: str = None, to_date: str = None) -> dict:
    """Daily/weekly/monthly OHLCV history for `symbol`. period: "d" | "w" | "m"."""
    if not EODHD_API_KEY:
        return _unavailable()

    cache_key = f"eodhd:eod:{symbol}:{period}:{from_date}:{to_date}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    params = {"period": period}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"/eod/{symbol}", params)

    if data is None:
        return {"available": False, "reason": "EODHD request failed", "bars": []}

    bars = [
        {
            "t": row.get("date"),
            "o": row.get("open"), "h": row.get("high"),
            "l": row.get("low"),  "c": row.get("close"),
            "adj_c": row.get("adjusted_close"), "v": row.get("volume"),
        }
        for row in (data or []) if row.get("close") is not None
    ]

    out = {"available": True, "symbol": symbol, "bars": bars}
    if bars:
        await cache_set(cache_key, out, TTL_EOD)
    return out
