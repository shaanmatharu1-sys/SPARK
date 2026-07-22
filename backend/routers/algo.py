"""
routers/algo.py — Algorithm framework + paper trading (NO real execution)

Lets you create algorithms, run them against live data, and track a simulated
portfolio. Nothing here connects to a broker or places real orders.

Per-user: algo configs and their paper-portfolio state live in Postgres
(source of truth) with Redis as a hot read-through cache in front of the
portfolio snapshots — a cache eviction must not look like losing your
simulated trade history.
"""
from fastapi import APIRouter, Query, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import time
import datetime
import asyncio

from analytics.algo.engine import (
    AlgoConfig, evaluate_algo, default_algo_templates, list_strategies
)
from analytics.algo.portfolio import PaperPortfolio
from services.polygon_client import fetch_agg_bars, fetch_snapshot
from cache.redis_client import cache_get, cache_set, get_redis
from auth import get_current_user
from db import get_db
from models import User, AlgoConfig as AlgoConfigRow, AlgoPortfolioSnapshot

router = APIRouter(prefix="/algo", tags=["algo"])

PF_CACHE_KEY = "algo:portfolio:"  # Redis hot-cache prefix; Postgres is the source of truth


# ── Models ──────────────────────────────────────────────────────────
class CreateAlgo(BaseModel):
    name:     str
    strategy: str
    universe: list[str]
    capital:  float = 100_000.0
    max_position_pct: float = 0.20
    params:   dict = {}


# ── Helpers ─────────────────────────────────────────────────────────
async def _get_owned_algo(db: AsyncSession, user: User, algo_id: str) -> AlgoConfigRow | None:
    """Fetch an algo config, scoped to the current user — never trust algo_id alone."""
    return await db.scalar(
        select(AlgoConfigRow).where(AlgoConfigRow.id == algo_id, AlgoConfigRow.user_id == user.id)
    )


async def _load_portfolio(db: AsyncSession, algo_id: str) -> PaperPortfolio:
    cached = await cache_get(PF_CACHE_KEY + algo_id)
    if cached:
        return PaperPortfolio.from_dict(cached)
    snap = await db.scalar(
        select(AlgoPortfolioSnapshot).where(AlgoPortfolioSnapshot.algo_id == algo_id)
    )
    if snap:
        await cache_set(PF_CACHE_KEY + algo_id, snap.state, ttl=86400 * 30)
        return PaperPortfolio.from_dict(snap.state)
    return PaperPortfolio(name=algo_id)


async def _save_portfolio(db: AsyncSession, algo_id: str, pf: PaperPortfolio):
    state = pf.to_dict()
    await cache_set(PF_CACHE_KEY + algo_id, state, ttl=86400 * 30)
    snap = await db.scalar(
        select(AlgoPortfolioSnapshot).where(AlgoPortfolioSnapshot.algo_id == algo_id)
    )
    if snap:
        snap.state = state
    else:
        db.add(AlgoPortfolioSnapshot(algo_id=algo_id, state=state))
    await db.commit()


async def _price_history(symbols: list[str], days: int = 200) -> dict:
    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    async def one(s):
        bars = await fetch_agg_bars(s.upper(), 1, "day", start, today, limit=5000)
        return s.upper(), [b["c"] for b in bars if b.get("c") is not None]
    results = await asyncio.gather(*[one(s) for s in symbols], return_exceptions=True)
    return {s: c for r in results if isinstance(r, tuple) for s, c in [r]}

async def _current_prices(symbols: list[str]) -> dict:
    snap = await fetch_snapshot([s.upper() for s in symbols])
    out = {}
    for s in symbols:
        d = snap.get(s.upper(), {})
        px = (d.get("lastTrade", {}).get("p") or d.get("day", {}).get("c")
              or d.get("prevDay", {}).get("c"))
        if px:
            out[s.upper()] = px
    return out


# ── Endpoints ───────────────────────────────────────────────────────
@router.get("/strategies")
async def get_strategies():
    """Available strategies + tunable params for the algo builder."""
    return list_strategies()


