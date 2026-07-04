"""
routers/fundamentals.py — Short interest & analyst ratings endpoints

Ticker-keyed fundamentals that don't fit neatly under /quotes (Polygon
reference data) or /markets: short interest (FINRA, free/keyless) and
analyst ratings/price targets (Finnhub, free tier w/ API key).
"""
from fastapi import APIRouter

from services.short_interest_client import fetch_short_interest
from services.analyst_client import fetch_analyst_ratings

router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])


@router.get("/{symbol}/short-interest")
async def get_short_interest(symbol: str):
    """GET /fundamentals/AAPL/short-interest — FINRA Rule 4560 consolidated short interest."""
    return await fetch_short_interest(symbol.upper())


@router.get("/{symbol}/ratings")
async def get_ratings(symbol: str):
    """GET /fundamentals/AAPL/ratings — Analyst consensus + price target (Finnhub)."""
    return await fetch_analyst_ratings(symbol.upper())
