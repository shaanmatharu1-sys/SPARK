"""
routers/workspace.py — Per-user multi-chart grid layout (Postgres-backed).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from config import DEFAULT_WATCHLIST
from db import get_db
from models import User, ChartWorkspace, Watchlist

router = APIRouter(prefix="/workspace", tags=["workspace"])

MAX_CELLS = 9  # caps at a 3x3 grid


class Cell(BaseModel):
    row: int
    col: int
    symbol: str
    timeframe: str = "1D"


class WorkspaceUpdate(BaseModel):
    rows: int
    cols: int
    cells: list[Cell]


def _default_cells(symbols: list[str]) -> list[dict]:
    fill = (symbols + list(DEFAULT_WATCHLIST))[:4]
    return [{"row": i // 2, "col": i % 2, "symbol": s, "timeframe": "1D"} for i, s in enumerate(fill)]


async def _get_or_create(db: AsyncSession, user: User) -> ChartWorkspace:
    ws = await db.scalar(select(ChartWorkspace).where(ChartWorkspace.user_id == user.id))
    if ws is None:
        wl = await db.scalar(select(Watchlist).where(Watchlist.user_id == user.id))
        symbols = wl.symbols if wl else []
        ws = ChartWorkspace(user_id=user.id, rows=2, cols=2, cells=_default_cells(symbols))
        db.add(ws)
        await db.commit()
        await db.refresh(ws)
    return ws


@router.get("/")
async def get_workspace(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Current user's saved chart-grid layout (created from the watchlist on first read)."""
    ws = await _get_or_create(db, current_user)
    return {"rows": ws.rows, "cols": ws.cols, "cells": ws.cells}


@router.put("/")
async def set_workspace(update: WorkspaceUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Replace the current user's chart-grid layout."""
    ws = await _get_or_create(db, current_user)
    if update.rows * update.cols > MAX_CELLS:
        return {"error": f"grid too large — max {MAX_CELLS} cells (3x3)"}
    ws.rows = update.rows
    ws.cols = update.cols
    ws.cells = [c.dict() for c in update.cells]
    await db.commit()
    return {"rows": ws.rows, "cols": ws.cols, "cells": ws.cells, "saved": True}
