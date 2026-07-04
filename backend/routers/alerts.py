"""
routers/alerts.py — Per-user price alerts (Postgres-backed) + real-time
delivery over an authenticated WebSocket.

WS auth note: browsers can't set an Authorization header on a WebSocket
handshake, and putting the real (30-day) JWT in a query string risks it
leaking into logs/history/Referer headers. Instead, an authenticated REST
call mints a short-lived, single-use ticket; the WS handshake exchanges
that ticket (not the JWT) for the connection.
"""
import asyncio
import datetime
import logging
import secrets

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from cache.redis_client import cache_get, cache_set, cache_delete, subscribe, publish
from db import get_db
from models import User, Alert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])

WS_TICKET_TTL = 60  # seconds a minted ticket stays valid/unused


class AlertCreate(BaseModel):
    symbol: str
    condition: str  # "above" | "below"
    threshold: float


def _serialize(a: Alert) -> dict:
    return {
        "id": a.id, "symbol": a.symbol, "condition": a.condition,
        "threshold": a.threshold, "active": a.active,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
    }


@router.get("/")
async def list_alerts(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Current user's alerts (active + recently triggered)."""
    rows = (await db.scalars(
        select(Alert).where(Alert.user_id == current_user.id).order_by(Alert.created_at.desc())
    )).all()
    return {"alerts": [_serialize(a) for a in rows]}


@router.post("/")
async def create_alert(body: AlertCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create a new price alert for the current user."""
    if body.condition not in ("above", "below"):
        return {"error": "condition must be 'above' or 'below'"}
    alert = Alert(user_id=current_user.id, symbol=body.symbol.upper().strip(),
                  condition=body.condition, threshold=body.threshold)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return {"alert": _serialize(alert), "saved": True}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Delete one of the current user's alerts (active or already-triggered)."""
    alert = await db.get(Alert, alert_id)
    if alert is None or alert.user_id != current_user.id:
        return {"error": "alert not found"}
    await db.delete(alert)
    await db.commit()
    return {"saved": True, "removed": alert_id}


@router.post("/ws-ticket")
async def mint_ws_ticket(current_user: User = Depends(get_current_user)):
    """
    Authenticated (Bearer) call that mints a short-lived, single-use ticket
    for the alerts WebSocket — the WS handshake itself uses this ticket
    instead of the real JWT, since it has to travel in a URL.
    """
    ticket = secrets.token_urlsafe(24)
    await cache_set(f"alerts:ws_ticket:{ticket}", {"user_id": current_user.id}, ttl=WS_TICKET_TTL)
    return {"ticket": ticket, "expires_in": WS_TICKET_TTL}


@router.websocket("/ws")
async def alerts_ws(websocket: WebSocket, ticket: str = Query(...)):
    """WebSocket: ws://.../alerts/ws?ticket=<one-time ticket from /alerts/ws-ticket>"""
    cache_key = f"alerts:ws_ticket:{ticket}"
    claim = await cache_get(cache_key)
    if not claim:
        await websocket.close(code=4401)
        return
    await cache_delete(cache_key)  # single-use

    user_id = claim["user_id"]
    await websocket.accept()
    channel = f"alerts:{user_id}"
    try:
        async for msg in subscribe(channel):
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"[Alerts WS] user {user_id}: {e}")
