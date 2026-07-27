"""
routers/research_ext.py — Credit data, options quant research, portfolio tracking
"""
from fastapi import APIRouter, Query, Body, Depends
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from services.fred_client import fetch_credit_dashboard
from services.polygon_client import fetch_snapshot, fetch_options_snapshot, fetch_agg_bars
from analytics.network.engine import build_network
from data_universe import UNIVERSE
import datetime
import asyncio

# GICS's 11 sectors collapsed to the 6 buckets Network.jsx's legend/color
# key actually has — was never wired in before (build_network() was called
# with no sectors arg at all, so every node silently fell back to "Unknown"
# and the sector legend was dead weight).
_GICS_TO_DISPLAY = {
    "Energy": "Energy",
    "Materials": "Industrials",
    "Industrials": "Industrials",
    "Utilities": "Industrials",
    "Consumer Discretionary": "Consumer",
    "Consumer Staples": "Consumer",
    "Health Care": "Healthcare",
    "Financials": "Financials",
    "Real Estate": "Financials",
    "Information Technology": "Tech",
    "Communication Services": "Tech",
}
from analytics.options.engine import (
    payoff_diagram, build_strategy, iv_rank_percentile, putcall_signal,
    vol_skew, STRATEGY_LIST,
)
from analytics.portfolio.manual import (
    compute_portfolio, compute_portfolio_risk, position_risk_contribution,
    stress_test_portfolio, STRESS_SCENARIOS,
)
from cache.redis_client import cache_get, cache_set
from auth import get_current_user
from db import get_db
from models import User, PortfolioHolding

router = APIRouter(tags=["research_ext"])


# ════════════════════════════════════════════════════════════════
# CREDIT
# ════════════════════════════════════════════════════════════════
@router.get("/credit/dashboard")
async def credit_dashboard():
    """IG/HY credit spreads, recession signal, credit-vs-equity divergence."""
    return await fetch_credit_dashboard()


@router.get("/network")
async def correlation_network(
    symbols:   str = Query(..., description="comma-separated tickers"),
    days:      int = Query(default=180),
    threshold: float = Query(default=0.4),
):
    """
    Correlation-network graph for any set of symbols the user requests.
    Returns nodes + weighted edges + clusters for the relationship map.
    """
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:40]
    if len(syms) < 2:
        return {"error": "provide at least 2 symbols"}

    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    async def closes(sym):
        bars = await fetch_agg_bars(sym, 1, "day", start, today, limit=5000)
        return sym, [b["c"] for b in bars if b.get("c") is not None]

    results = await asyncio.gather(*[closes(s) for s in syms], return_exceptions=True)
    universe = {s: c for r in results if isinstance(r, tuple) for s, c in [r] if len(c) >= 30}

    if len(universe) < 2:
        return {"error": "insufficient price data", "loaded": list(universe.keys())}

    sectors = {
        s: _GICS_TO_DISPLAY.get(UNIVERSE[s]["sector"], "Unknown")
        for s in universe if s in UNIVERSE
    }
    return build_network(universe, threshold=threshold, sectors=sectors)


@router.get("/ties")
async def company_ties(symbol: str = Query(...), top_n: int = Query(default=14)):
    """
    Bloomberg SPLC-style relationship web for ONE company.
    Pick a ticker; returns its strongest ties across the ~500-name universe,
    split into same-industry peers and cross-industry correlates.
    Reads a precomputed correlation cache (refreshed on schedule).
    """
    from analytics.relationships.engine import get_company_ties
    return await get_company_ties(symbol.upper(), top_n=top_n)


@router.get("/ties/universe")
async def ties_universe():
    """List the available universe (symbols + names) for the relationship map picker."""
    from data_universe import UNIVERSE
    return {"count": len(UNIVERSE),
            "companies": [{"symbol": s, "name": d["name"], "sector": d["sector"]}
                          for s, d in sorted(UNIVERSE.items())]}


@router.get("/arbitrage/etf")
async def arbitrage_etf_scan():
    """ETF vs underlying-holdings premium/discount scan across covered ETFs."""
    from analytics.arbitrage.etf_engine import scan_all_etfs
    return await scan_all_etfs()


@router.get("/arbitrage/etf/{etf}")
async def arbitrage_etf_one(etf: str):
    """Single ETF premium/discount detail with holdings breakdown."""
    from analytics.arbitrage.etf_engine import compute_etf_spread
    return await compute_etf_spread(etf.upper())


