"""
services/fred_client.py — FRED (St. Louis Fed) data client
Fetches: yield curve, CPI, unemployment, Fed funds, M2, GDP, VIX, etc.
"""
import asyncio
import logging
from datetime import date, timedelta
import aiohttp
from config import FRED_API_KEY, FRED_SERIES, TTL_MACRO
from cache.redis_client import cache_set, cache_get

logger = logging.getLogger(__name__)
FRED_BASE = "https://api.stlouisfed.org/fred"


async def _fred_get(session: aiohttp.ClientSession, endpoint: str, params: dict) -> dict | None:
    params["api_key"]       = FRED_API_KEY
    params["file_type"]     = "json"
    try:
        async with session.get(f"{FRED_BASE}{endpoint}", params=params,
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                return await r.json()
            body = await r.text()
            logger.warning(f"[FRED] {endpoint} → {r.status}: {body[:200]}")
            return None
    except Exception as e:
        logger.error(f"[FRED] {endpoint} error: {e}")
        return None


async def fetch_series(series_id: str, limit: int = 10) -> list[dict]:
    """Fetch the N most recent observations for a FRED series."""
    cache_key = f"fred:{series_id}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async with aiohttp.ClientSession() as session:
        data = await _fred_get(session, "/series/observations", {
            "series_id": series_id,
            "sort_order": "desc",
            "limit": limit,
            "observation_end": date.today().isoformat(),
        })

    if not data:
        return []

    obs = [
        {"date": o["date"], "value": float(o["value"]) if o["value"] != "." else None}
        for o in data.get("observations", [])
        if o.get("value") not in (".", None)
    ]
    await cache_set(cache_key, obs, TTL_MACRO)
    return obs


async def fetch_yield_curve() -> dict:
    """Fetch the full Treasury yield curve — all maturities."""
    cache_key = "fred:yield_curve"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    YIELD_SERIES = {
        "DGS1MO": "1M", "DGS3MO": "3M", "DGS6MO": "6M",
        "DGS1":   "1Y", "DGS2":   "2Y", "DGS3":   "3Y",
        "DGS5":   "5Y", "DGS7":   "7Y", "DGS10":  "10Y",
        "DGS20":  "20Y","DGS30":  "30Y",
    }

    async with aiohttp.ClientSession() as session:
        tasks = [
            _fred_get(session, "/series/observations", {
                "series_id":   sid,
                "sort_order":  "desc",
                "limit":       1,
            })
            for sid in YIELD_SERIES
        ]
        results = await asyncio.gather(*tasks)

    curve = {}
    for (sid, label), data in zip(YIELD_SERIES.items(), results):
        if data and data.get("observations"):
            obs = data["observations"][0]
            if obs["value"] != ".":
                curve[label] = float(obs["value"])

    # Compute 2s10s spread (key recession indicator)
    if "2Y" in curve and "10Y" in curve:
        curve["2s10s"] = round(curve["10Y"] - curve["2Y"], 3)

    await cache_set(cache_key, curve, TTL_MACRO)
    return curve


async def fetch_macro_dashboard() -> dict:
    """Fetch all key macro indicators for the dashboard panel."""
    cache_key = "fred:macro_dashboard"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    INDICATORS = {
        "FEDFUNDS":   "Fed Funds Rate",
        "CPIAUCSL":   "CPI YoY",
        "UNRATE":     "Unemployment Rate",
        "T10YIE":     "10Y Breakeven Inflation",
        "VIXCLS":     "VIX",
        "DCOILWTICO": "WTI Crude",
        "DEXUSEU":    "EUR/USD",
        "GDP":        "GDP (QoQ SAAR)",
        "M2SL":       "M2 Money Supply",
        "T10Y2Y":     "10Y-2Y Spread",
    }

    async with aiohttp.ClientSession() as session:
        tasks = [
            _fred_get(session, "/series/observations", {
                "series_id": sid, "sort_order": "desc", "limit": 2
            })
            for sid in INDICATORS
        ]
        results = await asyncio.gather(*tasks)

    dashboard = {}
    for (sid, name), data in zip(INDICATORS.items(), results):
        if data and data.get("observations"):
            obs_list = [o for o in data["observations"] if o["value"] != "."]
            if obs_list:
                current = float(obs_list[0]["value"])
                prev    = float(obs_list[1]["value"]) if len(obs_list) > 1 else None
                change  = round(current - prev, 4) if prev is not None else None
                dashboard[sid] = {
                    "name":    name,
                    "value":   current,
                    "prev":    prev,
                    "change":  change,
                    "date":    obs_list[0]["date"],
                }

    await cache_set(cache_key, dashboard, TTL_MACRO)
    return dashboard


async def fetch_series_history(series_id: str, years: int = 5) -> list[dict]:
    """Fetch multi-year history for a series (for charting)."""
    from_date = (date.today() - timedelta(days=365 * years)).isoformat()
    cache_key = f"fred:history:{series_id}:{years}y"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async with aiohttp.ClientSession() as session:
        data = await _fred_get(session, "/series/observations", {
            "series_id":        series_id,
            "sort_order":       "asc",
            "observation_start": from_date,
        })

    if not data:
        return []

    obs = [
        {"date": o["date"], "value": float(o["value"])}
        for o in data.get("observations", [])
        if o.get("value") not in (".", None)
    ]
    await cache_set(cache_key, obs, TTL_MACRO)
    return obs
