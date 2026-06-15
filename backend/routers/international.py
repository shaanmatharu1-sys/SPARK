"""routers/international.py — Global markets endpoints."""
from fastapi import APIRouter
from services.international_client import (
    fetch_world_indices, fetch_country_etfs, fetch_adrs, fetch_fx,
    fetch_international_all,
)

router = APIRouter(prefix="/international", tags=["international"])


@router.get("/all")
async def international_all():
    """Everything for the international tab: indices, ETFs, ADRs, FX."""
    return await fetch_international_all()


@router.get("/indices")
async def world_indices():
    """Native global index levels (yfinance)."""
    return await fetch_world_indices()


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
    """FX rates (Polygon FX)."""
    return await fetch_fx()
