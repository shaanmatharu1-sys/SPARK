"""
analytics/factors/engine.py
Cross-sectional factor model.

Computes standard equity factors per symbol, z-scores them across the universe,
and combines into a composite alpha score. This is the "rank my whole watchlist"
engine — it answers which names look best *relative to each other* right now.

Factors:
  - Momentum     : 12-1 month return (skip most recent month to avoid reversal)
  - Short reversal: -1 * last-month return (mean-reversion at short horizon)
  - Low-vol      : -1 * realized vol (low-vol anomaly: less vol -> higher score)
  - Trend        : distance above/below 200-day MA
  - Vol-adj mom  : momentum / realized vol (risk-adjusted)

All factors are cross-sectionally z-scored, then equal-weighted (configurable)
into a composite. Higher composite = more attractive long.
"""
import sys
import os
import numpy as np
import logging

logger = logging.getLogger(__name__)

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False


# Default factor weights for the composite (must sum to ~1 for interpretability)
DEFAULT_WEIGHTS = {
    "momentum":     0.30,
    "short_rev":    0.15,
    "low_vol":      0.20,
    "trend":        0.20,
    "vol_adj_mom":  0.15,
}


def _raw_factors(prices: list[float]) -> dict | None:
    """Compute raw (un-normalized) factor values for one symbol's price history."""
    n = len(prices)
    if n < 60:
        return None

    log_rets = q.log_returns(prices)

    # Momentum 12-1: return from ~252d ago to ~21d ago (skip last month)
    if n > 252:
        mom_12_1 = prices[-21] / prices[-252] - 1.0
    elif n > 63:
        # fallback: 3-month skip-1-week momentum for shorter history
        mom_12_1 = prices[-6] / prices[-63] - 1.0
    else:
        mom_12_1 = prices[-1] / prices[0] - 1.0

    # Short reversal: last ~21d return (will be negated in scoring)
    lookback_rev = min(21, n - 1)
    short_ret = prices[-1] / prices[-1 - lookback_rev] - 1.0

    # Low vol: realized vol over last 60d
    rvol = q.realized_vol(log_rets[-60:], 252) if len(log_rets) >= 60 else q.realized_vol(log_rets, 252)

    # Trend: % distance from 200d MA (or longest available)
    ma_window = min(200, n)
    ma = q.rolling_mean(prices, ma_window)
    ma_last = ma[-1] if ma and not _isnan(ma[-1]) else prices[-1]
    trend = (prices[-1] - ma_last) / ma_last if ma_last else 0.0

    # Vol-adjusted momentum
    vol_adj_mom = mom_12_1 / rvol if rvol and rvol > 0 else 0.0

    return {
        "momentum":    mom_12_1,
        "short_rev":   short_ret,    # negated at composite stage
        "low_vol":     rvol,         # negated at composite stage
        "trend":       trend,
        "vol_adj_mom": vol_adj_mom,
    }


def compute_factor_ranks(universe: dict[str, list[float]],
                         weights: dict[str, float] = None) -> dict:
    """
    universe: {symbol: [close prices oldest->newest]}
    Returns cross-sectional factor z-scores, composite, and ranking.
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}

    weights = weights or DEFAULT_WEIGHTS

    # 1. Raw factors per symbol
    raw = {}
    for sym, prices in universe.items():
        f = _raw_factors([float(p) for p in prices if p is not None])
        if f:
            raw[sym] = f

    if len(raw) < 2:
        return {"error": "need >= 2 symbols with sufficient history", "n": len(raw)}

    symbols = list(raw.keys())
    factor_names = ["momentum", "short_rev", "low_vol", "trend", "vol_adj_mom"]

    # 2. Cross-sectional z-score each factor across the universe
    z_factors = {}
    for fname in factor_names:
        values = [raw[s][fname] for s in symbols]
        z = q.zscore(values)
        # Negate factors where LOW raw value = GOOD
        if fname in ("short_rev", "low_vol"):
            z = [-zi for zi in z]
        z_factors[fname] = dict(zip(symbols, z))

    # 3. Composite score per symbol
    results = []
    for sym in symbols:
        composite = sum(
            weights.get(fname, 0) * z_factors[fname][sym]
            for fname in factor_names
        )
        results.append({
            "symbol":    sym,
            "composite": round(composite, 4),
            "factors": {
                fname: round(z_factors[fname][sym], 3)
                for fname in factor_names
            },
            "raw": {
                fname: round(raw[sym][fname], 4)
                for fname in factor_names
            },
        })

    # 4. Rank (descending composite) and assign percentile
    results.sort(key=lambda x: x["composite"], reverse=True)
    n = len(results)
    for i, r in enumerate(results):
        r["rank"] = i + 1
        r["percentile"] = round(100 * (n - i - 1) / (n - 1), 1) if n > 1 else 50.0
        # Suggested book side
        if r["percentile"] >= 80:   r["book"] = "LONG"
        elif r["percentile"] <= 20: r["book"] = "SHORT"
        else:                       r["book"] = "—"

    return {
        "n_symbols":    n,
        "weights":      weights,
        "factor_names": factor_names,
        "rankings":     results,
    }


def _isnan(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x))
