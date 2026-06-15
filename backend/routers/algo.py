"""
routers/algo.py — Algorithm framework + paper trading (NO real execution)

Lets you create algorithms, run them against live data, and track a simulated
portfolio. Nothing here connects to a broker or places real orders.
"""
from fastapi import APIRouter, Query, Body
from pydantic import BaseModel
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

router = APIRouter(prefix="/algo", tags=["algo"])

ALGO_KEY = "algo:configs"
PF_KEY   = "algo:portfolio:"


# ── Models ──────────────────────────────────────────────────────────
class CreateAlgo(BaseModel):
    name:     str
    strategy: str
    universe: list[str]
    capital:  float = 100_000.0
    max_position_pct: float = 0.20
    params:   dict = {}


# ── Helpers ─────────────────────────────────────────────────────────
async def _load_algos() -> dict:
    return await cache_get(ALGO_KEY) or {}

async def _save_algos(algos: dict):
    await cache_set(ALGO_KEY, algos, ttl=86400 * 30)

async def _load_portfolio(algo_id: str) -> PaperPortfolio:
    data = await cache_get(PF_KEY + algo_id)
    if data:
        return PaperPortfolio.from_dict(data)
    return PaperPortfolio(name=algo_id)

async def _save_portfolio(algo_id: str, pf: PaperPortfolio):
    await cache_set(PF_KEY + algo_id, pf.to_dict(), ttl=86400 * 30)

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
async def list_algos():
    """All configured algos with their latest portfolio snapshot."""
    algos = await _load_algos()
    out = []
    for aid, cfg in algos.items():
        pf = await _load_portfolio(aid)
        prices = await _current_prices(cfg["universe"])
        out.append({
            "config":    cfg,
            "portfolio": pf.snapshot(prices),
        })
    return out


@router.post("/create")
async def create_algo(algo: CreateAlgo):
    """Create a new algorithm (does not run it — call /run)."""
    algos = await _load_algos()
    aid = str(uuid.uuid4())[:8]
    cfg = AlgoConfig(
        algo_id=aid, name=algo.name, strategy=algo.strategy,
        universe=[s.upper() for s in algo.universe], capital=algo.capital,
        max_position_pct=algo.max_position_pct, params=algo.params,
    )
    from dataclasses import asdict
    algos[aid] = asdict(cfg)
    await _save_algos(algos)
    # Initialize portfolio with the algo's capital
    pf = PaperPortfolio(name=aid, starting_cash=algo.capital)
    await _save_portfolio(aid, pf)
    return {"created": aid, "config": algos[aid]}


@router.post("/{algo_id}/run")
async def run_algo(algo_id: str):
    """
    Evaluate the algo against live data and apply simulated orders to its
    paper portfolio. This is a SIMULATION — no real orders are placed.
    """
    algos = await _load_algos()
    if algo_id not in algos:
        return {"error": "algo not found"}

    cfg = AlgoConfig(**algos[algo_id])
    history = await _price_history(cfg.universe)
    prices  = await _current_prices(cfg.universe)

    result = evaluate_algo(cfg, history, prices)
    if "error" in result:
        return result

    # Apply target positions to the paper portfolio
    pf = await _load_portfolio(algo_id)
    orders = []
    for sym, target_shares in result["targets"].items():
        px = prices.get(sym)
        if not px:
            continue
        r = pf.target_position(sym, target_shares, px, strategy=cfg.strategy)
        if "filled" in r:
            orders.append(r["filled"])
    await _save_portfolio(algo_id, pf)

    return {
        "algo_id":   algo_id,
        "signals":   result["signals"],
        "targets":   result["targets"],
        "orders_filled": orders,
        "portfolio": pf.snapshot(prices),
        "note": "Simulated execution only — no real orders placed.",
    }


@router.get("/{algo_id}")
async def get_algo(algo_id: str):
    """Get one algo's config + portfolio snapshot."""
    algos = await _load_algos()
    if algo_id not in algos:
        return {"error": "algo not found"}
    cfg = algos[algo_id]
    pf = await _load_portfolio(algo_id)
    prices = await _current_prices(cfg["universe"])
    return {"config": cfg, "portfolio": pf.snapshot(prices)}


@router.post("/{algo_id}/reset")
async def reset_algo(algo_id: str):
    """Reset an algo's paper portfolio to its starting capital."""
    algos = await _load_algos()
    if algo_id not in algos:
        return {"error": "algo not found"}
    pf = PaperPortfolio(name=algo_id, starting_cash=algos[algo_id]["capital"])
    await _save_portfolio(algo_id, pf)
    return {"reset": algo_id}


@router.delete("/{algo_id}")
async def delete_algo(algo_id: str):
    """Delete an algo and its portfolio."""
    algos = await _load_algos()
    if algo_id in algos:
        del algos[algo_id]
        await _save_algos(algos)
        r = await get_redis()
        await r.delete(PF_KEY + algo_id)
    return {"deleted": algo_id}
