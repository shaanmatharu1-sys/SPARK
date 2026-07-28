"""
routers/orderbook.py — Order book depth endpoints.

Crypto gets a real, top-50-depth L2 book (Coinbase, free, no key — see
services/orderbook_client.py's CoinbaseOrderBookWS). Equities only ever get
a best-bid/ask NBBO quote where the data plan actually supports it — no
synthetic depth is ever fabricated for equities, see the honesty note in
services/orderbook_client.py.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

from services.orderbook_client import (
    PRODUCTS, get_book_snapshot, fetch_rest_snapshot, fetch_equity_top_of_book,
    _resolve_product_id,
)
from websocket.manager import manager
from cache.redis_client import subscribe

router = APIRouter(prefix="/orderbook", tags=["orderbook"])


@router.get("/products")
async def products():
    """Crypto products with a real, top-50-depth live order book."""
    return {"products": list(PRODUCTS.keys())}


@router.get("/{symbol}")
async def orderbook_snapshot(symbol: str, depth: int = 25):
    """
    GET /orderbook/BTCUSD -> top-50-depth L2 crypto book.
    GET /orderbook/AAPL   -> equity top-of-book only (or unavailable), never fabricated depth.
    """
    product_id = _resolve_product_id(symbol)
    if product_id:
        snap = get_book_snapshot(product_id, depth)
        if snap:
            return snap
        snap = await fetch_rest_snapshot(product_id, depth)
        if snap:
            return snap
        return {"symbol": symbol.upper(), "crypto": True, "available": False,
                "reason": "Order book feed not yet connected — try again shortly."}
    return await fetch_equity_top_of_book(symbol)


@router.websocket("/ws")
async def orderbook_websocket(websocket: WebSocket):
    """
    WebSocket: ws://localhost:8000/orderbook/ws
    Streams live L2 book updates (throttled ~6/sec/product) for every
    subscribed crypto product via Redis pub/sub — same channel/manager
    pattern as /markets/crypto/ws.
    """
    await manager.connect(websocket, "orderbook")
    try:
        async for message in subscribe("orderbook"):
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "orderbook")