# ════════════════════════════════════════════════════════════════
# OPTIONS RESEARCH
# ════════════════════════════════════════════════════════════════
@router.get("/options-research/strategies")
async def options_strategies():
    """List available options strategy templates."""
    return STRATEGY_LIST


class PayoffRequest(BaseModel):
    strategy: str
    spot:     float
    params:   dict


@router.post("/options-research/payoff")
async def options_payoff(req: PayoffRequest):
    """Compute payoff diagram for a strategy."""
    legs = build_strategy(req.strategy, req.spot, req.params)
    if not legs:
        return {"error": f"unknown strategy '{req.strategy}'"}
    return payoff_diagram(legs, req.spot)


class CustomLeg(BaseModel):
    type:    str    # call | put | stock
    strike:  float
    premium: float = 0
    qty:     float = 1  # positive = long, negative = short


class CustomPayoffRequest(BaseModel):
    legs: list[CustomLeg]
    spot: float


@router.post("/options-research/payoff/custom")
async def options_payoff_custom(req: CustomPayoffRequest):
    """
    Compute payoff diagram for an arbitrary user-built combination of legs,
    bypassing the named-strategy templates in /options-research/payoff.
    payoff_diagram() already accepts arbitrary legs — this just exposes that
    directly over HTTP instead of only through build_strategy()'s 8 presets.
    """
    if not req.legs:
        return {"error": "at least one leg is required"}
    legs = [leg.dict() for leg in req.legs]
    return payoff_diagram(legs, req.spot)


@router.get("/options-research/iv-rank/{symbol}")
async def options_iv_rank(symbol: str):
    """
    IV rank/percentile for a symbol. Pulls the option chain for current ATM IV,
    uses cached IV history (built up over time from scheduler runs).
    """
    # Note: uses the snapshot endpoint (fetch_options_snapshot), not the static
    # reference endpoint (fetch_options_chain) — the reference endpoint has no
    # implied_volatility/volume/open_interest fields at all, only the snapshot
    # endpoint carries those.
    chain = await fetch_options_snapshot(symbol.upper())
    snap = await fetch_snapshot([symbol.upper()])
    spot = (snap.get(symbol.upper(), {}).get("day", {}) or {}).get("c")

    # Find ATM IV from the chain
    atm_iv = None
    if chain and spot:
        atm = min(chain, key=lambda c: abs(c.get("details", {}).get("strike_price", 0) - spot), default=None)
        if atm:
            atm_iv = atm.get("implied_volatility")

    # IV history from cache (scheduler appends daily); fall back to single point
    hist_key = f"iv_hist:{symbol.upper()}"
    iv_history = await cache_get(hist_key) or []
    if atm_iv:
        iv_history = (iv_history + [atm_iv])[-252:]
        await cache_set(hist_key, iv_history, 86400 * 400)

    result = iv_rank_percentile(atm_iv, iv_history)
    result["symbol"] = symbol.upper()
    result["history_days"] = len(iv_history)
    if len(iv_history) < 20:
        result["note"] = ("IV history is still building. Rank/percentile become "
                          "meaningful after ~20+ trading days of data collection.")
    return result


@router.get("/options-research/flow/{symbol}")
async def options_flow(symbol: str):
    """Put/call ratio and flow sentiment from the option chain."""
    # Snapshot endpoint, not the reference endpoint — see note in options_iv_rank above.
    chain = await fetch_options_snapshot(symbol.upper())
    if not chain:
        return {"symbol": symbol.upper(), "error": "no option chain data"}
    def ctype(c): return c.get("details", {}).get("contract_type")
    call_vol = sum((c.get("day", {}) or {}).get("volume", 0) or 0 for c in chain if ctype(c) == "call")
    put_vol  = sum((c.get("day", {}) or {}).get("volume", 0) or 0 for c in chain if ctype(c) == "put")
    call_oi  = sum(c.get("open_interest", 0) or 0 for c in chain if ctype(c) == "call")
    put_oi   = sum(c.get("open_interest", 0) or 0 for c in chain if ctype(c) == "put")

    # Same rolling-history cache pattern as options_iv_rank above, so the
    # sentiment read is against this symbol's own trailing PCR range.
    hist_key = f"pcr_hist:{symbol.upper()}"
    pcr_history = await cache_get(hist_key) or []
    if call_vol:
        pcr_history = (pcr_history + [put_vol / call_vol])[-252:]
        await cache_set(hist_key, pcr_history, 86400 * 400)

    result = putcall_signal(call_vol, put_vol, call_oi, put_oi, pcr_history=pcr_history)
    result["symbol"] = symbol.upper()
    return result


