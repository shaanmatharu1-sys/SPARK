"""
services/futures_client.py

Futures market data — free/delayed, since no futures product is enabled on
this app's Polygon key and CFTC has no live-quote API at all:
  - Continuous front-month contract quotes + price history via yfinance
    (same "=F" tickers Yahoo Finance uses; identical async-wrapping pattern
    to services/international_client.py's fetch_world_indices).
  - Positioning depth (Non-Commercial/Commercial/Non-Reportable net
    positions) via CFTC's free weekly Commitment of Traders report —
    see services/cftc_client.py.
"""
import asyncio
import datetime
import logging

logger = logging.getLogger(__name__)

from cache.redis_client import cache_get, cache_set
from config import TTL_FUTURES

FUTURES = {
    "ES=F":  {"name": "S&P 500 E-mini",     "group": "Equity Index"},
    "NQ=F":  {"name": "Nasdaq 100 E-mini",   "group": "Equity Index"},
    "YM=F":  {"name": "Dow E-mini",          "group": "Equity Index"},
    "RTY=F": {"name": "Russell 2000 E-mini","group": "Equity Index"},
    "CL=F":  {"name": "WTI Crude Oil",       "group": "Energy"},
    "NG=F":  {"name": "Natural Gas",         "group": "Energy"},
    "GC=F":  {"name": "Gold",                "group": "Metals"},
    "SI=F":  {"name": "Silver",              "group": "Metals"},
    "HG=F":  {"name": "Copper",              "group": "Metals"},
    "ZN=F":  {"name": "10Y T-Note",          "group": "Rates"},
    "ZB=F":  {"name": "30Y T-Bond",          "group": "Rates"},
    "ZC=F":  {"name": "Corn",                "group": "Agriculture"},
    "ZS=F":  {"name": "Soybeans",            "group": "Agriculture"},
    "ZW=F":  {"name": "Wheat",               "group": "Agriculture"},
    "6E=F":  {"name": "Euro FX",             "group": "Currency"},
    "6J=F":  {"name": "Japanese Yen",        "group": "Currency"},
}


def _pct(cur, prev):
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / prev * 100, 2)


async def fetch_futures_quotes():
    """Front-month continuous contract quotes via yfinance (blocking call, threaded)."""
    cache_key = "futures:quotes"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    def _blocking():
        try:
            import yfinance as yf
        except ImportError:
            return {"available": False, "reason": "yfinance not installed"}
        symbols = list(FUTURES.keys())
        out = []
        try:
            data = yf.download(symbols, period="5d", interval="1d",
                               group_by="ticker", progress=False, threads=True)
        except Exception as e:
            return {"available": False, "reason": f"yfinance error: {str(e)[:120]}"}
        for sym in symbols:
            try:
                df = data[sym] if len(symbols) > 1 else data
                closes = df["Close"].dropna()
                if len(closes) < 2:
                    continue
                cur, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                meta = FUTURES[sym]
                out.append({
                    "symbol": sym, "name": meta["name"], "group": meta["group"],
                    "price": round(cur, 3), "change_pct": _pct(cur, prev),
                })
            except Exception:
                continue
        return {"available": True, "quotes": out,
                "as_of": datetime.datetime.utcnow().isoformat()}

    result = await asyncio.to_thread(_blocking)
    if result.get("available"):
        await cache_set(cache_key, result, ttl=TTL_FUTURES)
    return result


async def fetch_futures_bars(symbol: str, days: int = 90):
    """
    Daily price history for one contract's drill-down chart. Polygon doesn't
    cover "=F" continuous contracts, so this goes through yfinance directly
    rather than services/polygon_client.py's bars endpoint.
    """
    symbol = symbol.upper()
    if symbol not in FUTURES:
        return {"error": f"{symbol} not a covered futures contract",
                "covered": list(FUTURES.keys())}

    cache_key = f"futures:bars:{symbol}:{days}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    def _blocking():
        try:
            import yfinance as yf
        except ImportError:
            return {"available": False, "reason": "yfinance not installed"}
        try:
            hist = yf.Ticker(symbol).history(period=f"{days}d", interval="1d")
        except Exception as e:
            return {"available": False, "reason": f"yfinance error: {str(e)[:120]}"}
        bars = []
        for ts, row in hist.iterrows():
            if row.get("Close") != row.get("Close"):  # NaN
                continue
            bars.append({"t": int(ts.timestamp() * 1000), "c": round(float(row["Close"]), 4)})
        return {"available": True, "symbol": symbol, "bars": bars}

    result = await asyncio.to_thread(_blocking)
    if result.get("available"):
        await cache_set(cache_key, result, ttl=TTL_FUTURES * 5)
    return result


async def fetch_futures_all():
    return await fetch_futures_quotes()
