"""
services/sentiment_social.py — Social media sentiment

IMPORTANT LIMITATION: there is no high-quality *free* social sentiment source
as of 2026. Twitter/X API is paid, Reddit's API is restricted. This uses
StockTwits' public symbol stream, which is free but rate-limited and covers
only StockTwits users (a retail-trader-skewed sample). Treat as a directional
signal, not ground truth. If you later add a paid source (e.g. a sentiment
vendor), swap it in here behind the same interface.
"""
import aiohttp
import logging
from cache.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)

TTL_SOCIAL = 300
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


async def fetch_social_sentiment(symbol: str) -> dict:
    """
    StockTwits sentiment for a symbol: counts of bullish/bearish tagged messages
    in the recent stream, plus the most recent messages.
    """
    cache_key = f"social:{symbol.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol.upper()}.json"
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return {"symbol": symbol.upper(), "available": False,
                            "reason": f"StockTwits returned {r.status}",
                            "note": "Social sentiment is best-effort; source may be rate-limited."}
                data = await r.json(content_type=None)
    except Exception as e:
        logger.warning(f"[Social] {symbol}: {e}")
        return {"symbol": symbol.upper(), "available": False, "reason": str(e),
                "note": "Social sentiment is best-effort and may be unavailable."}

    messages = data.get("messages", [])
    bullish = bearish = neutral = 0
    recent = []
    for m in messages:
        sentiment = (m.get("entities", {}) or {}).get("sentiment") or {}
        basic = sentiment.get("basic") if sentiment else None
        if basic == "Bullish":   bullish += 1
        elif basic == "Bearish": bearish += 1
        else:                    neutral += 1
        if len(recent) < 15:
            recent.append({
                "body":      (m.get("body") or "")[:200],
                "sentiment": basic,
                "created":   m.get("created_at"),
                "user":      (m.get("user") or {}).get("username"),
            })

    total_tagged = bullish + bearish
    bull_pct = round(bullish / total_tagged * 100, 1) if total_tagged else None

    result = {
        "symbol":        symbol.upper(),
        "available":     True,
        "source":        "StockTwits",
        "message_count": len(messages),
        "bullish":       bullish,
        "bearish":       bearish,
        "neutral":       neutral,
        "bullish_pct":   bull_pct,
        "net_sentiment": ("bullish" if bull_pct and bull_pct > 60 else
                          "bearish" if bull_pct and bull_pct < 40 else "mixed"),
        "recent":        recent,
        "note":          "Retail-skewed sample from StockTwits; directional only.",
    }
    await cache_set(cache_key, result, TTL_SOCIAL)
    return result
