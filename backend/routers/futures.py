"""routers/futures.py — Futures market data endpoints (free/delayed)."""
from fastapi import APIRouter
from services.futures_client import fetch_futures_all, fetch_futures_bars
from services.cftc_client import fetch_cot

router = APIRouter(prefix="/futures", tags=["futures"])


@router.get("/all")
async def futures_all():
    """Front-month continuous contract quotes for all covered futures (yfinance)."""
    return await fetch_futures_all()


@router.get("/{symbol}/bars")
async def futures_bars(symbol: str, days: int = 90):
    """Daily price history for one contract's drill-down chart."""
    return await fetch_futures_bars(symbol, days=days)


@router.get("/{symbol}/cot")
async def futures_cot(symbol: str, weeks: int = 26):
    """CFTC Commitment of Traders positioning trend for one contract."""
    return await fetch_cot(symbol, weeks=weeks)