@router.get("/options-research/skew/{symbol}")
async def options_skew(symbol: str):
    """Put/call vol skew from the option chain."""
    # Snapshot endpoint, not the reference endpoint — see note in options_iv_rank above.
    chain = await fetch_options_snapshot(symbol.upper())
    snap = await fetch_snapshot([symbol.upper()])
    spot = (snap.get(symbol.upper(), {}).get("day", {}) or {}).get("c")
    if not chain or not spot:
        return {"symbol": symbol.upper(), "error": "insufficient data"}
    strikes_ivs = [
        {"strike": c.get("details", {}).get("strike_price"), "iv": c.get("implied_volatility"),
         "type": c.get("details", {}).get("contract_type")}
        for c in chain
        if c.get("implied_volatility") and c.get("details", {}).get("strike_price") and c.get("details", {}).get("contract_type")
    ]
    result = vol_skew(strikes_ivs, spot)
    result["symbol"] = symbol.upper()
    result["spot"] = spot
    return result


# ════════════════════════════════════════════════════════════════
# PORTFOLIO (manual holdings, per-user)
# ════════════════════════════════════════════════════════════════
# Note: "portfolio:last_prices" stays a global Redis cache keyed by symbol,
# not by user — it's a market-data fallback (last known price for a symbol),
# not private user data, so sharing it across users is correct and avoids
# needless duplication.


class Holding(BaseModel):
    symbol:     str
    shares:     float
    cost_basis: float


class PortfolioUpdate(BaseModel):
    holdings: list[Holding]


async def _user_holdings(db: AsyncSession, user: User) -> list[dict]:
    rows = (await db.scalars(
        select(PortfolioHolding).where(PortfolioHolding.user_id == user.id)
    )).all()
    return [{"symbol": r.symbol, "shares": r.shares, "cost_basis": r.cost_basis} for r in rows]


