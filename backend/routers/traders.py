"""
routers/traders.py — Notable traders: insiders, Congress, hedge fund 13F
"""
from fastapi import APIRouter, Query
from services.traders_client import (
    fetch_insider_trades, fetch_congress_trades, fetch_13f_filings, list_funds
)

router = APIRouter(prefix="/traders", tags=["traders"])


@router.get("/insider/{symbol}")
async def get_insider(symbol: str, limit: int = Query(default=30)):
    """Corporate insider (Form 4) trades for a ticker."""
    return await fetch_insider_trades(symbol, limit)


@router.get("/congress")
async def get_congress(chamber: str = Query(default="house"),
                       ticker: str = Query(default=None),
                       limit: int = Query(default=50)):
    """Congressional stock transactions. chamber: house | senate."""
    if chamber not in ("house", "senate"):
        return {"error": "chamber must be 'house' or 'senate'"}
    return await fetch_congress_trades(chamber, limit, ticker)


@router.get("/funds")
async def get_funds():
    """List notable funds available for 13F tracking."""
    return list_funds()


@router.get("/13f/{fund_key}")
async def get_13f(fund_key: str):
    """Recent 13F filings for a notable fund."""
    return await fetch_13f_filings(fund_key)
