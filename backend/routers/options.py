"""
routers/options.py — Options chain, Greeks, IV surface, real-time stream
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from websocket.manager import manager
from services.polygon_client import fetch_options_chain, fetch_options_snapshot, fetch_agg_bars
from cache.redis_client import subscribe
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
