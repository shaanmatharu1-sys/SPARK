"""
routers/research.py — Pairs/stat-arb scanner + correlation/macro matrices
"""
from fastapi import APIRouter, Query
import datetime
import asyncio

from services.polygon_client import fetch_agg_bars
from services.fred_client import fetch_series_history
from analytics.pairs.engine import scan_pairs, analyze_pair
from analytics.correlation.engine import correlation_matrix, macro_matrix, MACRO_FACTORS
from config import DEFAULT_WATCHLIST, SECTOR_ETFS

router = APIRouter(prefix="/research", tags=["research"])


async def _closes(symbol: str, days: int) -> tuple[str, list[float]]:
    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    bars = await fetch_agg_bars(symbol.upper(), 1, "day", start, today, limit=5000)
    return symbol.upper(), [b["c"] for b in bars if b.get("c") is not None]


async def _load_universe(symbols: list[str], days: int) -> dict:
    results = await asyncio.gather(*[_closes(s, days) for s in symbols],
                                   return_exceptions=True)
    return {s: c for r in results if isinstance(r, tuple) for s, c in [r] if len(c) >= 60}


@router.get("/pairs")
async def get_pairs(
    symbols:  str = Query(default=None),
    universe: str = Query(default="watchlist"),
    days:     int = Query(default=400),
):
    """Scan a universe for cointegrated pairs."""
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",")]
    elif universe == "sectors":
        syms = SECTOR_ETFS
    else:
        syms = DEFAULT_WATCHLIST
    data = await _load_universe(syms, days)
    if len(data) < 2:
        return {"error": "insufficient data", "loaded": list(data.keys())}
    return scan_pairs(data)


@router.get("/pairs/{sym_y}/{sym_x}")
async def get_pair_detail(sym_y: str, sym_x: str, days: int = Query(default=400)):
    """Detailed cointegration analysis of one pair, with spread series."""
    (_, y), (_, x) = await asyncio.gather(_closes(sym_y, days), _closes(sym_x, days))
    if len(y) < 60 or len(x) < 60:
        return {"error": "insufficient data"}
    return analyze_pair(y, x, sym_y.upper(), sym_x.upper())


@router.get("/correlation")
async def get_correlation(
    symbols:  str = Query(default=None),
    universe: str = Query(default="watchlist"),
    days:     int = Query(default=120),
):
    """Asset-to-asset return correlation matrix."""
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",")]
    elif universe == "sectors":
        syms = SECTOR_ETFS
    else:
        syms = DEFAULT_WATCHLIST
    data = await _load_universe(syms, days)
    return correlation_matrix(data)


@router.get("/macro-matrix")
async def get_macro_matrix(
    symbols: str = Query(default=None),
    days:    int = Query(default=250),
):
    """Asset-to-macro-factor correlation matrix."""
    syms = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_WATCHLIST
    assets = await _load_universe(syms, days)

    # Load macro factor histories from FRED
    async def macro_one(fid):
        hist = await fetch_series_history(fid, years=2)
        return fid, [h["value"] for h in hist]
    macro_results = await asyncio.gather(*[macro_one(f) for f in MACRO_FACTORS],
                                         return_exceptions=True)
    macro = {f: v for r in macro_results if isinstance(r, tuple) for f, v in [r] if len(v) >= 30}

    return macro_matrix(assets, macro)
