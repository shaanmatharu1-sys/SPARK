"""
analytics/portfolio/manual.py
Manual portfolio tracker — user enters their own holdings (symbol, shares,
cost basis) and the terminal marks them to live market prices, computing P&L,
weights, and basic risk stats. Persisted in Redis.

This is distinct from the algo paper-portfolios: those are simulated by
strategies; this is the user's own real book, entered by hand.
"""
import logging
import math
import sys
import os

import numpy as np

logger = logging.getLogger(__name__)

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False

# Standard-normal quantiles for the 95%/99% confidence levels used below —
# hardcoded rather than pulled from scipy.stats.norm.ppf since these two
# constants are all parametric VaR/CVaR need.
_Z = {0.95: 1.6448536269514722, 0.99: 2.3263478740408408}


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _var_cvar(confidence: float, mean: float, std: float, sorted_rets: list[float]) -> dict:
    """
    Both VaR/CVaR readings at one confidence level, so the two methods can
    be compared directly instead of picking one and hiding the disagreement:
      - historical (empirical): non-parametric, reads straight off the
        observed return distribution's left tail — captures real fat tails
        and skew, but noisy with a short history.
      - parametric (Gaussian): assumes normally-distributed returns —
        smoother with limited history, but understates tail risk whenever
        actual returns are fat-tailed (the normal case for equities).
    Both returned as POSITIVE numbers representing a loss.
    """
    z = _Z[confidence]
    var_param = z * std - mean
    cvar_param = (_norm_pdf(z) / (1.0 - confidence)) * std - mean

    n = len(sorted_rets)
    idx = max(0, int(round((1.0 - confidence) * n)) - 1)
    var_hist = -sorted_rets[idx]
    tail = sorted_rets[:idx + 1]
    cvar_hist = -(sum(tail) / len(tail)) if tail else var_hist

    return {
        "var_historical":  round(var_hist, 4),
        "cvar_historical": round(cvar_hist, 4),
        "var_parametric":  round(var_param, 4),
        "cvar_parametric": round(cvar_param, 4),
    }


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

    mean = sum(port_rets) / len(port_rets)
    std = (sum((r - mean) ** 2 for r in port_rets) / (len(port_rets) - 1)) ** 0.5
    sorted_rets = sorted(port_rets)

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
        "var_cvar_daily": {
            "95": _var_cvar(0.95, mean, std, sorted_rets),
            "99": _var_cvar(0.99, mean, std, sorted_rets),
        },
        "n_days":           min_len,
        "n_holdings_used":  len(usable),
    }


def position_risk_contribution(positions: list[dict],
                               returns_by_symbol: dict[str, list[float]]) -> dict:
    """
    Decomposes total portfolio volatility into each position's CONTRIBUTION
    to it — not the same thing as its dollar weight. A small, high-vol
    position that's tightly correlated with the rest of the book can drive
    far more of the portfolio's risk than its weight suggests; a large but
    diversifying position can drive less. Previously the portfolio tab only
    showed %-of-book weight, which hides exactly this.

    Standard risk-budgeting decomposition: for weights w and covariance
    matrix Sigma, portfolio vol = sqrt(w'Sigma w); each asset's marginal
    contribution is (Sigma w)_i / vol, and its contribution to TOTAL vol is
    w_i * marginal_i (these sum exactly to portfolio vol, so the %-of-risk
    figures below sum to 100%).
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}

    usable = [p for p in positions if p["symbol"] in returns_by_symbol and p.get("weight")]
    if len(usable) < 2:
        return {"error": "need >= 2 priced holdings with return history"}

    min_len = min(len(returns_by_symbol[p["symbol"]]) for p in usable)
    if min_len < 20:
        return {"error": "insufficient aligned history", "n_days": min_len}

    symbols = [p["symbol"] for p in usable]
    weight_sum = sum(abs(p["weight"]) for p in usable)
    weights = np.array([p["weight"] / weight_sum if weight_sum else 0.0 for p in usable])
    returns_matrix = np.array([returns_by_symbol[s][-min_len:] for s in symbols])

    cov = np.cov(returns_matrix) * 252.0  # annualized covariance
    if cov.ndim == 0:  # exactly 2 symbols with degenerate shape edge case
        cov = np.array([[cov]])

    port_var = float(weights @ cov @ weights)
    port_vol = float(np.sqrt(max(port_var, 0.0)))
    if port_vol < 1e-10:
        return {"error": "portfolio volatility is ~0, risk contribution undefined"}

    marginal = (cov @ weights) / port_vol       # d(vol)/d(w_i)
    component = weights * marginal               # contribution to vol, sums to port_vol
    pct = component / port_vol                   # sums to 1.0

    rows = sorted([
        {
            "symbol":                symbols[i],
            "weight_pct":            round(float(weights[i]) * 100, 2),
            "risk_contribution_pct": round(float(pct[i]) * 100, 2),
            "marginal_ann_vol":      round(float(marginal[i]), 4),
        }
        for i in range(len(symbols))
    ], key=lambda r: r["risk_contribution_pct"], reverse=True)

    return {
        "portfolio_ann_vol": round(port_vol, 4),
        "positions":         rows,
        "n_days":            min_len,
    }


# Canned historical stress windows: real market episodes with large,
# well-documented equity drawdowns, used to replay ACTUAL historical moves
# against TODAY'S position sizes.
STRESS_SCENARIOS = {
    "covid_crash_2020": {
        "label": "COVID Crash (Feb 19 - Mar 23, 2020)",
        "start": "2020-02-19", "end": "2020-03-23",
    },
    "rate_shock_2022": {
        "label": "2022 Rate-Shock Bear Market (Jan 3 - Oct 14, 2022)",
        "start": "2022-01-03", "end": "2022-10-14",
    },
    "svb_crisis_2023": {
        "label": "SVB / Regional Bank Crisis (Mar 8 - Mar 13, 2023)",
        "start": "2023-03-08", "end": "2023-03-13",
    },
}


def stress_test_portfolio(positions: list[dict], scenario_returns: dict[str, float]) -> dict:
    """
    positions: compute_portfolio()'s `positions` list.
    scenario_returns: {symbol: cumulative simple return of THAT symbol over
                       the stress window} — the caller fetches each held
                       symbol's own real historical price action for the
                       window (see routers/research_ext.py), so this isn't
                       "the S&P fell X%, so you fell X%" — it's each name's
                       own actual move.
    Answers "what would this exact book have lost/gained if this episode
    happened again", using real history, not a hypothetical shock model.
    Symbols with no data in the window (didn't trade yet, delisted, etc.)
    are excluded from stressed_pnl and flagged via coverage_pct.
    """
    total_value = sum(p["market_value"] for p in positions if p.get("market_value"))
    stressed_pnl = 0.0
    covered_value = 0.0
    rows = []
    for p in positions:
        mv = p.get("market_value")
        if mv is None:
            continue
        ret = scenario_returns.get(p["symbol"])
        impact = mv * ret if ret is not None else None
        if impact is not None:
            stressed_pnl += impact
            covered_value += mv
        rows.append({
            "symbol":          p["symbol"],
            "market_value":    round(mv, 2),
            "scenario_return": round(ret, 4) if ret is not None else None,
            "pnl_impact":      round(impact, 2) if impact is not None else None,
        })

    return {
        "total_value":      round(total_value, 2),
        "coverage_pct":     round(covered_value / total_value * 100, 1) if total_value else None,
        "stressed_pnl":     round(stressed_pnl, 2),
        "stressed_pnl_pct": round(stressed_pnl / covered_value * 100, 2) if covered_value else None,
        "positions":        rows,
    }
