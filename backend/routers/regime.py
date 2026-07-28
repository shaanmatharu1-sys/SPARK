"""routers/regime.py — Market-wide regime & breadth dashboard."""
from fastapi import APIRouter
from analytics.regime.engine import get_market_regime, get_regime_history

router = APIRouter(prefix="/regime", tags=["regime"])


@router.get("/")
async def market_regime():
    """
    Market-wide regime snapshot: % of SPY/QQQ/IWM/sector-ETFs trending vs
    mean-reverting vs random-walk, universe breadth (advance/decline, %
    in a 20d uptrend), and macro context (VIX regime, yield curve shape).
    """
    return await get_market_regime()


@router.get("/history")
async def market_regime_history():
    """
    Rolling history of regime snapshots (one point per precompute, hourly
    in production) — regime breadth %, advance/decline, VIX — so a shift
    like "60% trending -> 20% trending over two weeks" is visible as a
    trend instead of only ever showing the latest instant.
    """
    return {"history": await get_regime_history()}
