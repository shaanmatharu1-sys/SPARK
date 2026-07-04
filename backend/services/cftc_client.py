"""
services/cftc_client.py

CFTC Commitment of Traders (COT) — free, no API key, published weekly
(as-of Tuesday, released the following Friday). Socrata public API
(publicreporting.cftc.gov), dataset 6dca-aqww ("Futures Only" combined
report). Gives positioning depth (net long/short by trader category) that
a bare price quote can't — this is the "depth" layered on top of
futures_client.py's yfinance quotes.

CFTC's contract names don't match ticker symbols, so this dict maps our
=F tickers to CFTC's market_and_exchange_names (verified against live data;
each maps to the most liquid/primary contract by open interest, not just
the first text match, since many symbols have multiple similarly-named
but far-less-liquid variants — e.g. "MICRO E-MINI NASDAQ-100" vs the
primary "NASDAQ-100 STOCK INDEX (MINI)").
"""
import asyncio
import logging
import urllib.parse

logger = logging.getLogger(__name__)

import aiohttp

from cache.redis_client import cache_get, cache_set
from config import TTL_COT

CFTC_BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

CFTC_CONTRACT_NAMES = {
    "ES=F":  "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
    "NQ=F":  "NASDAQ-100 STOCK INDEX (MINI) - CHICAGO MERCANTILE EXCHANGE",
    "YM=F":  "DJIA x $5 - CHICAGO BOARD OF TRADE",
    "RTY=F": "E-MINI RUSSELL 2000 INDEX - CHICAGO MERCANTILE EXCHANGE",
    "CL=F":  "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE",
    "NG=F":  "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE",
    "GC=F":  "GOLD - COMMODITY EXCHANGE INC.",
    "SI=F":  "SILVER - COMMODITY EXCHANGE INC.",
    "HG=F":  "COPPER-GRADE #1 - COMMODITY EXCHANGE INC.",
    "ZN=F":  "10-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE",
    "ZB=F":  "U.S. TREASURY BONDS - CHICAGO BOARD OF TRADE",
    "ZC=F":  "CORN - CHICAGO BOARD OF TRADE",
    "ZS=F":  "SOYBEANS - CHICAGO BOARD OF TRADE",
    "ZW=F":  "WHEAT - CHICAGO BOARD OF TRADE",
    "6E=F":  "EURO FX - CHICAGO MERCANTILE EXCHANGE",
    "6J=F":  "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",
}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


async def fetch_cot(symbol: str, weeks: int = 26):
    """
    Positioning trend for one contract: net Non-Commercial (speculators),
    Commercial (hedgers), and Non-Reportable positions over the last `weeks`
    reports, plus open interest.
    """
    symbol = symbol.upper()
    contract_name = CFTC_CONTRACT_NAMES.get(symbol)
    if not contract_name:
        return {"available": False, "reason": f"no CFTC mapping for {symbol}"}

    cache_key = f"cftc:cot:{symbol}:{weeks}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    params = {
        "$where": f"market_and_exchange_names = '{contract_name}'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": weeks,
    }
    url = f"{CFTC_BASE}?{urllib.parse.urlencode(params)}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return {"available": False, "reason": f"CFTC returned {r.status}"}
                rows = await r.json()
    except Exception as e:
        logger.warning(f"[CFTC] {symbol}: {e}")
        return {"available": False, "reason": str(e)[:120]}

    if not rows:
        return {"available": False, "reason": "no COT data found for this contract"}

    history = []
    for row in reversed(rows):  # oldest -> newest for charting
        noncomm_long = _int(row.get("noncomm_positions_long_all"))
        noncomm_short = _int(row.get("noncomm_positions_short_all"))
        comm_long = _int(row.get("comm_positions_long_all"))
        comm_short = _int(row.get("comm_positions_short_all"))
        nonrept_long = _int(row.get("nonrept_positions_long_all"))
        nonrept_short = _int(row.get("nonrept_positions_short_all"))
        history.append({
            "date": row.get("report_date_as_yyyy_mm_dd", "")[:10],
            "open_interest": _int(row.get("open_interest_all")),
            "noncomm_net": (noncomm_long or 0) - (noncomm_short or 0),
            "comm_net": (comm_long or 0) - (comm_short or 0),
            "nonrept_net": (nonrept_long or 0) - (nonrept_short or 0),
        })

    result = {
        "available": True, "symbol": symbol, "contract_name": contract_name,
        "history": history,
        "note": "CFTC Commitment of Traders, futures-only, updated weekly (as-of Tuesday, released Friday).",
    }
    await cache_set(cache_key, result, ttl=TTL_COT)
    return result
