"""
services/analyst_client.py — Analyst ratings & price targets via Finnhub (free tier)

There is no free, keyless, official source for sell-side analyst
recommendations/price targets, so this uses Finnhub's free-tier REST API
(https://finnhub.io/api/v1), which requires a (free, self-serve) API key.

The key is read from the environment (FINNHUB_API_KEY) — never hardcoded —
following the same convention as services/vessel_client.py's AISSTREAM_API_KEY.
If it's not set, every function here returns {available: False, reason: ...}
rather than failing, so the tab degrades gracefully instead of crashing.
"""
import os
import asyncio
import logging

import aiohttp

from cache.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
BASE = "https://finnhub.io/api/v1"

TTL_RATINGS = 3600  # 1h — analyst data moves slowly intraday


def _unavailable(reason: str = "FINNHUB_API_KEY not configured") -> dict:
    return {
        "available": False,
        "reason": reason,
        "note": "Set FINNHUB_API_KEY in the environment to enable analyst ratings.",
    }


async def _get(session: aiohttp.ClientSession, path: str, params: dict) -> dict | list | None:
    params = {**params, "token": FINNHUB_API_KEY}
    url = f"{BASE}{path}"
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                return await r.json()
            body = await r.text()
            logger.warning(f"[Finnhub] {url} -> {r.status}: {body[:200]}")
            return None
    except Exception as e:
        logger.error(f"[Finnhub] {url} error: {e}")
        return None


async def fetch_analyst_ratings(symbol: str) -> dict:
    """
    Analyst consensus (buy/hold/sell counts by period) + price target for `symbol`.
    Requires FINNHUB_API_KEY; degrades gracefully to {available: False} otherwise.
    """
    symbol = symbol.upper()
    if not FINNHUB_API_KEY:
        return _unavailable()

    cache_key = f"analyst_ratings:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async with aiohttp.ClientSession() as session:
        recs, target = await asyncio.gather(
            _get(session, "/stock/recommendation", {"symbol": symbol}),
            _get(session, "/stock/price-target", {"symbol": symbol}),
        )

    recs = recs or []
    target = target or {}
    latest = recs[0] if recs else {}

    out = {
        "available": True,
        "symbol": symbol,
        "consensus": {
            "period":      latest.get("period"),
            "strong_buy":  latest.get("strongBuy", 0),
            "buy":         latest.get("buy", 0),
            "hold":        latest.get("hold", 0),
            "sell":        latest.get("sell", 0),
            "strong_sell": latest.get("strongSell", 0),
        } if latest else None,
        "history": [
            {
                "period":      r.get("period"),
                "strong_buy":  r.get("strongBuy", 0),
                "buy":         r.get("buy", 0),
                "hold":        r.get("hold", 0),
                "sell":        r.get("sell", 0),
                "strong_sell": r.get("strongSell", 0),
            } for r in recs[:6]
        ],
        "price_target": {
            "high":         target.get("targetHigh"),
            "low":          target.get("targetLow"),
            "mean":         target.get("targetMean"),
            "median":       target.get("targetMedian"),
            "last_updated": target.get("lastUpdated"),
        } if target else None,
        "source": "Finnhub",
    }

    if latest or target:
        await cache_set(cache_key, out, TTL_RATINGS)
    else:
        out = {"available": False, "symbol": symbol,
               "reason": "Finnhub returned no recommendation/price-target data for this ticker"}
    return out
