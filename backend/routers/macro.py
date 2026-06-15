"""
routers/macro.py — FRED macro data endpoints
"""
from fastapi import APIRouter, Query
from services.fred_client import (
    fetch_yield_curve,
    fetch_macro_dashboard,
    fetch_series,
    fetch_series_history,
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


@router.get("/series/{series_id}")
async def get_series(series_id: str, limit: int = Query(default=10)):
    """GET /macro/series/DGS10?limit=20 — Latest N observations."""
    return await fetch_series(series_id.upper(), limit)


@router.get("/series/{series_id}/history")
async def get_series_history(series_id: str, years: int = Query(default=5)):
    """GET /macro/series/DGS10/history?years=5 — Multi-year history for charting."""
    return await fetch_series_history(series_id.upper(), years)
