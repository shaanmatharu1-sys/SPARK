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


async def fetch_yield_curve_extended() -> dict:
    """
    Extended yield curve data: current curve + key spreads + inversion status
    + interpretation. Powers the dedicated Yield Curve tab.
    """
    cache_key = "fred:yield_curve_ext"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    curve = await fetch_yield_curve()  # current curve + 2s10s

    # Key spreads (recession indicators)
    spreads = {}
    if "10Y" in curve and "2Y" in curve:
        spreads["2s10s"] = round(curve["10Y"] - curve["2Y"], 3)
    if "10Y" in curve and "3M" in curve:
        spreads["3m10y"] = round(curve["10Y"] - curve["3M"], 3)
    if "30Y" in curve and "5Y" in curve:
        spreads["5s30s"] = round(curve["30Y"] - curve["5Y"], 3)

    # Inversion status
    inverted = [k for k, v in spreads.items() if v < 0]
    if "2s10s" in spreads and spreads["2s10s"] < 0:
        shape = "inverted"
        interp = ("The 2s10s spread is inverted (2Y yields more than 10Y). "
                  "Historically this has preceded recessions by 6-18 months, as it "
                  "signals the market expects the Fed to cut rates in the future.")
    elif "2s10s" in spreads and spreads["2s10s"] < 0.5:
        shape = "flat"
        interp = ("The curve is relatively flat. This often signals uncertainty about "
                  "the economic outlook or a transition between policy regimes.")
    else:
        shape = "normal"
        interp = ("The curve is upward-sloping (normal). Longer maturities yield more "
                  "than shorter ones, consistent with expectations of stable or growing "
                  "economic activity.")

    result = {
        "curve":      {k: v for k, v in curve.items() if k not in ("2s10s",)},
        "spreads":    spreads,
        "inverted_spreads": inverted,
        "shape":      shape,
        "interpretation": interp,
    }
    await cache_set(cache_key, result, TTL_MACRO)
    return result


# Credit market series (FRED, free)
CREDIT_SERIES = {
    "BAMLH0A0HYM2":    "HY OAS",          # ICE BofA US High Yield OAS
    "BAMLC0A0CM":      "IG OAS",          # ICE BofA US Corporate (IG) OAS
    "BAMLH0A0HYM2EY":  "HY Effective Yield",
    "BAMLC0A0CMEY":    "IG Effective Yield",
    "TEDRATE":         "TED Spread",
    "T10Y2Y":          "2s10s",
}


async def fetch_credit_dashboard() -> dict:
    """
    Credit market dashboard: IG/HY spreads (OAS) + levels + recession signal +
    credit-vs-equity risk-on/off read. All from FRED (free).
    """
    cache_key = "fred:credit"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async def latest(series_id):
        obs = await fetch_series(series_id, limit=60)
        vals = [o for o in obs if o.get("value") is not None]
        return vals

    hy = await latest("BAMLH0A0HYM2")     # HY OAS, in percent
    ig = await latest("BAMLC0A0CM")       # IG OAS, in percent

    def level_and_change(vals):
        if not vals:
            return None, None, []
        cur = vals[-1]["value"]
        # ~21 trading days ago for 1mo change
        prior = vals[-22]["value"] if len(vals) >= 22 else vals[0]["value"]
        return cur, round(cur - prior, 3), [
            {"date": v["date"], "value": v["value"]} for v in vals[-60:]
        ]

    hy_oas, hy_chg, hy_hist = level_and_change(hy)
    ig_oas, ig_chg, ig_hist = level_and_change(ig)

    # Recession signal heuristics on HY OAS
    # HY OAS > ~5.5% historically signals stress; > 8% serious stress.
    signal = "calm"
    if hy_oas is not None:
        if hy_oas > 8.0:   signal = "stress"
        elif hy_oas > 5.5: signal = "elevated"
        elif hy_oas > 4.0: signal = "watch"

    # Credit vs equity divergence read:
    # widening credit spreads while equities hold up = risk-off warning
    divergence = None
    if hy_chg is not None:
        if hy_chg > 0.3:
            divergence = "credit_widening"   # credit getting nervous
        elif hy_chg < -0.3:
            divergence = "credit_tightening"  # risk-on
        else:
            divergence = "stable"

    result = {
        "hy_oas":      hy_oas,
        "hy_change":   hy_chg,
        "ig_oas":      ig_oas,
        "ig_change":   ig_chg,
        "hy_ig_ratio": round(hy_oas / ig_oas, 2) if (hy_oas and ig_oas) else None,
        "signal":      signal,
        "divergence":  divergence,
        "hy_history":  hy_hist,
        "ig_history":  ig_hist,
        "interpretation": _credit_interp(signal, divergence, hy_oas),
    }
    await cache_set(cache_key, result, TTL_MACRO)
    return result


def _credit_interp(signal, divergence, hy_oas):
    parts = []
    if signal == "stress":
        parts.append("High-yield spreads are at stressed levels, historically associated "
                     "with recessions or financial crises.")
    elif signal == "elevated":
        parts.append("High-yield spreads are elevated, signaling rising credit risk and "
                     "tighter financial conditions.")
    elif signal == "watch":
        parts.append("Credit spreads are modestly above their calm range, worth watching.")
    else:
        parts.append("Credit spreads are in a calm range, consistent with risk-on conditions.")

    if divergence == "credit_widening":
        parts.append("Spreads have widened recently; if equities remain elevated, this "
                     "credit-equity divergence is a classic risk-off warning, since credit "
                     "markets often lead equities at turning points.")
    elif divergence == "credit_tightening":
        parts.append("Spreads are tightening, a risk-on signal that credit markets are "
                     "growing more comfortable.")
    return " ".join(parts)
