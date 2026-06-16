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


# ════════════════════════════════════════════════════════════════
# BUILD-YOUR-OWN ALGO — rule-based strategy composer
# ════════════════════════════════════════════════════════════════
# A custom strategy is a set of rules over indicators. Each rule:
#   {"indicator": "rsi"|"sma_ratio"|"zscore"|"momentum"|"price_vs_sma",
#    "op": "<"|">"|"cross_above"|"cross_below", "value": float, "param": int}
# Entry rules (ALL must hold) -> go long; exit rules (ANY) -> flat.

def _sma(prices, w):
    out = [float('nan')] * len(prices)
    for i in range(w - 1, len(prices)):
        out[i] = sum(prices[i - w + 1:i + 1]) / w
    return out

def _rsi(prices, w=14):
    out = [float('nan')] * len(prices)
    gains, losses = [], []
    for i in range(1, len(prices)):
        ch = prices[i] - prices[i - 1]
        gains.append(max(ch, 0)); losses.append(max(-ch, 0))
        if i >= w:
            ag = sum(gains[-w:]) / w; al = sum(losses[-w:]) / w
            rs = ag / al if al > 0 else 999
            out[i] = 100 - 100 / (1 + rs)
    return out

def _zscore(prices, w=20):
    out = [float('nan')] * len(prices)
    for i in range(w - 1, len(prices)):
        window = prices[i - w + 1:i + 1]
        m = sum(window) / w
        sd = (sum((x - m) ** 2 for x in window) / w) ** 0.5
        out[i] = (prices[i] - m) / sd if sd > 0 else 0
    return out

def _indicator_series(prices, indicator, param):
    if indicator == "rsi":          return _rsi(prices, param or 14)
    if indicator == "zscore":       return _zscore(prices, param or 20)
    if indicator == "momentum":
        p = param or 60
        return [float('nan') if i < p else (prices[i] / prices[i - p] - 1) * 100
                for i in range(len(prices))]
    if indicator == "price_vs_sma":
        sma = _sma(prices, param or 50)
        return [float('nan') if sma[i] != sma[i] else (prices[i] / sma[i] - 1) * 100
                for i in range(len(prices))]
    if indicator == "sma_ratio":
        fast = _sma(prices, max(2, (param or 50) // 5)); slow = _sma(prices, param or 50)
        return [float('nan') if (slow[i] != slow[i] or fast[i] != fast[i]) else (fast[i] / slow[i] - 1) * 100
                for i in range(len(prices))]
    return [float('nan')] * len(prices)

def _rule_holds(series, i, op, value):
    v = series[i]
    if v != v:  # NaN
        return False
    if op == "<":  return v < value
    if op == ">":  return v > value
    if op == "cross_above":
        return i > 0 and series[i-1] == series[i-1] and series[i-1] <= value < v
    if op == "cross_below":
        return i > 0 and series[i-1] == series[i-1] and series[i-1] >= value > v
    return False

def custom_strategy(prices, entry_rules, exit_rules):
    """Compile entry/exit rules into a long/flat position series."""
    n = len(prices)
    entry_series = [(_indicator_series(prices, r["indicator"], r.get("param")), r) for r in entry_rules]
    exit_series  = [(_indicator_series(prices, r["indicator"], r.get("param")), r) for r in exit_rules]
    positions = [0.0] * n
    pos = 0.0
    for i in range(n):
        if pos == 0.0 and entry_series:
            if all(_rule_holds(s, i, r["op"], r["value"]) for s, r in entry_series):
                pos = 1.0
        elif pos == 1.0 and exit_series:
            if any(_rule_holds(s, i, r["op"], r["value"]) for s, r in exit_series):
                pos = 0.0
        positions[i] = pos
    return positions

def run_custom(prices, entry_rules, exit_rules, cost_bps=1.0, ppy=252.0):
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}
    prices = [float(p) for p in prices if p is not None]
    if len(prices) < 60:
        return {"error": "need >= 60 price points"}
    positions = custom_strategy(prices, entry_rules, exit_rules)
    bt = q.backtest_signal(prices, positions, cost_bps=cost_bps, ppy=ppy)
    return {
        "strategy": "custom",
        "n_periods": len(prices),
        "equity_curve": [round(e, 5) for e in bt.equity_curve],
        "total_turnover": round(bt.total_turnover, 2),
        "stats": bt.stats.to_dict(),
        "positions": [round(p, 1) for p in positions],
    }

INDICATOR_META = {
    "rsi":          {"name": "RSI", "default_param": 14, "range": "0-100", "param_label": "period"},
    "zscore":       {"name": "Z-Score", "default_param": 20, "range": "~ -3 to 3", "param_label": "window"},
    "momentum":     {"name": "Momentum %", "default_param": 60, "range": "% return", "param_label": "lookback"},
    "price_vs_sma": {"name": "Price vs SMA %", "default_param": 50, "range": "% above/below", "param_label": "SMA period"},
    "sma_ratio":    {"name": "Fast/Slow SMA %", "default_param": 50, "range": "% spread", "param_label": "slow period"},
}
