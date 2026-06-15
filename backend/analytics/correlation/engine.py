"""
analytics/correlation/engine.py
Correlation matrix (asset-to-asset) and macro matrix (asset-to-macro-factor).
Uses returns, not price levels, for meaningful correlations.
"""
import sys
import os
import logging

logger = logging.getLogger(__name__)

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False


def _returns(prices: list[float]) -> list[float]:
    return q.simple_returns([float(p) for p in prices if p is not None])


def correlation_matrix(universe: dict[str, list[float]]) -> dict:
    """
    Asset-to-asset return correlation matrix.
    universe: {symbol: [aligned close prices]}
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}

    symbols = [s for s, p in universe.items() if len(p) >= 30]
    if len(symbols) < 2:
        return {"error": "need >= 2 symbols", "n": len(symbols)}

    # Align lengths, compute returns
    min_len = min(len(universe[s]) for s in symbols)
    rets = {s: _returns(universe[s][-min_len:]) for s in symbols}

    # Build matrix
    matrix = []
    for s1 in symbols:
        row = []
        for s2 in symbols:
            if s1 == s2:
                row.append(1.0)
            else:
                c = q.correlation(rets[s1], rets[s2])
                row.append(round(c, 3) if c == c else None)  # NaN-safe
        matrix.append(row)

    # Find most/least correlated pairs (excluding self)
    pairs = []
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            if matrix[i][j] is not None:
                pairs.append({"pair": f"{symbols[i]}/{symbols[j]}", "corr": matrix[i][j]})
    pairs.sort(key=lambda p: p["corr"], reverse=True)

    return {
        "symbols":      symbols,
        "matrix":       matrix,
        "most_correlated":  pairs[:5],
        "least_correlated": pairs[-5:][::-1] if len(pairs) >= 5 else [],
    }


# Macro factors to correlate assets against (FRED series the backend already pulls)
MACRO_FACTORS = {
    "DGS10":      "10Y Yield",
    "DGS2":       "2Y Yield",
    "VIXCLS":     "VIX",
    "DCOILWTICO": "WTI Oil",
    "DEXUSEU":    "EUR/USD",
    "T10Y2Y":     "2s10s Spread",
}


def macro_matrix(asset_universe: dict[str, list[float]],
                 macro_series: dict[str, list[float]]) -> dict:
    """
    Asset-to-macro-factor correlation matrix.
    asset_universe: {symbol: [close prices]}
    macro_series:   {factor_id: [values]}   (already fetched from FRED)
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}

    assets = [s for s, p in asset_universe.items() if len(p) >= 30]
    factors = [f for f, v in macro_series.items() if len(v) >= 30]
    if not assets or not factors:
        return {"error": "insufficient asset or macro data",
                "assets": len(assets), "factors": len(factors)}

    matrix = []
    for sym in assets:
        a_ret = _returns(asset_universe[sym])
        row = []
        for fac in factors:
            f_ret = _returns(macro_series[fac])
            # Align to common length
            n = min(len(a_ret), len(f_ret))
            if n < 20:
                row.append(None)
                continue
            c = q.correlation(a_ret[-n:], f_ret[-n:])
            row.append(round(c, 3) if c == c else None)
        matrix.append(row)

    return {
        "assets":        assets,
        "factors":       [MACRO_FACTORS.get(f, f) for f in factors],
        "factor_ids":    factors,
        "matrix":        matrix,
    }
