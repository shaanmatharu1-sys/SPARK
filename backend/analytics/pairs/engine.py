"""
analytics/pairs/engine.py
Pairs / statistical-arbitrage scanner.

Tests all pairs in a universe for cointegration, ranks by tradeability
(stationary spread + reasonable half-life + current z-score extremity).
Built on the C++ test_pair (OLS hedge ratio + ADF + half-life + z-score).
"""
import sys
import os
import logging
from itertools import combinations

logger = logging.getLogger(__name__)

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False


def scan_pairs(universe: dict[str, list[float]],
               min_correlation: float = 0.5,
               max_half_life: float = 60.0) -> dict:
    """
    universe: {symbol: [aligned close prices]}
    Returns ranked cointegrated pairs with trade signals.

    All price series must be the same length (aligned by date).
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}

    symbols = [s for s, p in universe.items() if len(p) >= 60]
    if len(symbols) < 2:
        return {"error": "need >= 2 symbols with 60+ aligned points", "n": len(symbols)}

    # Align all to the shortest length
    min_len = min(len(universe[s]) for s in symbols)
    prices = {s: [float(p) for p in universe[s][-min_len:]] for s in symbols}

    results = []
    for sym_y, sym_x in combinations(symbols, 2):
        y, x = prices[sym_y], prices[sym_x]
        r = q.test_pair(y, x)

        # Filter: need meaningful correlation and a usable half-life
        if abs(r.correlation) < min_correlation:
            continue
        if not r.is_cointegrated:
            continue
        if r.half_life <= 0 or r.half_life > max_half_life:
            continue

        # Trade signal from current z-score
        signal = "NEUTRAL"
        if r.spread_z > 2.0:    signal = "SHORT_SPREAD"   # short y, long x
        elif r.spread_z < -2.0: signal = "LONG_SPREAD"    # long y, short x
        elif abs(r.spread_z) < 0.5: signal = "AT_MEAN"

        results.append({
            "pair":          f"{sym_y}/{sym_x}",
            "y":             sym_y,
            "x":             sym_x,
            "hedge_ratio":   round(r.hedge_ratio, 4),
            "correlation":   round(r.correlation, 4),
            "adf_stat":      round(r.adf_stat, 3),
            "half_life":     round(r.half_life, 1),
            "spread_z":      round(r.spread_z, 2),
            "signal":        signal,
            # Tradeability score: more stationary + more extreme z + faster reversion
            "score":         round(abs(r.adf_stat) * abs(r.spread_z) / max(r.half_life, 1), 3),
        })

    # Rank by tradeability score
    results.sort(key=lambda p: p["score"], reverse=True)

    return {
        "n_pairs_tested": len(list(combinations(symbols, 2))),
        "n_cointegrated": len(results),
        "n_symbols":      len(symbols),
        "pairs":          results,
    }


def analyze_pair(y_prices: list[float], x_prices: list[float],
                 y_sym: str = "Y", x_sym: str = "X") -> dict:
    """Detailed analysis of one specific pair, including spread series for charting."""
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}

    n = min(len(y_prices), len(x_prices))
    if n < 60:
        return {"error": "need >= 60 aligned points"}

    y = [float(p) for p in y_prices[-n:]]
    x = [float(p) for p in x_prices[-n:]]
    r = q.test_pair(y, x)

    # Build spread series + rolling z-score for the chart
    spread = [y[i] - (r.intercept + r.hedge_ratio * x[i]) for i in range(n)]
    z_series = q.rolling_zscore(spread, min(20, n // 3))

    return {
        "pair":        f"{y_sym}/{x_sym}",
        "hedge_ratio": round(r.hedge_ratio, 4),
        "correlation": round(r.correlation, 4),
        "adf_stat":    round(r.adf_stat, 3),
        "half_life":   round(r.half_life, 1),
        "spread_z":    round(r.spread_z, 2),
        "is_cointegrated": r.is_cointegrated,
        "spread":      [round(s, 4) for s in spread],
        "zscore":      [round(z, 3) if z == z else None for z in z_series],  # NaN-safe
    }