@router.get("/templates")
async def get_templates():
    """Pre-built algo templates that can be created with one click."""
    return default_algo_templates()


@router.get("/list")
async def list_algos(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """All of the current user's configured algos with their latest portfolio snapshot."""
    rows = (await db.scalars(
        select(AlgoConfigRow).where(AlgoConfigRow.user_id == current_user.id)
    )).all()
    out = []
    for row in rows:
        pf = await _load_portfolio(db, row.id)
        prices = await _current_prices(row.config["universe"])
        out.append({
            "config":    row.config,
            "portfolio": pf.snapshot(prices),
        })
    return out


@router.post("/create")
async def create_algo(algo: CreateAlgo, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create a new algorithm (does not run it — call /run)."""
    aid = str(uuid.uuid4())[:8]
    cfg = AlgoConfig(
        algo_id=aid, name=algo.name, strategy=algo.strategy,
        universe=[s.upper() for s in algo.universe], capital=algo.capital,
        max_position_pct=algo.max_position_pct, params=algo.params,
    )
    from dataclasses import asdict
    cfg_dict = asdict(cfg)
    db.add(AlgoConfigRow(id=aid, user_id=current_user.id, name=algo.name, config=cfg_dict))
    await db.commit()
    # Initialize portfolio with the algo's capital, seeding the equity curve
    # with a starting point so the chart isn't empty before the first /run.
    pf = PaperPortfolio(name=aid, starting_cash=algo.capital)
    pf.record_equity({})
    await _save_portfolio(db, aid, pf)
    return {"created": aid, "config": cfg_dict}


@router.post("/{algo_id}/run")
async def run_algo(algo_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Evaluate the algo against live data and apply simulated orders to its
    paper portfolio. This is a SIMULATION — no real orders are placed.
    """
    row = await _get_owned_algo(db, current_user, algo_id)
    if not row:
        return {"error": "algo not found"}

    cfg = AlgoConfig(**row.config)
    history = await _price_history(cfg.universe)
    prices  = await _current_prices(cfg.universe)

    result = evaluate_algo(cfg, history, prices)
    if "error" in result:
        return result

    # Apply target positions to the paper portfolio
    pf = await _load_portfolio(db, algo_id)
    orders = []
    for sym, target_shares in result["targets"].items():
        px = prices.get(sym)
        if not px:
            continue
        r = pf.target_position(sym, target_shares, px, strategy=cfg.strategy)
        if "filled" in r:
            orders.append(r["filled"])
    pf.record_equity(prices)
    await _save_portfolio(db, algo_id, pf)

    return {
        "algo_id":   algo_id,
        "signals":   result["signals"],
        "targets":   result["targets"],
        "orders_filled": orders,
        "portfolio": pf.snapshot(prices),
        "note": "Simulated execution only — no real orders placed.",
    }


@router.get("/{algo_id}")
async def get_algo(algo_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get one algo's config + portfolio snapshot."""
    row = await _get_owned_algo(db, current_user, algo_id)
    if not row:
        return {"error": "algo not found"}
    pf = await _load_portfolio(db, algo_id)
    prices = await _current_prices(row.config["universe"])
    return {"config": row.config, "portfolio": pf.snapshot(prices)}


@router.post("/{algo_id}/reset")
async def reset_algo(algo_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Reset an algo's paper portfolio to its starting capital."""
    row = await _get_owned_algo(db, current_user, algo_id)
    if not row:
        return {"error": "algo not found"}
    pf = PaperPortfolio(name=algo_id, starting_cash=row.config["capital"])
    pf.record_equity({})
    await _save_portfolio(db, algo_id, pf)
    return {"reset": algo_id}


@router.delete("/{algo_id}")
async def delete_algo(algo_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Delete an algo and its portfolio."""
    row = await _get_owned_algo(db, current_user, algo_id)
    if row:
        await db.delete(row)  # cascades to algo_portfolio_snapshots via FK
        await db.commit()
        r = await get_redis()
        await r.delete(PF_CACHE_KEY + algo_id)
    return {"deleted": algo_id}
