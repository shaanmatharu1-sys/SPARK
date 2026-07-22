"""
routers/fundamentals.py — Short interest & analyst ratings endpoints

Ticker-keyed fundamentals that don't fit neatly under /quotes (Polygon
reference data) or /markets: short interest (FINRA, free/keyless) and
analyst ratings/price targets (Finnhub, free tier w/ API key).
"""
from fastapi import APIRouter, Query
import asyncio

from services.short_interest_client import fetch_short_interest
from services.analyst_client import fetch_analyst_ratings
from services.polygon_client import fetch_ticker_details, fetch_earnings, fetch_snapshot

router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])


@router.get("/{symbol}/short-interest")
async def get_short_interest(symbol: str):
    """GET /fundamentals/AAPL/short-interest — FINRA Rule 4560 consolidated short interest."""
    return await fetch_short_interest(symbol.upper())


@router.get("/{symbol}/ratings")
async def get_ratings(symbol: str):
    """GET /fundamentals/AAPL/ratings — Analyst consensus + price target (Finnhub)."""
    return await fetch_analyst_ratings(symbol.upper())


@router.get("/relative-valuation")
async def relative_valuation(symbols: str = Query(..., description="comma-separated tickers, up to 4")):
    """
    GET /fundamentals/relative-valuation?symbols=AAPL,MSFT,GOOGL — Bloomberg RV:
    compare trailing P/E and market cap across up to 4 tickers side by side.
    Stitched from two calls this app already makes elsewhere (ticker details
    for market cap, quarterly financials for EPS) — not a new data source.
    """
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:4]
    if not syms:
        return {"error": "provide at least one symbol"}

    async def one(sym):
        details, earnings, snap = await asyncio.gather(
            fetch_ticker_details(sym), fetch_earnings(sym), fetch_snapshot([sym]),
        )
        quarters = earnings.get("quarters", []) if isinstance(earnings, dict) else []
        eps_qtrs = [q["eps_diluted"] for q in quarters[:4] if q.get("eps_diluted") is not None]
        ttm_eps = sum(eps_qtrs) if eps_qtrs else None
        s = snap.get(sym, {})
        price = (s.get("lastTrade", {}) or {}).get("p") or (s.get("day", {}) or {}).get("c") \
            or (s.get("prevDay", {}) or {}).get("c")
        pe = round(price / ttm_eps, 2) if price and ttm_eps and ttm_eps > 0 else None
        return {
            "symbol":     sym,
            "name":       details.get("name"),
            "market_cap": details.get("market_cap"),
            "price":      price,
            "ttm_eps":    round(ttm_eps, 2) if ttm_eps is not None else None,
            "pe_ratio":   pe,
            "sector":     details.get("sic_description"),
        }

    rows = await asyncio.gather(*[one(s) for s in syms], return_exceptions=True)
    return {"symbols": syms, "rows": [r for r in rows if not isinstance(r, Exception)]}
