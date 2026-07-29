"""routers/international.py — Global markets endpoints."""
from fastapi import APIRouter
from services.international_client import (
    fetch_world_indices, fetch_country_etfs, fetch_adrs, fetch_fx,
    fetch_international_all, fetch_country_directory, fetch_index_bars,
)

router = APIRouter(prefix="/international", tags=["international"])


@router.get("/all")
async def international_all():
    """Everything for the international tab: indices, ETFs, ADRs, FX."""
    return await fetch_international_all()


@router.get("/indices")
async def world_indices():
    """Native global index levels (EODHD real-time, yfinance fallback)."""
    return await fetch_world_indices()


@router.get("/indices/{symbol}/bars")
async def index_bars(symbol: str, interval: str = "5m"):
    """GET /international/indices/^GSPC/bars — intraday chart bars (EODHD)."""
    return await fetch_index_bars(symbol, interval=interval)


@router.get("/etfs")
async def country_etfs():
    """Country/region ETF performance (Polygon)."""
    return await fetch_country_etfs()


@router.get("/adrs")
async def adrs():
    """Major ADR performance (Polygon)."""
    return await fetch_adrs()


@router.get("/fx")
async def fx():
    """FX rates (Frankfurter — ECB reference rates)."""
    return await fetch_fx()


@router.get("/fx/matrix")
async def fx_matrix():
    """Cross-rate matrix among the major currencies."""
    return await fetch_fx_matrix()


@router.get("/fx/{code}/history")
async def fx_history(code: str, days: int = 180):
    """Historical daily series for one currency pair's drill-down chart."""
    return await fetch_fx_history(code, days=days)


@router.get("/directory")
async def directory():
    """CBQ-style country directory — index/ETF/ADRs/FX grouped by country."""
    return await fetch_country_directory()
