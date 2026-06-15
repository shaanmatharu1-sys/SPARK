"""
services/international_client.py

Global markets data:
  - Native index levels via yfinance (Nikkei, FTSE, DAX, Hang Seng, ...)
    yfinance scrapes Yahoo's unofficial API — free, global coverage, but can be
    rate-limited. Fails gracefully if unavailable.
  - Country/region ETFs, ADRs via Polygon (US-listed, already-wired).
  - FX rates via Polygon FX (or FRED fallback).
"""
import asyncio
import logging
import datetime

logger = logging.getLogger(__name__)

from cache.redis_client import cache_get, cache_set
from services.polygon_client import fetch_snapshot, fetch_fx_snapshot

# ── Native indices (yfinance symbols) ──
WORLD_INDICES = {
    "^GSPC":  {"name": "S&P 500",        "region": "Americas",  "country": "US"},
    "^IXIC":  {"name": "Nasdaq",         "region": "Americas",  "country": "US"},
    "^DJI":   {"name": "Dow Jones",      "region": "Americas",  "country": "US"},
    "^GSPTSE":{"name": "TSX",            "region": "Americas",  "country": "Canada"},
    "^BVSP":  {"name": "Bovespa",        "region": "Americas",  "country": "Brazil"},
    "^FTSE":  {"name": "FTSE 100",       "region": "Europe",    "country": "UK"},
    "^GDAXI": {"name": "DAX",            "region": "Europe",    "country": "Germany"},
    "^FCHI":  {"name": "CAC 40",         "region": "Europe",    "country": "France"},
    "^STOXX50E":{"name": "Euro Stoxx 50","region": "Europe",    "country": "Eurozone"},
    "^IBEX":  {"name": "IBEX 35",        "region": "Europe",    "country": "Spain"},
    "^N225":  {"name": "Nikkei 225",     "region": "Asia",      "country": "Japan"},
    "^HSI":   {"name": "Hang Seng",      "region": "Asia",      "country": "Hong Kong"},
    "000001.SS":{"name":"Shanghai Comp", "region": "Asia",      "country": "China"},
    "^KS11":  {"name": "KOSPI",          "region": "Asia",      "country": "Korea"},
    "^TWII":  {"name": "Taiwan Weighted","region": "Asia",      "country": "Taiwan"},
    "^BSESN": {"name": "Sensex",         "region": "Asia",      "country": "India"},
    "^AXJO":  {"name": "ASX 200",        "region": "Asia",      "country": "Australia"},
}

# ── Country/region ETFs (Polygon, US-listed) ──
COUNTRY_ETFS = {
    "EWJ":  {"name": "Japan",            "region": "Asia"},
    "MCHI": {"name": "China",            "region": "Asia"},
    "FXI":  {"name": "China Large-Cap",  "region": "Asia"},
    "EWY":  {"name": "South Korea",      "region": "Asia"},
    "EWT":  {"name": "Taiwan",           "region": "Asia"},
    "INDA": {"name": "India",            "region": "Asia"},
    "EWA":  {"name": "Australia",        "region": "Asia"},
    "EWU":  {"name": "United Kingdom",   "region": "Europe"},
    "EWG":  {"name": "Germany",          "region": "Europe"},
    "EWQ":  {"name": "France",           "region": "Europe"},
    "EWL":  {"name": "Switzerland",      "region": "Europe"},
    "EWP":  {"name": "Spain",            "region": "Europe"},
    "EWI":  {"name": "Italy",            "region": "Europe"},
    "EWC":  {"name": "Canada",           "region": "Americas"},
    "EWZ":  {"name": "Brazil",           "region": "Americas"},
    "EWW":  {"name": "Mexico",           "region": "Americas"},
    "EFA":  {"name": "Developed ex-US",  "region": "Broad"},
    "VWO":  {"name": "Emerging Markets", "region": "Broad"},
    "ACWX": {"name": "All-World ex-US",  "region": "Broad"},
}

# ── Major ADRs (Polygon, US-listed foreign companies) ──
ADRS = {
    "TSM":  {"name": "Taiwan Semiconductor", "country": "Taiwan"},
    "ASML": {"name": "ASML Holding",         "country": "Netherlands"},
    "BABA": {"name": "Alibaba",              "country": "China"},
    "TM":   {"name": "Toyota Motor",         "country": "Japan"},
    "SAP":  {"name": "SAP SE",               "country": "Germany"},
    "NVO":  {"name": "Novo Nordisk",         "country": "Denmark"},
    "SHEL": {"name": "Shell",                "country": "UK"},
    "BP":   {"name": "BP",                   "country": "UK"},
    "HSBC": {"name": "HSBC Holdings",        "country": "UK"},
    "SONY": {"name": "Sony Group",           "country": "Japan"},
    "UL":   {"name": "Unilever",             "country": "UK"},
    "RIO":  {"name": "Rio Tinto",            "country": "Australia"},
    "TD":   {"name": "Toronto-Dominion",     "country": "Canada"},
    "PDD":  {"name": "PDD Holdings",         "country": "China"},
    "MUFG": {"name": "Mitsubishi UFJ",       "country": "Japan"},
    "INFY": {"name": "Infosys",              "country": "India"},
}

