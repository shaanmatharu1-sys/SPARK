"""
services/fear_greed.py — CNN Fear & Greed Index scraper
Source: https://production.dataviz.cnn.io/index/fearandgreed/graphdata
Returns current score + all 7 sub-indicators + 30-day history
"""
import aiohttp
import logging
from cache.redis_client import cache_set, cache_get
from config import TTL_FG

logger = logging.getLogger(__name__)

FG_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
}

RATING_MAP = {
    (0, 25):   "Extreme Fear",
    (25, 45):  "Fear",
    (45, 55):  "Neutral",
    (55, 75):  "Greed",
    (75, 100): "Extreme Greed",
}


def _classify(score: float) -> str:
    for (lo, hi), label in RATING_MAP.items():
        if lo <= score <= hi:
            return label
    return "Unknown"


async def fetch_fear_greed() -> dict:
    cached = await cache_get("fear_greed")
    if cached:
        return cached

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(FG_URL, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    logger.warning(f"[FearGreed] HTTP {r.status}")
                    return {}
                data = await r.json(content_type=None)
    except Exception as e:
        logger.error(f"[FearGreed] fetch error: {e}")
        return {}

    fg = data.get("fear_and_greed", {})
    history_raw = data.get("fear_and_greed_historical", {}).get("data", [])

    score = fg.get("score", 0)

    result = {
        "score":    round(score, 1),
        "rating":   fg.get("rating", _classify(score)),
        "timestamp": fg.get("timestamp"),
        # Sub-indicators
        "indicators": {
            "market_momentum":    data.get("market_momentum_sp500", {}).get("score"),
            "stock_strength":     data.get("stock_price_strength", {}).get("score"),
            "stock_breadth":      data.get("stock_price_breadth", {}).get("score"),
            "put_call":           data.get("put_call_options", {}).get("score"),
            "junk_bond_demand":   data.get("junk_bond_demand", {}).get("score"),
            "market_volatility":  data.get("market_volatility_vix", {}).get("score"),
            "safe_haven_demand":  data.get("safe_haven_demand", {}).get("score"),
        },
        # 30-day history for sparkline
        "history": [
            {"date": p.get("x"), "score": round(p.get("y", 0), 1)}
            for p in history_raw[-30:]
        ],
    }

    await cache_set("fear_greed", result, TTL_FG)
    return result
