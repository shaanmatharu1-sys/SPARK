"""
services/international_client.py

Global markets data:
  - Native index levels: EODHD real-time quotes (live, ~15-20min delayed)
    when EODHD_API_KEY is set, since Polygon/Finnhub here are US-only.
    Falls back to yfinance (Yahoo's unofficial API — free, but EOD-only and
    can be rate-limited) per-index for whatever EODHD doesn't cover.
  - Country/region ETFs, ADRs via Polygon (US-listed, already-wired).
  - FX rates via Polygon FX (or FRED fallback).
"""
import asyncio
import logging
import datetime

logger = logging.getLogger(__name__)

from cache.redis_client import cache_get, cache_set
from services.polygon_client import fetch_snapshot, fetch_fx_snapshot
from services.eodhd_client import fetch_realtime_quotes, fetch_intraday

# ── Native indices — yfinance symbol (fallback) + EODHD code (primary) ──
WORLD_INDICES = {
    "^GSPC":  {"name": "S&P 500",        "region": "Americas",  "country": "US",        "eodhd": "GSPC.INDX"},
    "^IXIC":  {"name": "Nasdaq",         "region": "Americas",  "country": "US",        "eodhd": "IXIC.INDX"},
    "^DJI":   {"name": "Dow Jones",      "region": "Americas",  "country": "US",        "eodhd": "DJI.INDX"},
    "^GSPTSE":{"name": "TSX",            "region": "Americas",  "country": "Canada",    "eodhd": "GSPTSE.INDX"},
    "^BVSP":  {"name": "Bovespa",        "region": "Americas",  "country": "Brazil",    "eodhd": "BVSP.INDX"},
    "^FTSE":  {"name": "FTSE 100",       "region": "Europe",    "country": "UK",        "eodhd": "FTSE.INDX"},
    "^GDAXI": {"name": "DAX",            "region": "Europe",    "country": "Germany",   "eodhd": "GDAXI.INDX"},
    "^FCHI":  {"name": "CAC 40",         "region": "Europe",    "country": "France",    "eodhd": "FCHI.INDX"},
    "^STOXX50E":{"name": "Euro Stoxx 50","region": "Europe",    "country": "Eurozone",  "eodhd": "STOXX50E.INDX"},
    "^IBEX":  {"name": "IBEX 35",        "region": "Europe",    "country": "Spain",     "eodhd": "IBEX.INDX"},
    "^N225":  {"name": "Nikkei 225",     "region": "Asia",      "country": "Japan",     "eodhd": "N225.INDX"},
    "^HSI":   {"name": "Hang Seng",      "region": "Asia",      "country": "Hong Kong", "eodhd": "HSI.INDX"},
    "000001.SS":{"name":"Shanghai Comp", "region": "Asia",      "country": "China",     "eodhd": "SSEC.INDX"},
    "^KS11":  {"name": "KOSPI",          "region": "Asia",      "country": "Korea",     "eodhd": "KS11.INDX"},
    "^TWII":  {"name": "Taiwan Weighted","region": "Asia",      "country": "Taiwan",    "eodhd": "TWII.INDX"},
    "^BSESN": {"name": "Sensex",         "region": "Asia",      "country": "India",     "eodhd": "SENSEX.INDX"},
    "^AXJO":  {"name": "ASX 200",        "region": "Asia",      "country": "Australia", "eodhd": "AXJO.INDX"},
}

EODHD_TO_YF = {meta["eodhd"]: yf_sym for yf_sym, meta in WORLD_INDICES.items()}

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


def _yfinance_indices(symbols: list[str]) -> list[dict]:
    """Blocking yfinance lookup for whichever index symbols need it. Runs in a thread."""
    try:
        import yfinance as yf
    except ImportError:
        return []
    if not symbols:
        return []
    out = []
    try:
        data = yf.download(symbols, period="5d", interval="1d",
                           group_by="ticker", progress=False, threads=True)
    except Exception as e:
        logger.warning(f"[International] yfinance error: {str(e)[:120]}")
        return []
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
                "change_pct": _pct(cur, prev), "source": "yfinance",
            })
        except Exception:
            continue
    return out


