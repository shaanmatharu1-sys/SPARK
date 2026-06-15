"""
routers/factors.py — Cross-sectional factor ranking endpoints
"""
from fastapi import APIRouter, Query
from services.polygon_client import fetch_agg_bars
from analytics.factors.engine import compute_factor_ranks, DEFAULT_WEIGHTS
from config import DEFAULT_WATCHLIST, SECTOR_ETFS
import datetime
import asyncio

router = APIRouter(prefix="/factors", tags=["factors"])


async def _get_closes(symbol: str, days: int) -> tuple[str, list[float]]:
    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    bars = await fetch_agg_bars(symbol.upper(), 1, "day", start, today, limit=5000)
    return symbol.upper(), [b["c"] for b in bars if b.get("c") is not None]


@router.get("/rankings")
async def get_rankings(
    symbols: str = Query(default=None),
    days:    int = Query(default=400),
    universe: str = Query(default="watchlist"),
):
    """
    GET /factors/rankings?universe=watchlist
    GET /factors/rankings?symbols=AAPL,MSFT,NVDA,TSLA

    Cross-sectional factor ranking across a universe. Returns each name's
    factor z-scores, composite alpha score, rank, and suggested book side.
    """
    # Resolve universe
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",")]
    elif universe == "sectors":
        sym_list = SECTOR_ETFS
    else:
        sym_list = DEFAULT_WATCHLIST

    # Fetch all price histories concurrently
    tasks = [_get_closes(s, days) for s in sym_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    universe_data = {}
    for r in results:
        if isinstance(r, tuple):
            sym, closes = r
            if len(closes) >= 60:
                universe_data[sym] = closes

    if len(universe_data) < 2:
        return {"error": "insufficient data for universe", "symbols_loaded": list(universe_data.keys())}

    ranking = compute_factor_ranks(universe_data)
    ranking["universe"] = universe if not symbols else "custom"
    return ranking


@router.get("/weights")
async def get_default_weights():
    """GET /factors/weights — Default factor weights used in the composite."""
    return DEFAULT_WEIGHTS
