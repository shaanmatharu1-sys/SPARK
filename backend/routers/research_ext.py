"""
routers/research_ext.py — Credit data, options quant research, portfolio tracking
"""
from fastapi import APIRouter, Query, Body
from pydantic import BaseModel

from services.fred_client import fetch_credit_dashboard
from services.polygon_client import fetch_snapshot, fetch_options_chain, fetch_agg_bars
from analytics.network.engine import build_network
import datetime
import asyncio
from analytics.options.engine import (
    payoff_diagram, build_strategy, iv_rank_percentile, putcall_signal,
    vol_skew, STRATEGY_LIST,
)
from analytics.portfolio.manual import compute_portfolio
from cache.redis_client import cache_get, cache_set

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

    return build_network(universe, threshold=threshold)


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


@router.get("/options-research/iv-rank/{symbol}")
async def options_iv_rank(symbol: str):
    """
    IV rank/percentile for a symbol. Pulls the option chain for current ATM IV,
    uses cached IV history (built up over time from scheduler runs).
    """
    chain = await fetch_options_chain(symbol.upper())
    snap = await fetch_snapshot([symbol.upper()])
    spot = (snap.get(symbol.upper(), {}).get("day", {}) or {}).get("c")

    # Find ATM IV from the chain
    atm_iv = None
    if chain and spot:
        atm = min(chain, key=lambda c: abs(c.get("strike_price", 0) - spot), default=None)
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
    chain = await fetch_options_chain(symbol.upper())
    if not chain:
        return {"symbol": symbol.upper(), "error": "no option chain data"}
    call_vol = sum(c.get("volume", 0) or 0 for c in chain if c.get("contract_type") == "call")
    put_vol  = sum(c.get("volume", 0) or 0 for c in chain if c.get("contract_type") == "put")
    call_oi  = sum(c.get("open_interest", 0) or 0 for c in chain if c.get("contract_type") == "call")
    put_oi   = sum(c.get("open_interest", 0) or 0 for c in chain if c.get("contract_type") == "put")
    result = putcall_signal(call_vol, put_vol, call_oi, put_oi)
    result["symbol"] = symbol.upper()
    return result


@router.get("/options-research/skew/{symbol}")
async def options_skew(symbol: str):
    """Put/call vol skew from the option chain."""
    chain = await fetch_options_chain(symbol.upper())
    snap = await fetch_snapshot([symbol.upper()])
    spot = (snap.get(symbol.upper(), {}).get("day", {}) or {}).get("c")
    if not chain or not spot:
        return {"symbol": symbol.upper(), "error": "insufficient data"}
    strikes_ivs = [
        {"strike": c.get("strike_price"), "iv": c.get("implied_volatility"),
         "type": c.get("contract_type")}
        for c in chain
        if c.get("implied_volatility") and c.get("strike_price") and c.get("contract_type")
    ]
    result = vol_skew(strikes_ivs, spot)
    result["symbol"] = symbol.upper()
    result["spot"] = spot
    return result


# ════════════════════════════════════════════════════════════════
# PORTFOLIO (manual holdings)
# ════════════════════════════════════════════════════════════════
PF_KEY = "user:portfolio"


class Holding(BaseModel):
    symbol:     str
    shares:     float
    cost_basis: float


class PortfolioUpdate(BaseModel):
    holdings: list[Holding]


@router.get("/portfolio")
async def get_portfolio():
    """Current manual portfolio, marked to live prices."""
    holdings = await cache_get(PF_KEY) or []
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
    return result


@router.put("/portfolio")
async def set_portfolio(update: PortfolioUpdate):
    """Replace the portfolio holdings."""
    holdings = [h.dict() for h in update.holdings]
    await cache_set(PF_KEY, holdings, ttl=86400 * 365)
    return {"saved": True, "n": len(holdings)}


@router.post("/portfolio/add")
async def add_holding(holding: Holding):
    """Add or update a single holding."""
    holdings = await cache_get(PF_KEY) or []
    sym = holding.symbol.upper()
    holdings = [h for h in holdings if h["symbol"].upper() != sym]
    holdings.append(holding.dict())
    await cache_set(PF_KEY, holdings, ttl=86400 * 365)
    return {"saved": True, "symbol": sym}


@router.delete("/portfolio/{symbol}")
async def remove_holding(symbol: str):
    """Remove a holding."""
    holdings = await cache_get(PF_KEY) or []
    holdings = [h for h in holdings if h["symbol"].upper() != symbol.upper()]
    await cache_set(PF_KEY, holdings, ttl=86400 * 365)
    return {"saved": True, "removed": symbol.upper()}
