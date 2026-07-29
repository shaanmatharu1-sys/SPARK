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

# yfinance intraday windows are capped by Yahoo itself regardless of what's
# asked for: 1m bars only go back 7 days, anything up to 90m only goes back 60.
_INTRADAY_MAX_DAYS = {1: 7, 5: 60, 15: 60, 30: 60, 60: 60, 90: 60}

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
            # Full OHLCV (yfinance actually carries all of it, not just Close)
            # so the frontend gets real candlesticks + volume, not just a
            # line-only series.
            bars.append({
                "t": int(ts.timestamp() * 1000),
                "o": round(float(row["Open"]), 4) if row.get("Open") == row.get("Open") else None,
                "h": round(float(row["High"]), 4) if row.get("High") == row.get("High") else None,
                "l": round(float(row["Low"]), 4) if row.get("Low") == row.get("Low") else None,
                "c": round(float(row["Close"]), 4),
                "v": float(row["Volume"]) if row.get("Volume") == row.get("Volume") else None,
            })
        return {"available": True, "symbol": symbol, "bars": bars}

    result = await asyncio.to_thread(_blocking)
    if result.get("available"):
        await cache_set(cache_key, result, ttl=TTL_FUTURES * 5)
    return result


async def fetch_futures_all():
    return await fetch_futures_quotes()


def resolve_futures_symbol(raw: str) -> str | None:
    """
    Accepts either the exact yfinance "=F" ticker or the bare root (e.g. "ES",
    "CL", "GC") someone would naturally type into the main symbol search —
    that search box has no idea futures use a different convention, so
    without this a typed "ES" just silently 404s against the equity feed.
    Returns None if it's not a covered contract either way.
    """
    s = (raw or "").upper().strip()
    if s in FUTURES:
        return s
    alt = f"{s}=F"
    if alt in FUTURES:
        return alt
    return None


async def fetch_futures_bars_chart(
    symbol: str, multiplier: int = 1, timespan: str = "minute",
    from_date: str = None, to_date: str = None, limit: int = 390,
):
    """
    Same OHLCV shape polygon_client.fetch_agg_bars returns (flat list of
    {t,o,h,l,c,v}, t in epoch ms) but sourced from yfinance — this is what
    lets the main chart's generic /quotes/{symbol}/bars call plot a futures
    contract via the exact same PriceChart code path an equity uses, instead
    of needing a separate chart just for futures.
    """
    symbol = symbol.upper()
    if symbol not in FUTURES:
        return []

    interval = {"minute": f"{multiplier}m", "day": "1d", "week": "1wk", "month": "1mo"}.get(timespan, "1d")
    today = datetime.date.today()
    if from_date:
        start = from_date
    elif timespan == "minute":
        cap = _INTRADAY_MAX_DAYS.get(multiplier, 60)
        start = (today - datetime.timedelta(days=cap)).isoformat()
    elif timespan == "week":
        start = (today - datetime.timedelta(days=limit * 7 + 7)).isoformat()
    elif timespan == "month":
        start = (today - datetime.timedelta(days=limit * 31 + 31)).isoformat()
    else:
        start = (today - datetime.timedelta(days=limit + 5)).isoformat()
    end = to_date or (today + datetime.timedelta(days=1)).isoformat()

    cache_key = f"futures:chartbars:{symbol}:{interval}:{start}:{end}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    def _blocking():
        try:
            import yfinance as yf
        except ImportError:
            return []
        try:
            hist = yf.Ticker(symbol).history(start=start, end=end, interval=interval)
        except Exception as e:
            logger.warning(f"[futures_client] yfinance chart fetch failed for {symbol}: {e}")
            return []
        bars = []
        for ts, row in hist.iterrows():
            if row.get("Close") != row.get("Close"):  # NaN
                continue
            bars.append({
                "t": int(ts.timestamp() * 1000),
                "o": round(float(row["Open"]), 4) if row.get("Open") == row.get("Open") else None,
                "h": round(float(row["High"]), 4) if row.get("High") == row.get("High") else None,
                "l": round(float(row["Low"]), 4) if row.get("Low") == row.get("Low") else None,
                "c": round(float(row["Close"]), 4),
                "v": float(row["Volume"]) if row.get("Volume") == row.get("Volume") else None,
            })
        return bars[-limit:] if limit else bars

    bars = await asyncio.to_thread(_blocking)
    if bars:
        await cache_set(cache_key, bars, ttl=TTL_FUTURES)
    return bars
