"""
routers/macro.py — FRED macro data endpoints
"""
from fastapi import APIRouter, Query
from services.fred_client import (
    fetch_yield_curve,
    fetch_macro_dashboard,
    fetch_series,
    fetch_series_history,
    fetch_global_yields,
    fetch_real_yields,
)

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("/dashboard")
async def get_macro_dashboard():
    """GET /macro/dashboard — All key macro indicators."""
    return await fetch_macro_dashboard()


@router.get("/yield-curve")
async def get_yield_curve():
    """GET /macro/yield-curve — Full Treasury curve + 2s10s spread."""
    return await fetch_yield_curve()


@router.get("/yield-curve/extended")
async def get_yield_curve_extended():
    """GET /macro/yield-curve/extended — Curve + spreads + inversion + interpretation."""
    from services.fred_client import fetch_yield_curve_extended
    return await fetch_yield_curve_extended()


@router.get("/global-yields")
async def get_global_yields():
    """GET /macro/global-yields — Sovereign 10Y benchmark yields across 17 countries (FRED/OECD)."""
    return await fetch_global_yields()


@router.get("/real-yields")
async def get_real_yields():
    """GET /macro/real-yields — TIPS real yields + breakeven inflation (5Y/10Y/30Y, 5Y5Y fwd)."""
    return await fetch_real_yields()


@router.get("/expanded")
async def get_macro_expanded(category: str = None):
    """GET /macro/expanded — Broad macro across growth/inflation/labor/rates/credit/markets."""
    from services.fred_client import fetch_macro_expanded
    return await fetch_macro_expanded(category)


@router.get("/series/{series_id}")
async def get_series(series_id: str, limit: int = Query(default=10)):
    """GET /macro/series/DGS10?limit=20 — Latest N observations."""
    return await fetch_series(series_id.upper(), limit)


@router.get("/series/{series_id}/history")
async def get_series_history(series_id: str, years: int = Query(default=5)):
    """GET /macro/series/DGS10/history?years=5 — Multi-year history for charting."""
    return await fetch_series_history(series_id.upper(), years)
