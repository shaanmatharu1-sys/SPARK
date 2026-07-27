"""
analytics/portfolio/manual.py
Manual portfolio tracker — user enters their own holdings (symbol, shares,
cost basis) and the terminal marks them to live market prices, computing P&L,
weights, and basic risk stats. Persisted in Redis.

This is distinct from the algo paper-portfolios: those are simulated by
strategies; this is the user's own real book, entered by hand.
"""
import logging
import sys
import os

logger = logging.getLogger(__name__)

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False


def compute_portfolio(holdings: list[dict], prices: dict[str, float]) -> dict:
    """
    holdings: [{symbol, shares, cost_basis}]
    prices:   {symbol: current_price}
    Returns marked-to-market portfolio with P&L, weights, allocation.
    """
    positions = []
    total_value = 0.0
    total_cost = 0.0

    for h in holdings:
        sym = h["symbol"].upper()
        shares = float(h.get("shares", 0))
        cost = float(h.get("cost_basis", 0))
        price = prices.get(sym)

        market_value = shares * price if price else None
        cost_value = shares * cost
        unreal = (market_value - cost_value) if market_value is not None else None
        unreal_pct = (unreal / cost_value * 100) if (unreal is not None and cost_value) else None

        if market_value is not None:
            total_value += market_value
        total_cost += cost_value

        positions.append({
            "symbol":         sym,
            "shares":         shares,
            "cost_basis":     round(cost, 2),
            "last_price":     round(price, 2) if price else None,
            "market_value":   round(market_value, 2) if market_value is not None else None,
            "cost_value":     round(cost_value, 2),
            "unrealized_pnl": round(unreal, 2) if unreal is not None else None,
            "unrealized_pct": round(unreal_pct, 2) if unreal_pct is not None else None,
        })

    # Weights
    for p in positions:
        p["weight"] = round(p["market_value"] / total_value * 100, 2) \
            if (p["market_value"] and total_value) else None

    total_pnl = total_value - total_cost
    return {
        "positions":       sorted(positions, key=lambda p: p.get("market_value") or 0, reverse=True),
        "total_value":     round(total_value, 2),
        "total_cost":      round(total_cost, 2),
        "total_pnl":       round(total_pnl, 2),
        "total_pnl_pct":   round(total_pnl / total_cost * 100, 2) if total_cost else None,
        "n_positions":     len([p for p in positions if p["shares"] != 0]),
    }


def compute_portfolio_risk(positions: list[dict], returns_by_symbol: dict[str, list[float]],
                           benchmark_returns: list[float], benchmark: str = "SPY") -> dict:
    """
    positions: compute_portfolio()'s `positions` list (needs symbol + weight,
               weight in percent as compute_portfolio produces).
    returns_by_symbol: {symbol: [daily simple returns, oldest -> newest]}
    benchmark_returns: benchmark's daily simple returns, same convention.

    Blends held names' daily returns using CURRENT weights (a snapshot risk
    read against today's book, not a backtest replaying historical weights),
    then derives beta, vol, drawdown, and historical VaR/CVaR from that
    blended series via the same C++ stats core the rest of the app uses
    (analytics/signals, analytics/backtest) — previously the portfolio tab
    had none of this, just P&L and %-weights.
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}

    usable = [p for p in positions if p["symbol"] in returns_by_symbol and p.get("weight")]
    if not usable:
        return {"error": "no return history available for any holding"}

    min_len = min(len(returns_by_symbol[p["symbol"]]) for p in usable)
    min_len = min(min_len, len(benchmark_returns))
    if min_len < 20:
        return {"error": "insufficient aligned history", "n_days": min_len}

    weight_sum = sum(abs(p["weight"]) for p in usable)
    port_rets = [0.0] * min_len
    for p in usable:
        w = (p["weight"] / weight_sum) if weight_sum else 0.0
        rets = returns_by_symbol[p["symbol"]][-min_len:]
        for i, ret in enumerate(rets):
            port_rets[i] += w * ret

    bench = benchmark_returns[-min_len:]
    beta = q.beta(port_rets, bench)
    corr = q.correlation(port_rets, bench)
    ann_vol = q.realized_vol(port_rets, 252)
    stats = q.perf_stats(port_rets, 0.0, 252.0).to_dict()

    # Historical (non-parametric) VaR/CVaR at 95% — empirical left tail of
    # the blended daily-return distribution, no normality assumption.
    sorted_rets = sorted(port_rets)
    cutoff_idx = max(0, int(round(0.05 * len(sorted_rets))) - 1)
    var_95 = -sorted_rets[cutoff_idx]
    tail = sorted_rets[:cutoff_idx + 1]
    cvar_95 = -(sum(tail) / len(tail)) if tail else var_95

    def _clean(x):
        return round(x, 4) if x is not None and x == x else None  # NaN-safe

    return {
        "benchmark":        benchmark,
        f"beta_vs_{benchmark.lower()}": _clean(beta),
        f"correlation_{benchmark.lower()}": _clean(corr),
        "ann_vol":          _clean(ann_vol),
        "sharpe":           _clean(stats.get("sharpe")),
        "sortino":          _clean(stats.get("sortino")),
        "max_drawdown":     _clean(stats.get("max_drawdown")),
        "var_95_daily":     _clean(var_95),
        "cvar_95_daily":    _clean(cvar_95),
        "n_days":           min_len,
        "n_holdings_used":  len(usable),
    }
