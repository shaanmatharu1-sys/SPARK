"""
routers/vol.py — Volatility surface analytics endpoints
"""
from fastapi import APIRouter, Query
from services.polygon_client import fetch_options_snapshot, fetch_snapshot
from analytics.vol.engine import build_surface, iv_rank

router = APIRouter(prefix="/vol", tags=["vol"])


@router.get("/surface/{symbol}")
async def get_vol_surface(symbol: str):
    """
    GET /vol/surface/AAPL
    Full implied-vol surface: term structure, skew (risk reversal/butterfly),
    and surface grid. Built by solving IV per contract via the C++ Greeks engine.
    """
    symbol = symbol.upper()

    # Get spot price
    snap = await fetch_snapshot([symbol])
    spot = None
    if symbol in snap:
        s = snap[symbol]
        spot = (s.get("lastTrade", {}).get("p")
                or s.get("day", {}).get("c")
                or s.get("prevDay", {}).get("c"))

    if not spot:
        return {"error": "could not determine spot price", "symbol": symbol}

    # Get options chain snapshot
    chain = await fetch_options_snapshot(symbol)
    if not chain:
        return {"error": "no options data (check Polygon options entitlement)", "symbol": symbol}

    # Extract contracts in the shape the engine expects
    contracts = []
    for c in chain:
        det = c.get("details", {})
        day = c.get("day", {})
        # Use Polygon's IV/greeks midpoint if available, else day close as mid
        mid = None
        q = c.get("last_quote", {})
        if q.get("bid") and q.get("ask"):
            mid = (q["bid"] + q["ask"]) / 2
        elif day.get("close"):
            mid = day["close"]

        if det.get("strike_price") and det.get("expiration_date") and mid:
            contracts.append({
                "strike":     float(det["strike_price"]),
                "expiration": det["expiration_date"],
                "mid":        float(mid),
                "type":       det.get("contract_type", "call"),
            })

    if not contracts:
        return {"error": "no usable contracts with quotes", "symbol": symbol, "spot": spot}

    result = build_surface(spot, contracts)
    result["symbol"] = symbol
    return result


@router.get("/iv-rank/{symbol}")
async def get_iv_rank(symbol: str, current_iv: float = Query(...)):
    """
    GET /vol/iv-rank/AAPL?current_iv=0.28
    IV rank & percentile vs trailing range. (History approximated from cached
    surface snapshots; pass current_iv from the surface endpoint.)
    """
    # In a full build this would pull stored IV history; here we return the calc
    # against whatever history is cached. Placeholder uses a reasonable window.
    from cache.redis_client import cache_get
    hist = await cache_get(f"iv_history:{symbol.upper()}") or []
    return iv_rank(current_iv, hist)
