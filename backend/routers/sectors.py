"""
routers/sectors.py — Sector ETF performance + heatmap data
"""
from fastapi import APIRouter
from services.polygon_client import fetch_snapshot
from config import SECTOR_ETFS
from cache.redis_client import cache_set, cache_get
from config import TTL_SECTORS

router = APIRouter(prefix="/sectors", tags=["sectors"])

SECTOR_LABELS = {
    "XLF":  "Financials",
    "XLE":  "Energy",
    "XLK":  "Technology",
    "XLV":  "Health Care",
    "XLI":  "Industrials",
    "XLB":  "Materials",
    "XLU":  "Utilities",
    "XLRE": "Real Estate",
    "XLC":  "Comm Services",
    "XLP":  "Cons Staples",
    "XLY":  "Cons Discretionary",
}


@router.get("/")
async def get_sector_performance():
    """
    GET /sectors/ — Returns all sector ETF performance with % change,
    volume, and day range. Powers the sector heatmap.
    """
    cache_key = "sectors:performance"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    snapshots = await fetch_snapshot(SECTOR_ETFS)

    result = []
    for etf in SECTOR_ETFS:
        snap = snapshots.get(etf, {})
        day  = snap.get("day", {})
        prev = snap.get("prevDay", {})

        close_today = day.get("c") or snap.get("lastTrade", {}).get("p")
        close_prev  = prev.get("c")

        pct_change = None
        if close_today and close_prev and close_prev != 0:
            pct_change = round((close_today - close_prev) / close_prev * 100, 3)

        result.append({
            "symbol":     etf,
            "name":       SECTOR_LABELS.get(etf, etf),
            "price":      close_today,
            "prev_close": close_prev,
            "pct_change": pct_change,
            "volume":     day.get("v"),
            "high":       day.get("h"),
            "low":        day.get("l"),
        })

    # Sort by pct_change descending
    result.sort(key=lambda x: x["pct_change"] or 0, reverse=True)
    await cache_set(cache_key, result, TTL_SECTORS)
    return result
