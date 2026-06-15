"""
routers/markets.py — Movers, crypto, earnings, SEC filings, social sentiment
"""
from fastapi import APIRouter, Query
from services.polygon_client import (
    fetch_movers, fetch_crypto_snapshot, fetch_crypto_bars, fetch_earnings,
)
from services.filings_client import fetch_filings, fetch_filings_by_type
from services.sentiment_social import fetch_social_sentiment

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/movers")
async def get_movers(direction: str = Query(default="gainers")):
    """Top gainers or losers. direction: gainers | losers"""
    if direction not in ("gainers", "losers"):
        return {"error": "direction must be 'gainers' or 'losers'"}
    return await fetch_movers(direction)


@router.get("/crypto")
async def get_crypto(symbols: str = Query(default=None)):
    """Crypto snapshots. Default majors, or pass X:BTCUSD,X:ETHUSD."""
    syms = [s.strip() for s in symbols.split(",")] if symbols else None
    return await fetch_crypto_snapshot(syms)


@router.get("/crypto/{symbol}/bars")
async def get_crypto_bars(symbol: str, days: int = Query(default=30)):
    """OHLCV bars for a crypto symbol (e.g. X:BTCUSD)."""
    sym = symbol if symbol.startswith("X:") else f"X:{symbol.upper()}"
    return await fetch_crypto_bars(sym, days)


@router.get("/earnings/{symbol}")
async def get_earnings(symbol: str):
    """Quarterly financials/earnings history for a symbol."""
    return await fetch_earnings(symbol)


@router.get("/filings/{symbol}")
async def get_filings(symbol: str, form_type: str = Query(default=None),
                      limit: int = Query(default=20)):
    """SEC EDGAR filings. Optionally filter by form_type (10-K, 10-Q, 8-K)."""
    if form_type:
        return await fetch_filings_by_type(symbol, form_type, limit)
    return await fetch_filings(symbol, limit)


@router.get("/social/{symbol}")
async def get_social(symbol: str):
    """Social media sentiment (StockTwits, best-effort)."""
    return await fetch_social_sentiment(symbol)


@router.get("/vessels")
async def get_vessels(limit: int = Query(default=500)):
    """Live vessel positions from AISstream for the supply-routes map."""
    from services.vessel_client import get_vessels as _gv
    return _gv(limit)


@router.get("/portwatch")
async def portwatch_all():
    """IMF PortWatch: chokepoint transit trends + port activity (weekly, official)."""
    from services.portwatch_client import fetch_portwatch_all
    return await fetch_portwatch_all()


@router.get("/portwatch/chokepoints")
async def portwatch_chokepoints():
    from services.portwatch_client import fetch_chokepoint_trends
    return await fetch_chokepoint_trends()


@router.get("/portwatch/ports")
async def portwatch_ports():
    from services.portwatch_client import fetch_port_activity
    return await fetch_port_activity()
