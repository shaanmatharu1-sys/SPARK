"""
routers/unusual_activity.py — Unusual options activity + WebSocket stream
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from services.polygon_client import fetch_unusual_activity
from websocket.manager import manager
from cache.redis_client import subscribe
import json

router = APIRouter(prefix="/unusual", tags=["unusual_activity"])


@router.get("/")
async def get_unusual_activity(symbol: str = Query(default=None)):
    """
    GET /unusual/?symbol=AAPL — Top unusual options activity.
    Sorted by volume, flags large OI/volume ratio trades.
    """
    data = await fetch_unusual_activity(symbol)

    # Enrich with flags
    enriched = []
    for contract in data:
        day    = contract.get("day", {})
        detail = contract.get("details", {})
        oi     = contract.get("open_interest")
        vol    = day.get("volume")

        flags = []
        if vol and oi and oi > 0 and vol / oi > 0.5:
            flags.append("HIGH_VOL_OI")
        if detail.get("contract_type") == "call":
            flags.append("CALL")
        else:
            flags.append("PUT")
        if day.get("vwap") and detail.get("strike_price"):
            # Above vs below strike
            if day["vwap"] > float(detail["strike_price"]):
                flags.append("ITM")
            else:
                flags.append("OTM")

        contract["flags"] = flags
        enriched.append(contract)

    return enriched


@router.websocket("/ws")
async def unusual_websocket(websocket: WebSocket):
    """WebSocket: ws://localhost:8000/unusual/ws — Real-time unusual activity alerts."""
    await manager.connect(websocket, "unusual")
    try:
        async for message in subscribe("unusual"):
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "unusual")
