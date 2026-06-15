"""
routers/watchlist.py — User-customizable watchlist (persisted in Redis)
Lets the UI add/remove symbols instead of relying on env vars.
"""
from fastapi import APIRouter, Body
from pydantic import BaseModel
from cache.redis_client import cache_get, cache_set
from config import DEFAULT_WATCHLIST

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

WL_KEY = "user:watchlist"


class WatchlistUpdate(BaseModel):
    symbols: list[str]


@router.get("/")
async def get_watchlist():
    """Current watchlist (falls back to default if none saved)."""
    saved = await cache_get(WL_KEY)
    return {"symbols": saved or DEFAULT_WATCHLIST, "is_custom": saved is not None}


@router.put("/")
async def set_watchlist(update: WatchlistUpdate):
    """Replace the watchlist with a new symbol list."""
    syms = [s.strip().upper() for s in update.symbols if s.strip()][:50]  # cap at 50
    await cache_set(WL_KEY, syms, ttl=86400 * 365)
    return {"symbols": syms, "saved": True}


@router.post("/add/{symbol}")
async def add_symbol(symbol: str):
    """Add one symbol to the watchlist."""
    saved = await cache_get(WL_KEY) or list(DEFAULT_WATCHLIST)
    sym = symbol.strip().upper()
    if sym and sym not in saved:
        saved.append(sym)
        await cache_set(WL_KEY, saved[:50], ttl=86400 * 365)
    return {"symbols": saved}


@router.delete("/{symbol}")
async def remove_symbol(symbol: str):
    """Remove one symbol from the watchlist."""
    saved = await cache_get(WL_KEY) or list(DEFAULT_WATCHLIST)
    sym = symbol.strip().upper()
    saved = [s for s in saved if s != sym]
    await cache_set(WL_KEY, saved, ttl=86400 * 365)
    return {"symbols": saved}


@router.post("/reset")
async def reset_watchlist():
    """Reset to the default watchlist."""
    await cache_set(WL_KEY, list(DEFAULT_WATCHLIST), ttl=86400 * 365)
    return {"symbols": list(DEFAULT_WATCHLIST), "reset": True}
