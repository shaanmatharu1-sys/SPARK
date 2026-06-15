"""
routers/quotes.py — Real-time quote endpoints + WebSocket stream
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from websocket.manager import manager
from services.polygon_client import fetch_snapshot, fetch_agg_bars, fetch_ticker_details
from cache.redis_client import hget_quote, subscribe
import asyncio

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get("/snapshot")
async def get_snapshot(symbols: str = Query(default=None)):
    """GET /quotes/snapshot?symbols=AAPL,MSFT,SPY"""
    from config import DEFAULT_WATCHLIST
    sym_list = symbols.split(",") if symbols else DEFAULT_WATCHLIST
    return await fetch_snapshot(sym_list)


@router.get("/{symbol}")
async def get_quote(symbol: str):
    """GET /quotes/AAPL — Returns latest cached quote or REST fallback."""
    cached = await hget_quote(symbol.upper())
    if cached:
        return cached
    snapshot = await fetch_snapshot([symbol.upper()])
    return snapshot.get(symbol.upper(), {})


@router.get("/{symbol}/bars")
async def get_bars(
    symbol:     str,
    multiplier: int = Query(default=1),
    timespan:   str = Query(default="minute"),
    from_date:  str = Query(default=None),
    to_date:    str = Query(default=None),
    limit:      int = Query(default=390),
):
    """GET /quotes/AAPL/bars?multiplier=1&timespan=minute — OHLCV for charting."""
    return await fetch_agg_bars(
        symbol.upper(), multiplier, timespan, from_date, to_date, limit
    )


@router.get("/{symbol}/details")
async def get_details(symbol: str):
    return await fetch_ticker_details(symbol.upper())


@router.websocket("/ws")
async def quotes_websocket(websocket: WebSocket, symbols: str = Query(default=None)):
    """
    WebSocket: ws://localhost:8000/quotes/ws?symbols=AAPL,MSFT
    Streams real-time trade/quote/bar messages from Polygon feed via Redis pub/sub.
    """
    await manager.connect(websocket, "quotes")
    filter_syms = set(symbols.upper().split(",")) if symbols else None

    try:
        async for message in subscribe("quotes"):
            if filter_syms and message.get("symbol") not in filter_syms:
                continue
            try:
                import json
                await websocket.send_text(json.dumps(message))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "quotes")
