"""
analytics/backtest/strategies.py
Strategy library — each strategy maps a price series to a position series in [-1, 1].
Positions are then fed to the C++ backtest_signal engine.
"""
import sys
import os
import numpy as np

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False


def _nan_to_zero(x):
    return 0.0 if x is None or (isinstance(x, float) and np.isnan(x)) else x


def zscore_reversion(prices: list[float], window: int = 20,
                     entry: float = 1.5, exit: float = 0.5) -> list[float]:
    """
    Mean-reversion: short when z > entry, long when z < -entry,
    flatten when |z| < exit. Position scaled by z magnitude.
    """
    z = q.rolling_zscore(prices, window)
    positions = []
    pos = 0.0
    for zi in z:
        zi = _nan_to_zero(zi)
        if zi < -entry:   pos = min(1.0, abs(zi) / 3.0)   # long
        elif zi > entry:  pos = -min(1.0, abs(zi) / 3.0)  # short
        elif abs(zi) < exit: pos = 0.0                     # flatten
        positions.append(pos)
    return positions


def momentum(prices: list[float], lookback: int = 60) -> list[float]:
    """Time-series momentum: long if trailing return > 0, short otherwise."""
    positions = []
    for i in range(len(prices)):
        if i < lookback:
            positions.append(0.0)
        else:
            ret = prices[i] / prices[i - lookback] - 1.0
            positions.append(1.0 if ret > 0 else -1.0)
    return positions


def ma_crossover(prices: list[float], fast: int = 10, slow: int = 50) -> list[float]:
    """Long when fast MA > slow MA, short otherwise."""
    mf = q.rolling_mean(prices, fast)
    ms = q.rolling_mean(prices, slow)
    positions = []
    for f, s in zip(mf, ms):
        if _nan_to_zero(f) == 0 or _nan_to_zero(s) == 0:
            positions.append(0.0)
        else:
            positions.append(1.0 if f > s else -1.0)
    return positions


def bollinger_reversion(prices: list[float], window: int = 20, n_std: float = 2.0) -> list[float]:
    """Long at lower band, short at upper band, flat in between."""
    means = q.rolling_mean(prices, window)
    stds  = q.rolling_std(prices, window)
    positions = []
    pos = 0.0
    for p, m, s in zip(prices, means, stds):
        m, s = _nan_to_zero(m), _nan_to_zero(s)
        if s == 0:
            positions.append(pos); continue
        upper, lower = m + n_std * s, m - n_std * s
        if p <= lower:   pos = 1.0
        elif p >= upper: pos = -1.0
        elif abs(p - m) < 0.25 * s: pos = 0.0  # revert to mean -> flatten
        positions.append(pos)
    return positions


STRATEGIES = {
    "zscore_reversion":     zscore_reversion,
    "momentum":             momentum,
    "ma_crossover":         ma_crossover,
    "bollinger_reversion":  bollinger_reversion,
}

STRATEGY_META = {
    "zscore_reversion":    {"name": "Z-Score Mean Reversion", "params": {"window": 20, "entry": 1.5, "exit": 0.5}},
    "momentum":            {"name": "Time-Series Momentum",   "params": {"lookback": 60}},
    "ma_crossover":        {"name": "MA Crossover",            "params": {"fast": 10, "slow": 50}},
    "bollinger_reversion": {"name": "Bollinger Reversion",     "params": {"window": 20, "n_std": 2.0}},
}


def run_strategy(name: str, prices: list[float], cost_bps: float = 1.0,
                 ppy: float = 252.0, **params) -> dict:
    """Run a named strategy and return equity curve + stats."""
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}
    if name not in STRATEGIES:
        return {"error": f"unknown strategy '{name}'", "available": list(STRATEGIES)}
    if len(prices) < 60:
        return {"error": "need >= 60 price points", "n": len(prices)}

    prices = [float(p) for p in prices if p is not None]
    positions = STRATEGIES[name](prices, **params)

    bt = q.backtest_signal(prices, positions, cost_bps=cost_bps, ppy=ppy)

    return {
        "strategy":      name,
        "n_periods":     len(prices),
        "equity_curve":  [round(e, 5) for e in bt.equity_curve],
        "strategy_returns": [round(r, 6) for r in bt.strategy_returns],
        "total_turnover": round(bt.total_turnover, 2),
        "stats":         bt.stats.to_dict(),
        "positions":     [round(p, 3) for p in positions],
    }