# ── FX pairs (Polygon FX uses C:EURUSD style) ──
FX_PAIRS = {
    "C:EURUSD": "EUR/USD",
    "C:USDJPY": "USD/JPY",
    "C:GBPUSD": "GBP/USD",
    "C:USDCNH": "USD/CNH",
    "C:USDCAD": "USD/CAD",
    "C:AUDUSD": "AUD/USD",
    "C:USDCHF": "USD/CHF",
    "C:USDKRW": "USD/KRW",
}


def _pct(cur, prev):
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / prev * 100, 2)


async def fetch_world_indices():
    """Native index levels via yfinance. Runs blocking yfinance in a thread."""
    cache_key = "intl:indices"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    def _blocking():
        try:
            import yfinance as yf
        except ImportError:
            return {"available": False, "reason": "yfinance not installed"}
        out = []
        symbols = list(WORLD_INDICES.keys())
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
                meta = WORLD_INDICES[sym]
                out.append({
                    "symbol": sym, "name": meta["name"], "region": meta["region"],
                    "country": meta["country"], "level": round(cur, 2),
                    "change_pct": _pct(cur, prev),
                })
            except Exception:
                continue
        return {"available": True, "indices": out,
                "as_of": datetime.datetime.utcnow().isoformat()}

    result = await asyncio.to_thread(_blocking)
    if result.get("available"):
        await cache_set(cache_key, result, ttl=300)  # 5 min
    return result


async def _etf_perf(mapping, label):
    """Generic snapshot-based performance for a set of US-listed symbols."""
    symbols = list(mapping.keys())
    snap = await fetch_snapshot(symbols)
    rows = []
    for sym in symbols:
        d = snap.get(sym, {})
        day = d.get("day", {}) or {}
        prev = d.get("prevDay", {}) or {}
        last = (d.get("lastTrade", {}) or {}).get("p") or day.get("c") or prev.get("c")
        pchg = d.get("todaysChangePerc")
        if pchg is None:
            pchg = _pct(last, prev.get("c"))
        rows.append({
            "symbol": sym, **mapping[sym],
            "price": round(last, 2) if last else None,
            "change_pct": round(pchg, 2) if pchg is not None else None,
        })
    return rows


async def fetch_country_etfs():
    cache_key = "intl:etfs"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    rows = await _etf_perf(COUNTRY_ETFS, "etf")
    out = {"etfs": rows, "as_of": datetime.datetime.utcnow().isoformat()}
    await cache_set(cache_key, out, ttl=60)
    return out


async def fetch_adrs():
    cache_key = "intl:adrs"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    rows = await _etf_perf(ADRS, "adr")
    out = {"adrs": rows, "as_of": datetime.datetime.utcnow().isoformat()}
    await cache_set(cache_key, out, ttl=60)
    return out


async def fetch_fx():
    """FX rates via Polygon FX snapshot."""
    cache_key = "intl:fx"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    symbols = list(FX_PAIRS.keys())
    snap = await fetch_fx_snapshot(symbols)
    rows = []
    for sym in symbols:
        d = snap.get(sym, {})
        day = d.get("day", {}) or {}
        prev = d.get("prevDay", {}) or {}
        last = (d.get("lastTrade", {}) or {}).get("p") or day.get("c") or prev.get("c")
        pchg = d.get("todaysChangePerc")
        if pchg is None:
            pchg = _pct(last, prev.get("c"))
        rows.append({
            "pair": FX_PAIRS[sym], "symbol": sym,
            "rate": round(last, 4) if last else None,
            "change_pct": round(pchg, 2) if pchg is not None else None,
        })
    out = {"fx": rows, "as_of": datetime.datetime.utcnow().isoformat()}
    await cache_set(cache_key, out, ttl=60)
    return out


async def fetch_international_all():
    """Everything for the international tab in one call."""
    indices, etfs, adrs, fx = await asyncio.gather(
        fetch_world_indices(), fetch_country_etfs(), fetch_adrs(), fetch_fx(),
        return_exceptions=True,
    )
    def safe(x, key):
        return x if not isinstance(x, Exception) else {"available": False, "reason": str(x)[:100], key: []}
    return {
        "indices": safe(indices, "indices"),
        "etfs":    safe(etfs, "etfs"),
        "adrs":    safe(adrs, "adrs"),
        "fx":      safe(fx, "fx"),
    }
