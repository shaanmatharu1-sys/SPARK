"""routers/altdata.py — Alternative data + events calendar endpoints."""
from fastapi import APIRouter, Query
from services.altdata_client import (
    fetch_trends, fetch_commodities, fetch_social_volume, fetch_altdata_all,
)
from services.events_client import (
    fetch_economic_calendar, fetch_earnings_calendar, fetch_events_all,
)

router = APIRouter(tags=["altdata"])


# ── Alt-data ──
@router.get("/altdata/all")
async def altdata_all(keywords: str = None, symbols: str = None):
    kw = [k.strip() for k in keywords.split(",")] if keywords else None
    sy = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    return await fetch_altdata_all(kw, sy)


@router.get("/altdata/trends")
async def trends(keywords: str = Query(default="recession,inflation,buy stocks,layoffs")):
    return await fetch_trends([k.strip() for k in keywords.split(",")])


@router.get("/altdata/commodities")
async def commodities():
    return await fetch_commodities()


@router.get("/altdata/social")
async def social(symbols: str = Query(default="AAPL,TSLA,NVDA,SPY,GME,AMC")):
    return await fetch_social_volume([s.strip().upper() for s in symbols.split(",")])


# ── Events ──
@router.get("/events/all")
async def events_all(watchlist: str = None):
    wl = [s.strip().upper() for s in watchlist.split(",")] if watchlist else None
    return await fetch_events_all(wl)


@router.get("/events/economic")
async def economic_calendar():
    return await fetch_economic_calendar()


@router.get("/events/earnings")
async def earnings_calendar(symbols: str = Query(default="AAPL,MSFT,NVDA,TSLA,AMZN,GOOGL,META")):
    return await fetch_earnings_calendar([s.strip().upper() for s in symbols.split(",")])
