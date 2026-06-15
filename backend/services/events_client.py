"""
services/events_client.py

Economic & market events calendar:
  - Economic releases (CPI, FOMC, jobs, GDP...) via FRED release-dates endpoint.
    Using official release schedules rather than scraping a calendar site.
  - Earnings dates via Polygon (best-effort).

Forward economic calendars are hard to get free; FRED's release-dates endpoint
gives official upcoming publication dates for major series, which is the most
reliable free approach.
"""
import asyncio
import logging
import datetime

logger = logging.getLogger(__name__)

import aiohttp
from config import FRED_API_KEY
from cache.redis_client import cache_get, cache_set

FRED_BASE = "https://api.stlouisfed.org/fred"

# Major FRED releases to track (release_id -> friendly name + importance)
# release_ids are stable FRED identifiers for these publications.
KEY_RELEASES = {
    10:  {"name": "Consumer Price Index (CPI)",        "importance": "high"},
    50:  {"name": "Employment Situation (Jobs Report)", "importance": "high"},
    53:  {"name": "Gross Domestic Product (GDP)",       "importance": "high"},
    21:  {"name": "FOMC Press Release / Rate Decision",  "importance": "high"},
    13:  {"name": "Personal Income & Outlays (PCE)",    "importance": "high"},
    46:  {"name": "Producer Price Index (PPI)",         "importance": "med"},
    175: {"name": "Retail Sales",                       "importance": "med"},
    97:  {"name": "Industrial Production",              "importance": "med"},
    9:   {"name": "Consumer Sentiment (UMich)",         "importance": "med"},
}


async def _fred_get(session, endpoint, params):
    params["api_key"] = FRED_API_KEY
    params["file_type"] = "json"
    try:
        async with session.get(f"{FRED_BASE}{endpoint}", params=params,
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                return await r.json()
            return None
    except Exception as e:
        logger.error(f"[Events] {endpoint} error: {e}")
        return None


async def fetch_economic_calendar(days_ahead: int = 30):
    """Upcoming economic releases from FRED release-dates."""
    cache_key = "events:econ"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    today = datetime.date.today()
    end = today + datetime.timedelta(days=days_ahead)
    start = today - datetime.timedelta(days=2)

    events = []
    async with aiohttp.ClientSession() as session:
        async def one(rid, meta):
            data = await _fred_get(session, f"/release/dates", {
                "release_id": rid,
                "realtime_start": start.isoformat(),
                "realtime_end": end.isoformat(),
                "include_release_dates_with_no_data": "true",
                "sort_order": "asc",
            })
            out = []
            if data and "release_dates" in data:
                for rd in data["release_dates"]:
                    d = rd.get("date")
                    if d and start.isoformat() <= d <= end.isoformat():
                        out.append({"date": d, "name": meta["name"],
                                    "importance": meta["importance"], "type": "economic"})
            return out
        results = await asyncio.gather(*[one(rid, m) for rid, m in KEY_RELEASES.items()])
        for r in results:
            events.extend(r)

    events.sort(key=lambda e: e["date"])
    out = {"events": events, "as_of": datetime.datetime.utcnow().isoformat(),
           "available": len(events) > 0}
    if events:
        await cache_set(cache_key, out, ttl=21600)  # 6h
    return out


async def fetch_earnings_calendar(symbols: list[str]):
    """
    Upcoming earnings dates for watchlist symbols (best-effort via Polygon).
    Polygon's free tier earnings coverage is limited; fails gracefully.
    """
    cache_key = "events:earnings:" + ",".join(sorted(symbols))
    cached = await cache_get(cache_key)
    if cached:
        return cached

    from services.polygon_client import fetch_earnings
    rows = []
    for sym in symbols[:20]:
        try:
            e = await fetch_earnings(sym)
            if e and e.get("date"):
                rows.append({"date": e["date"], "name": f"{sym} earnings",
                             "symbol": sym, "type": "earnings", "importance": "med"})
        except Exception:
            continue
    out = {"earnings": rows, "available": len(rows) > 0,
           "as_of": datetime.datetime.utcnow().isoformat()}
    if rows:
        await cache_set(cache_key, out, ttl=21600)
    return out


async def fetch_events_all(watchlist=None):
    watchlist = watchlist or ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META"]
    econ, earnings = await asyncio.gather(
        fetch_economic_calendar(),
        fetch_earnings_calendar(watchlist),
        return_exceptions=True,
    )
    def safe(x, k):
        return x if not isinstance(x, Exception) else {"available": False, k: [], "reason": str(x)[:100]}
    return {"economic": safe(econ, "events"), "earnings": safe(earnings, "earnings")}
