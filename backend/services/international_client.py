"""
services/international_client.py

Global markets data:
  - Native index levels: EODHD real-time quotes (live, ~15-20min delayed)
    when EODHD_API_KEY is set, since Polygon/Finnhub here are US-only.
    Falls back to yfinance (Yahoo's unofficial API — free, but EOD-only and
    can be rate-limited) per-index for whatever EODHD doesn't cover.
  - Country/region ETFs, ADRs via Polygon (US-listed, already-wired).
  - FX rates via Frankfurter (ECB reference rates, free, no key — see the
    note above FX_CURRENCIES for why this replaced Polygon FX).
"""
import asyncio
import logging
import datetime

logger = logging.getLogger(__name__)

import aiohttp

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

# ── FX (Frankfurter — ECB reference rates, free, no key) ───────────────────
# Polygon's forex snapshot endpoint returns NOT_AUTHORIZED on this project's
# plan (verified directly against the live API: a call to
# /v2/snapshot/locale/global/markets/forex/tickers returns
# {"status":"NOT_AUTHORIZED","message":"You are not entitled to this
# data..."}) — this plan simply has no forex entitlement, which is why the
# World tab's FX section always rendered "unavailable" before this. Swapped
# to Frankfurter (api.frankfurter.app), which publishes daily ECB reference
# rates for free with no key and no rate-limit trouble, so FX now has a data
# source entirely independent of Polygon's entitlement.
FRANKFURTER_BASE = "https://api.frankfurter.app"

# code -> display metadata. "convention": market convention always quotes a
# handful of currencies AS the base against USD (EUR/USD, GBP/USD, AUD/USD,
# NZD/USD — "inverse" here, since Frankfurter's raw rate is USD-per-unit and
# needs inverting to get the conventional USD-per-EUR quote); every other
# currency here is quoted USD/CCY directly ("direct").
FX_CURRENCIES = {
    "EUR": {"name": "Euro",                 "country": "Eurozone",      "convention": "inverse"},
    "GBP": {"name": "British Pound",        "country": "UK",            "convention": "inverse"},
    "AUD": {"name": "Australian Dollar",    "country": "Australia",     "convention": "inverse"},
    "NZD": {"name": "New Zealand Dollar",   "country": "New Zealand",   "convention": "inverse"},
    "JPY": {"name": "Japanese Yen",         "country": "Japan",         "convention": "direct"},
    "CHF": {"name": "Swiss Franc",          "country": "Switzerland",   "convention": "direct"},
    "CAD": {"name": "Canadian Dollar",      "country": "Canada",        "convention": "direct"},
    "CNY": {"name": "Chinese Yuan",         "country": "China",         "convention": "direct"},
    "HKD": {"name": "Hong Kong Dollar",     "country": "Hong Kong",     "convention": "direct"},
    "SGD": {"name": "Singapore Dollar",     "country": "Singapore",     "convention": "direct"},
    "KRW": {"name": "Korean Won",           "country": "Korea",         "convention": "direct"},
    "INR": {"name": "Indian Rupee",         "country": "India",         "convention": "direct"},
    "MXN": {"name": "Mexican Peso",         "country": "Mexico",        "convention": "direct"},
    "BRL": {"name": "Brazilian Real",       "country": "Brazil",        "convention": "direct"},
    "ZAR": {"name": "South African Rand",   "country": "South Africa",  "convention": "direct"},
    "TRY": {"name": "Turkish Lira",         "country": "Turkey",        "convention": "direct"},
    "SEK": {"name": "Swedish Krona",        "country": "Sweden",        "convention": "direct"},
    "NOK": {"name": "Norwegian Krone",      "country": "Norway",        "convention": "direct"},
    "PLN": {"name": "Polish Zloty",         "country": "Poland",        "convention": "direct"},
}

# Curated set for the cross-rate matrix — the majors, where an NxN grid is
# actually useful (the full 19-currency set would make an unreadable table).
FX_MATRIX_CODES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY"]


def _fx_pair_label(code):
    meta = FX_CURRENCIES[code]
    return f"{code}/USD" if meta["convention"] == "inverse" else f"USD/{code}"


def _fx_display(code, usd_base_rate):
    """Convert Frankfurter's raw 'units of `code` per 1 USD' rate into the
    conventional display value for that pair (e.g. EUR/USD wants USD-per-EUR
    — the inverse of the raw USD-per-EUR... rate Frankfurter actually returns
    the other way: `usd_base_rate` here is units-of-code-per-USD, so EUR/USD
    display = 1 / that)."""
    if usd_base_rate in (None, 0):
        return None
    meta = FX_CURRENCIES[code]
    return (1 / usd_base_rate) if meta["convention"] == "inverse" else usd_base_rate


