"""
routers/options.py — Options chain, Greeks, IV surface, real-time stream
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from websocket.manager import manager
from services.polygon_client import fetch_options_chain, fetch_options_snapshot, fetch_agg_bars
from cache.redis_client import subscribe
from auth import get_current_user
from db import get_db
from models import User, OptionPosition
import json

router = APIRouter(prefix="/options", tags=["options"])


@router.get("/{symbol}/chain")
async def get_options_chain(
    symbol:          str,
    expiration_date: str = Query(default=None),
):
    """GET /options/AAPL/chain?expiration_date=2024-01-19"""
    return await fetch_options_chain(symbol.upper(), expiration_date)


@router.get("/{symbol}/snapshot")
async def get_options_snapshot(symbol: str):
    """
    GET /options/AAPL/snapshot
    Returns options chain with Greeks + IV from Polygon (requires options tier).
    Falls back to our C++ Greeks calculator if server-side Greeks unavailable.
    """
    data = await fetch_options_snapshot(symbol.upper())

    # Enrich with C++ Greeks if Polygon didn't supply them
    try:
        from cpp_ext.greeks import greeks_module  # compiled pybind11 module
        import time
        S = None  # underlying price — would be fetched separately

        for contract in data:
            details = contract.get("details", {})
            day     = contract.get("day", {})
            greeks  = contract.get("greeks", {})

            # Only compute if Polygon Greeks are missing
            if not greeks.get("delta") and S:
                import datetime
                exp_str = details.get("expiration_date", "")
                if exp_str:
                    exp_dt  = datetime.datetime.strptime(exp_str, "%Y-%m-%d")
                    T       = max((exp_dt - datetime.datetime.now()).days / 365.0, 1e-6)
                    K       = float(details.get("strike_price", S))
                    mid     = (day.get("open", S) + day.get("close", S)) / 2 if day else S
                    is_call = details.get("contract_type", "call").lower() == "call"

                    g = greeks_module.compute_greeks(
                        S=S, K=K, T=T, r=0.05, sigma=0.25, is_call=is_call
                    )
                    contract["greeks"] = g

    except ImportError:
        pass  # C++ extension not compiled yet — serve Polygon data as-is

    return data


@router.get("/{symbol}/chain-full")
async def get_options_chain_full(
    symbol:          str,
    expiration_date: str = Query(default=None),
):
    """
    GET /options/AAPL/chain-full?expiration_date=2026-07-06
    Calls | strike | puts chain, grouped by expiration, using the snapshot
    endpoint (which carries Greeks/IV/volume/OI) rather than the reference
    endpoint (which only has static contract metadata, no Greeks).
    """
    contracts = await fetch_options_snapshot(symbol.upper())

    expirations = sorted({
        c.get("details", {}).get("expiration_date")
        for c in contracts if c.get("details", {}).get("expiration_date")
    })

    if expiration_date is None and expirations:
        expiration_date = expirations[0]

    by_strike = {}
    for c in contracts:
        details = c.get("details", {})
        if details.get("expiration_date") != expiration_date:
            continue
        strike = details.get("strike_price")
        if strike is None:
            continue
        row = by_strike.setdefault(strike, {"strike": strike, "call": None, "put": None})
        side = "call" if details.get("contract_type") == "call" else "put"
        row[side] = {
            "ticker":        details.get("ticker"),
            "iv":            c.get("implied_volatility"),
            "delta":         c.get("greeks", {}).get("delta"),
            "gamma":         c.get("greeks", {}).get("gamma"),
            "theta":         c.get("greeks", {}).get("theta"),
            "vega":          c.get("greeks", {}).get("vega"),
            "volume":        c.get("day", {}).get("volume"),
            "open_interest": c.get("open_interest"),
            "bid":           c.get("last_quote", {}).get("bid"),
            "ask":           c.get("last_quote", {}).get("ask"),
            "last":          c.get("last_trade", {}).get("price"),
        }

    rows = sorted(by_strike.values(), key=lambda r: r["strike"])
    return {"symbol": symbol.upper(), "expiration": expiration_date, "expirations": expirations, "rows": rows}


# ════════════════════════════════════════════════════════════════
# MANUAL OPTIONS POSITIONS + PORTFOLIO GREEKS DASHBOARD (per-user)
# ════════════════════════════════════════════════════════════════
class PositionIn(BaseModel):
    symbol:         str
    strike:         float
    expiration:     str   # YYYY-MM-DD
    contract_type:  str   # call | put
    qty:            int   # positive = long, negative = short
    side:           str   # long | short
    cost_basis:     float = 0


def _position_out(p: OptionPosition) -> dict:
    return {
        "id": p.id, "symbol": p.symbol, "strike": p.strike, "expiration": p.expiration,
        "contract_type": p.contract_type, "qty": p.qty, "side": p.side, "cost_basis": p.cost_basis,
    }


@router.get("/positions")
async def list_positions(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Current user's manually-tracked option positions."""
    rows = (await db.scalars(
        select(OptionPosition).where(OptionPosition.user_id == current_user.id)
    )).all()
    return [_position_out(p) for p in rows]


@router.post("/positions")
async def add_position(pos: PositionIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Add a manual option position."""
    row = OptionPosition(user_id=current_user.id, symbol=pos.symbol.upper(), strike=pos.strike,
                          expiration=pos.expiration, contract_type=pos.contract_type,
                          qty=pos.qty, side=pos.side, cost_basis=pos.cost_basis)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _position_out(row)


@router.delete("/positions/{position_id}")
async def remove_position(position_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Remove a manual option position (must belong to the current user)."""
    row = await db.scalar(
        select(OptionPosition).where(OptionPosition.id == position_id, OptionPosition.user_id == current_user.id)
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="position not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": position_id}


@router.get("/positions/greeks")
async def positions_greeks(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Portfolio-level Greeks: sum each position's live per-contract delta/gamma/
    theta/vega (scaled by qty x 100-share multiplier) across all positions.
    """
    rows = (await db.scalars(
        select(OptionPosition).where(OptionPosition.user_id == current_user.id)
    )).all()
    if not rows:
        return {"positions": [], "total": {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}, "n": 0}

    # One snapshot fetch per distinct underlying symbol, reused across that
    # symbol's positions instead of a request per position.
    symbols = {p.symbol for p in rows}
    snapshots = {}
    for sym in symbols:
        contracts = await fetch_options_snapshot(sym)
        lookup = {}
        for c in contracts:
            d = c.get("details", {})
            key = (d.get("strike_price"), d.get("expiration_date"), d.get("contract_type"))
            lookup[key] = c.get("greeks", {})
        snapshots[sym] = lookup

    out = []
    total = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for p in rows:
        greeks = snapshots.get(p.symbol, {}).get((p.strike, p.expiration, p.contract_type))
        multiplier = p.qty * 100
        contribution = None
        if greeks and all(greeks.get(k) is not None for k in ("delta", "gamma", "theta", "vega")):
            contribution = {k: round(greeks[k] * multiplier, 4) for k in ("delta", "gamma", "theta", "vega")}
            for k in total:
                total[k] += contribution[k]
        out.append({**_position_out(p), "greeks": greeks, "contribution": contribution})

    return {"positions": out, "total": {k: round(v, 4) for k, v in total.items()}, "n": len(rows)}


@router.websocket("/ws")
async def options_websocket(websocket: WebSocket):
    """
    WebSocket: ws://localhost:8000/options/ws
    Streams real-time options quote updates.
    """
    await manager.connect(websocket, "options")
    try:
        async for message in subscribe("options"):
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "options")