@router.get("/portfolio")
async def get_portfolio(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Current user's manual portfolio, marked to live prices."""
    holdings = await _user_holdings(db, current_user)
    if not holdings:
        return {"positions": [], "total_value": 0, "total_cost": 0,
                "total_pnl": 0, "n_positions": 0, "empty": True}
    symbols = [h["symbol"].upper() for h in holdings]
    snap = await fetch_snapshot(symbols)

    # Last-known prices cache, so a momentarily-missing snapshot doesn't blank a position
    last_known = await cache_get("portfolio:last_prices") or {}

    prices = {}
    for s in symbols:
        d = snap.get(s, {})
        px = ((d.get("lastTrade", {}) or {}).get("p")
              or (d.get("day", {}) or {}).get("c")
              or (d.get("prevDay", {}) or {}).get("c"))
        if px:
            prices[s] = px
            last_known[s] = px              # remember it
        elif s in last_known:
            prices[s] = last_known[s]       # fall back to last good price
        else:
            # Brand-new symbol whose snapshot isn't warm yet: use cost basis
            # so the row still renders instead of going blank.
            h = next((x for x in holdings if x["symbol"].upper() == s), None)
            if h and h.get("cost_basis"):
                prices[s] = float(h["cost_basis"])

    await cache_set("portfolio:last_prices", last_known, ttl=86400)
    result = compute_portfolio(holdings, prices)
    # Flag any symbols still awaiting a real quote, so the UI can show a subtle marker
    result["pending_prices"] = [s for s in symbols if s not in {**last_known}]
    result["risk"], result["risk_contribution"] = await _portfolio_risk_block(result["positions"])
    return result


async def _fetch_returns(symbols: set[str], start: str, end: str):
    """Daily closes -> simple returns for a set of symbols over [start, end].
    Returns (returns_by_symbol, quant_module) or (None, None) on failure."""
    import sys, os
    _quant_path = os.path.join(os.path.dirname(__file__), "..", "cpp_ext", "quant")
    sys.path.insert(0, os.path.abspath(_quant_path))
    try:
        import quant_module as qm
    except ImportError:
        return None, None

    async def closes_for(sym):
        try:
            bars = await fetch_agg_bars(sym, 1, "day", start, end, limit=5000)
            return sym, [b["c"] for b in bars if b.get("c") is not None]
        except Exception:
            return sym, []

    results = await asyncio.gather(*[closes_for(s) for s in symbols])
    return {s: qm.simple_returns(c) for s, c in results if len(c) >= 2}, qm


async def _portfolio_risk_block(positions: list[dict], days: int = 180):
    """Fetch trailing daily closes for the book + SPY and derive both the
    beta/vol/VaR risk block and the per-position risk-contribution
    decomposition (see analytics.portfolio.manual for the actual math)."""
    held_symbols = {p["symbol"] for p in positions if p.get("weight")}
    if not held_symbols:
        return {"error": "no priced positions"}, {"error": "no priced positions"}

    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    returns_by_symbol, qm = await _fetch_returns(held_symbols | {"SPY"}, start, today)
    if qm is None:
        err = {"error": "quant_module not compiled"}
        return err, err
    bench_returns = returns_by_symbol.pop("SPY", [])
    if len(bench_returns) < 20:
        err = {"error": "benchmark history unavailable"}
        return err, err
    returns_by_symbol = {s: r for s, r in returns_by_symbol.items() if len(r) >= 20}

    risk = compute_portfolio_risk(positions, returns_by_symbol, bench_returns)
    contribution = position_risk_contribution(positions, returns_by_symbol)
    return risk, contribution


@router.get("/portfolio/stress-test")
async def get_portfolio_stress_test(current_user: User = Depends(get_current_user),
                                    db: AsyncSession = Depends(get_db)):
    """
    Replays real historical stress episodes (see
    analytics.portfolio.manual.STRESS_SCENARIOS) against TODAY'S position
    sizes — "what would this exact book have lost if this exact episode
    happened again" using each held symbol's own actual historical move,
    not a hypothetical uniform shock.
    """
    holdings = await _user_holdings(db, current_user)
    if not holdings:
        return {"scenarios": {}, "empty": True}
    symbols = [h["symbol"].upper() for h in holdings]

    snap = await fetch_snapshot(symbols)
    prices = {}
    for s in symbols:
        d = snap.get(s, {})
        px = ((d.get("lastTrade", {}) or {}).get("p")
              or (d.get("day", {}) or {}).get("c")
              or (d.get("prevDay", {}) or {}).get("c"))
        if px:
            prices[s] = px
    positions = compute_portfolio(holdings, prices)["positions"]

    async def one_scenario(key, cfg):
        returns_by_symbol, _ = await _fetch_returns(set(symbols), cfg["start"], cfg["end"])
        scenario_returns = {}
        for sym in symbols:
            closes_ret = returns_by_symbol.get(sym) if returns_by_symbol else None
            # Cumulative return across the window: compound the daily
            # simple returns rather than just (last - first)/first, so it's
            # exact even if a day is missing from the bar series.
            if closes_ret:
                cum = 1.0
                for r in closes_ret:
                    cum *= (1.0 + r)
                scenario_returns[sym] = cum - 1.0
        out = stress_test_portfolio(positions, scenario_returns)
        out["label"] = cfg["label"]
        out["start"], out["end"] = cfg["start"], cfg["end"]
        return key, out

    results = await asyncio.gather(*[one_scenario(k, c) for k, c in STRESS_SCENARIOS.items()])
    return {"scenarios": dict(results)}


@router.put("/portfolio")
async def set_portfolio(update: PortfolioUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Replace the current user's portfolio holdings."""
    await db.execute(delete(PortfolioHolding).where(PortfolioHolding.user_id == current_user.id))
    for h in update.holdings:
        db.add(PortfolioHolding(user_id=current_user.id, symbol=h.symbol.upper(),
                                 shares=h.shares, cost_basis=h.cost_basis))
    await db.commit()
    return {"saved": True, "n": len(update.holdings)}


@router.post("/portfolio/add")
async def add_holding(holding: Holding, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Add or update a single holding for the current user."""
    sym = holding.symbol.upper()
    existing = await db.scalar(
        select(PortfolioHolding).where(
            PortfolioHolding.user_id == current_user.id, PortfolioHolding.symbol == sym
        )
    )
    if existing:
        existing.shares = holding.shares
        existing.cost_basis = holding.cost_basis
    else:
        db.add(PortfolioHolding(user_id=current_user.id, symbol=sym,
                                 shares=holding.shares, cost_basis=holding.cost_basis))
    await db.commit()
    return {"saved": True, "symbol": sym}


@router.delete("/portfolio/{symbol}")
async def remove_holding(symbol: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Remove a holding for the current user."""
    sym = symbol.upper()
    await db.execute(delete(PortfolioHolding).where(
        PortfolioHolding.user_id == current_user.id, PortfolioHolding.symbol == sym
    ))
    await db.commit()
    return {"saved": True, "removed": sym}
