"""
services/altdata_client.py

Alternative-data signals:
  - Google Trends search interest (pytrends; unofficial, rate-limited, cached hard)
  - Commodities & shipping/supply-chain indicators (FRED; official, keyed)
  - Social volume & sentiment (StockTwits; best-effort)

All sources fail gracefully — a dead source returns {available: False} rather
than crashing the tab. Sandbox blocks these hosts; they work from Railway.
"""
import asyncio
import logging
import datetime

logger = logging.getLogger(__name__)

from cache.redis_client import cache_get, cache_set
from services.fred_client import fetch_series_history

# ── Commodities & shipping/supply-chain (FRED series) ──
COMMODITY_SERIES = {
    "DCOILWTICO":  {"name": "WTI Crude Oil",        "unit": "$/bbl", "group": "Energy"},
    "DCOILBRENTEU":{"name": "Brent Crude Oil",      "unit": "$/bbl", "group": "Energy"},
    "DHHNGSP":     {"name": "Natural Gas (Henry Hub)","unit": "$/MMBtu","group": "Energy"},
    "GOLDAMGBD228NLBM": {"name": "Gold",            "unit": "$/oz",  "group": "Metals"},
    "PCOPPUSDM":   {"name": "Copper (Global)",      "unit": "$/mt",  "group": "Metals"},
    "PWHEAMTUSDM": {"name": "Wheat (Global)",       "unit": "$/mt",  "group": "Agriculture"},
}
SHIPPING_SERIES = {
    "GSCPI":       {"name": "Global Supply Chain Pressure Index", "unit": "std dev", "group": "Supply Chain"},
    # Note: some shipping/freight series have restricted FRED availability; GSCPI is the
    # reliable headline supply-chain stress measure (NY Fed).
}


async def fetch_trends(keywords: list[str]):
    """
    Google Trends interest-over-time for given keywords (last 90 days).
    pytrends is unofficial and rate-limits hard, so cache aggressively (6h).
    """
    kw_key = ",".join(sorted(keywords))
    cache_key = f"altdata:trends:{kw_key}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    def _blocking():
        try:
            from pytrends.request import TrendReq
        except ImportError:
            return {"available": False, "reason": "pytrends not installed"}
        try:
            py = TrendReq(hl="en-US", tz=300)
            py.build_payload(keywords[:5], timeframe="today 3-m")
            df = py.interest_over_time()
            if df.empty:
                return {"available": False, "reason": "no trends data returned"}
            series = []
            for kw in keywords[:5]:
                if kw in df.columns:
                    pts = [{"date": d.strftime("%Y-%m-%d"), "value": int(v)}
                           for d, v in df[kw].items()]
                    latest = pts[-1]["value"] if pts else 0
                    prior = pts[-8]["value"] if len(pts) >= 8 else (pts[0]["value"] if pts else 0)
                    series.append({
                        "keyword": kw, "points": pts,
                        "latest": latest,
                        "change_7": latest - prior,
                    })
            return {"available": True, "series": series,
                    "as_of": datetime.datetime.utcnow().isoformat()}
        except Exception as e:
            return {"available": False, "reason": f"trends error: {str(e)[:120]}"}

    result = await asyncio.to_thread(_blocking)
    if result.get("available"):
        await cache_set(cache_key, result, ttl=21600)  # 6h
    return result


async def fetch_commodities():
    """Commodity prices + shipping/supply-chain stress from FRED."""
    cache_key = "altdata:commodities"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async def one(sid, meta):
        hist = await fetch_series_history(sid, years=1)
        vals = [h for h in hist if h.get("value") is not None]
        if not vals:
            return None
        cur = vals[-1]["value"]
        prev = vals[-2]["value"] if len(vals) >= 2 else cur
        mo_ago = vals[-22]["value"] if len(vals) >= 22 else vals[0]["value"]
        spark = [v["value"] for v in vals[-60:]]
        return {
            "id": sid, **meta,
            "value": round(cur, 2),
            "change_1d": round(cur - prev, 3),
            "change_1mo_pct": round((cur - mo_ago) / mo_ago * 100, 2) if mo_ago else None,
            "spark": spark,
        }

    all_series = {**COMMODITY_SERIES, **SHIPPING_SERIES}
    results = await asyncio.gather(*[one(sid, m) for sid, m in all_series.items()])
    rows = [r for r in results if r]
    out = {"commodities": [r for r in rows if r["group"] != "Supply Chain"],
           "shipping":    [r for r in rows if r["group"] == "Supply Chain"],
           "as_of": datetime.datetime.utcnow().isoformat()}
    await cache_set(cache_key, out, ttl=3600)
    return out


async def fetch_social_volume(symbols: list[str]):
    """Social message volume + sentiment via StockTwits (best-effort)."""
    cache_key = "altdata:social:" + ",".join(sorted(symbols))
    cached = await cache_get(cache_key)
    if cached:
        return cached

    import aiohttp
    rows = []
    async with aiohttp.ClientSession() as session:
        for sym in symbols[:12]:
            try:
                url = f"https://api.stocktwits.com/api/2/streams/symbol/{sym}.json"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8),
                                       headers={"User-Agent": "Mozilla/5.0"}) as r:
                    if r.status != 200:
                        continue
                    data = await r.json()
                    msgs = data.get("messages", [])
                    bull = bear = 0
                    for m in msgs:
                        s = (m.get("entities", {}) or {}).get("sentiment") or {}
                        b = s.get("basic")
                        if b == "Bullish": bull += 1
                        elif b == "Bearish": bear += 1
                    total_sent = bull + bear
                    rows.append({
                        "symbol": sym,
                        "volume": len(msgs),
                        "bullish": bull, "bearish": bear,
                        "sentiment": round((bull - bear) / total_sent, 2) if total_sent else None,
                    })
            except Exception:
                continue
    out = {"social": rows, "available": len(rows) > 0,
           "as_of": datetime.datetime.utcnow().isoformat()}
    if rows:
        await cache_set(cache_key, out, ttl=300)
    return out


async def fetch_altdata_all(trend_keywords=None, social_symbols=None):
    trend_keywords = trend_keywords or ["recession", "buy stocks", "inflation", "layoffs"]
    social_symbols = social_symbols or ["AAPL", "TSLA", "NVDA", "SPY", "GME", "AMC"]
    trends, commodities, social = await asyncio.gather(
        fetch_trends(trend_keywords),
        fetch_commodities(),
        fetch_social_volume(social_symbols),
        return_exceptions=True,
    )
    def safe(x):
        return x if not isinstance(x, Exception) else {"available": False, "reason": str(x)[:100]}
    return {"trends": safe(trends), "commodities": safe(commodities), "social": safe(social)}