async def _frankfurter_range(days=10, to_codes=None):
    """One Frankfurter call spanning `days` back from today, optionally
    restricted to a subset of currencies. Returns the raw JSON or None on
    any network/HTTP failure."""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    params = {"from": "USD"}
    if to_codes:
        params["to"] = ",".join(to_codes)
    url = f"{FRANKFURTER_BASE}/{start.isoformat()}..{end.isoformat()}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    logger.warning(f"[FX] Frankfurter HTTP {r.status}")
                    return None
                return await r.json()
    except Exception as e:
        logger.warning(f"[FX] Frankfurter fetch failed: {e}")
        return None


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
    """
    FX rates via Frankfurter (ECB reference rates). One range call covering
    the trailing ~10 days gets both the latest rate and the prior business
    day in a single request (for change_pct) — cheaper than two separate calls.
    """
    cache_key = "intl:fx"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await _frankfurter_range(days=10, to_codes=list(FX_CURRENCIES.keys()))
    if not data or not data.get("rates"):
        out = {
            "fx": [], "available": False,
            "reason": "Frankfurter FX feed unavailable (network error)",
            "as_of": datetime.datetime.utcnow().isoformat(),
        }
        await cache_set(cache_key, out, ttl=60)
        return out

    dated = sorted(data["rates"].items())  # [(date_str, {code: rate}), ...] ascending
    latest_date, latest_rates = dated[-1]
    prev_rates = dated[-2][1] if len(dated) > 1 else {}

    rows = []
    for code, meta in FX_CURRENCIES.items():
        cur_disp  = _fx_display(code, latest_rates.get(code))
        prev_disp = _fx_display(code, prev_rates.get(code))
        rows.append({
            "pair": _fx_pair_label(code), "code": code,
            "name": meta["name"], "country": meta["country"],
            "rate": round(cur_disp, 4) if cur_disp is not None else None,
            "change_pct": _pct(cur_disp, prev_disp),
        })
    out = {
        "fx": rows, "available": True, "date": latest_date,
        "source": "Frankfurter (ECB reference rates)",
        "as_of": datetime.datetime.utcnow().isoformat(),
    }
    await cache_set(cache_key, out, ttl=TTL_FX)
    return out


async def fetch_fx_matrix():
    """Cross-rate matrix among the major currencies — units of column-code
    per 1 unit of row-code, derived from Frankfurter's USD-base snapshot."""
    cache_key = "intl:fx:matrix"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{FRANKFURTER_BASE}/latest", params={"from": "USD"},
                                   timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                data = await r.json()
    except Exception as e:
        out = {"available": False, "reason": f"Frankfurter unavailable: {str(e)[:100]}"}
        await cache_set(cache_key, out, ttl=60)
        return out

    usd_rates = {"USD": 1.0, **(data.get("rates") or {})}
    matrix = []
    for base in FX_MATRIX_CODES:
        row = {"base": base}
        for quote in FX_MATRIX_CODES:
            b, q = usd_rates.get(base), usd_rates.get(quote)
            row[quote] = round(q / b, 6) if b and q else None
        matrix.append(row)

    out = {
        "available": True, "codes": FX_MATRIX_CODES, "matrix": matrix,
        "date": data.get("date"), "as_of": datetime.datetime.utcnow().isoformat(),
    }
    await cache_set(cache_key, out, ttl=TTL_FX)
    return out


async def fetch_fx_history(code: str, days: int = 180):
    """Historical daily series for one currency's drill-down chart (the
    RawSeriesChart canvas engine on the frontend, same as futures/equities)."""
    code = code.upper()
    if code not in FX_CURRENCIES:
        return {"available": False, "reason": f"Unknown currency code '{code}'",
                "codes": list(FX_CURRENCIES.keys())}

    cache_key = f"intl:fx:history:{code}:{days}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await _frankfurter_range(days=days, to_codes=[code])
    if not data or not data.get("rates"):
        out = {"available": False, "reason": "Frankfurter history unavailable",
               "pair": _fx_pair_label(code), "code": code}
        await cache_set(cache_key, out, ttl=60)
        return out

    bars = []
    for date_str, rates in sorted(data["rates"].items()):
        disp = _fx_display(code, rates.get(code))
        if disp is None:
            continue
        t = int(datetime.datetime.fromisoformat(date_str).replace(
            tzinfo=datetime.timezone.utc).timestamp())
        bars.append({"t": t, "c": round(disp, 5)})

    out = {"available": True, "pair": _fx_pair_label(code), "code": code, "bars": bars}
    await cache_set(cache_key, out, ttl=TTL_FX)
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
        if row.get("country"):
            bucket(row["country"])["fx"] = row

    return {"countries": sorted(countries.values(), key=lambda c: c["country"])}
