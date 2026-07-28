"""
routers/vol.py — Volatility surface analytics endpoints
"""
import datetime
from fastapi import APIRouter, Query
from services.polygon_client import fetch_options_snapshot, fetch_snapshot
from analytics.vol.engine import build_surface, iv_rank
from cache.redis_client import cache_get, cache_set

router = APIRouter(prefix="/vol", tags=["vol"])

VOL_HISTORY_MAX = 60  # capped snapshot history per symbol, used for IV rank + term-structure overlay


def _parse_iso(ts: str):
    try:
        return datetime.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


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
    result["computed_at"] = datetime.datetime.utcnow().isoformat()
    if "error" in result:
        return result

    # Append this snapshot to a rolling per-symbol history — the surface is
    # otherwise stateless, so IV rank/percentile and "where was term structure
    # a week ago" had nothing to compare against (iv_rank() existed but was
    # never called with real history; the term-structure chart had no
    # historical reference line at all).
    atm_front = result.get("summary", {}).get("atm_iv_front")
    if atm_front is not None:
        hist_key = f"vol_history:{symbol}"
        history = await cache_get(hist_key) or []
        prior_snapshots = list(history)  # before appending the current one
        history.append({
            "computed_at":    result["computed_at"],
            "atm_iv_front":   atm_front,
            "term_structure": result["term_structure"],
        })
        await cache_set(hist_key, history[-VOL_HISTORY_MAX:], ttl=86400 * 30)

        iv_history_values = [h["atm_iv_front"] for h in prior_snapshots]
        result["iv_rank"] = iv_rank(atm_front, iv_history_values)

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        dated = [(h, _parse_iso(h["computed_at"])) for h in prior_snapshots]
        dated = [(h, ts) for h, ts in dated if ts is not None]
        prior_week = min(dated, key=lambda p: abs((p[1] - cutoff).total_seconds()), default=(None, None))[0]
        result["term_structure_prior_week"] = prior_week["term_structure"] if prior_week else None

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