async def fetch_world_indices():
    """
    Native index levels. EODHD real-time quotes are the primary source (live,
    global exchange coverage); any index EODHD doesn't return a quote for
    (key not configured, or that particular index code failed) falls back to
    yfinance's last two daily closes.
    """
    cache_key = "intl:indices"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    eodhd_result = await fetch_realtime_quotes([meta["eodhd"] for meta in WORLD_INDICES.values()])
    eodhd_quotes = eodhd_result.get("quotes", {}) if eodhd_result.get("available") else {}

    out = []
    missing_yf_symbols = []
    for yf_sym, meta in WORLD_INDICES.items():
        q = eodhd_quotes.get(meta["eodhd"])
        if q and q.get("price") is not None:
            out.append({
                "symbol": yf_sym, "name": meta["name"], "region": meta["region"],
                "country": meta["country"], "level": round(q["price"], 2),
                "change_pct": q.get("change_pct"), "source": "eodhd",
            })
        else:
            missing_yf_symbols.append(yf_sym)

    if missing_yf_symbols:
        out.extend(await asyncio.to_thread(_yfinance_indices, missing_yf_symbols))

    if not out:
        return {"available": False, "reason": "no index data from EODHD or yfinance"}

    result = {
        "available": True, "indices": out,
        "as_of": datetime.datetime.utcnow().isoformat(),
    }
    # Live EODHD data moves fast; a pure yfinance fallback is EOD so cache longer.
    await cache_set(cache_key, result, ttl=30 if eodhd_quotes else 300)
    return result


async def fetch_index_bars(symbol: str, interval: str = "5m"):
    """
    Intraday chart bars for a World Indices symbol (the yfinance-style key,
    e.g. "^GSPC") — resolves to its EODHD code and pulls intraday history.
    Requires EODHD_API_KEY; the World Indices row otherwise has no chart.
    """
    meta = WORLD_INDICES.get(symbol)
    if not meta:
        return {"available": False, "reason": f"unknown index symbol {symbol}"}
    return await fetch_intraday(meta["eodhd"], interval=interval)


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
    if not snap:
        # fetch_fx_snapshot returns {} both on a transient failure and on a
        # 403 (this Polygon plan doesn't include forex) — either way, don't
        # silently render every row as blank dashes; say so.
        out = {
            "fx": [], "available": False,
            "reason": "FX snapshot unavailable — check Polygon plan entitlement for forex data",
            "as_of": datetime.datetime.utcnow().isoformat(),
        }
        await cache_set(cache_key, out, ttl=60)
        return out
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
    out = {"fx": rows, "available": True, "as_of": datetime.datetime.utcnow().isoformat()}
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


# FX pair -> country/region name, for grouping FX into the country directory
# below (WORLD_INDICES/COUNTRY_ETFS/ADRS already carry a country field;
# FX_PAIRS only carries the pair label, so this fills that gap).
_CURRENCY_COUNTRY = {
    "EUR/USD": "Eurozone", "USD/JPY": "Japan", "GBP/USD": "UK", "USD/CNH": "China",
    "USD/CAD": "Canada", "AUD/USD": "Australia", "USD/CHF": "Switzerland", "USD/KRW": "Korea",
}


async def fetch_country_directory():
    """
    CBQ-style country directory: the same indices/ETFs/ADRs/FX
    fetch_international_all() already pulls, regrouped by country instead
    of by asset type — no new data source, just a different shape for
    browsing "everything about country X" in one place.
    """
    all_data = await fetch_international_all()
    countries: dict[str, dict] = {}

    def bucket(name):
        return countries.setdefault(
            name, {"country": name, "index": None, "etf": None, "adrs": [], "fx": None})

    for row in (all_data.get("indices") or {}).get("indices") or []:
        bucket(row["country"])["index"] = row
    for row in (all_data.get("etfs") or {}).get("etfs") or []:
        if row.get("region") == "Broad":
            continue  # regional baskets (EFA/VWO/ACWX), not a single country
        bucket(row["name"])["etf"] = row
    for row in (all_data.get("adrs") or {}).get("adrs") or []:
        bucket(row["country"])["adrs"].append(row)
    for row in (all_data.get("fx") or {}).get("fx") or []:
        country = _CURRENCY_COUNTRY.get(row["pair"])
        if country:
            bucket(country)["fx"] = row

    return {"countries": sorted(countries.values(), key=lambda c: c["country"])}
