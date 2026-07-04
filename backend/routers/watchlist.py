"""
routers/watchlist.py — Per-user watchlist (Postgres-backed).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from config import DEFAULT_WATCHLIST
from db import get_db
from models import User, Watchlist

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistUpdate(BaseModel):
    symbols: list[str]


async def _get_or_create(db: AsyncSession, user: User) -> Watchlist:
    wl = await db.scalar(select(Watchlist).where(Watchlist.user_id == user.id))
    if wl is None:
        wl = Watchlist(user_id=user.id, symbols=list(DEFAULT_WATCHLIST))
        db.add(wl)
        await db.commit()
        await db.refresh(wl)
    return wl


@router.get("/")
async def get_watchlist(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Current user's watchlist (created with the default set on first read)."""
    wl = await _get_or_create(db, current_user)
    return {"symbols": wl.symbols, "is_custom": wl.symbols != list(DEFAULT_WATCHLIST)}


@router.put("/")
async def set_watchlist(update: WatchlistUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Replace the current user's watchlist with a new symbol list."""
    wl = await _get_or_create(db, current_user)
    wl.symbols = [s.strip().upper() for s in update.symbols if s.strip()][:50]  # cap at 50
    await db.commit()
    return {"symbols": wl.symbols, "saved": True}


@router.post("/add/{symbol}")
async def add_symbol(symbol: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Add one symbol to the current user's watchlist."""
    wl = await _get_or_create(db, current_user)
    sym = symbol.strip().upper()
    if sym and sym not in wl.symbols:
        wl.symbols = [*wl.symbols, sym][:50]
        await db.commit()
    return {"symbols": wl.symbols}


@router.delete("/{symbol}")
async def remove_symbol(symbol: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Remove one symbol from the current user's watchlist."""
    wl = await _get_or_create(db, current_user)
    sym = symbol.strip().upper()
    wl.symbols = [s for s in wl.symbols if s != sym]
    await db.commit()
    return {"symbols": wl.symbols}


@router.post("/reset")
async def reset_watchlist(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Reset the current user's watchlist to the default."""
    wl = await _get_or_create(db, current_user)
    wl.symbols = list(DEFAULT_WATCHLIST)
    await db.commit()
    return {"symbols": wl.symbols, "reset": True}
