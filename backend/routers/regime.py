"""routers/regime.py — Market-wide regime & breadth dashboard."""
from fastapi import APIRouter
from analytics.regime.engine import get_market_regime

router = APIRouter(prefix="/regime", tags=["regime"])


@router.get("/")
async def market_regime():
    """
    Market-wide regime snapshot: % of SPY/QQQ/IWM/sector-ETFs trending vs
    mean-reverting vs random-walk, universe breadth (advance/decline, %
    in a 20d uptrend), and macro context (VIX regime, yield curve shape).
    """
    return await get_market_regime()
