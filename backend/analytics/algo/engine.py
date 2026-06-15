"""
analytics/algo/engine.py
Algorithm engine — define strategies that run live against real-time data
and emit simulated orders into a paper portfolio.

An "algo" = a strategy function + universe + sizing rule + risk limits.
On each evaluation tick, the algo:
  1. pulls recent price history for its universe
  2. computes target positions from the strategy
  3. routes the deltas as simulated orders to the paper portfolio

NO REAL EXECUTION anywhere in this module.
"""
import sys
import os
import time
import logging
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False

from analytics.backtest.strategies import STRATEGIES, STRATEGY_META


@dataclass
class AlgoConfig:
    algo_id:       str
    name:          str
    strategy:      str                       # key into STRATEGIES
    universe:      list[str]
    capital:       float = 100_000.0         # capital allocated to this algo
    max_position_pct: float = 0.20           # max % of capital per name
    params:        dict = field(default_factory=dict)
    enabled:       bool = True
    created:       float = field(default_factory=time.time)


def evaluate_algo(config: AlgoConfig, price_history: dict[str, list[float]],
                  current_prices: dict[str, float]) -> dict:
    """
    Run one evaluation of an algo. Returns the target positions and the orders
    that would be sent (caller applies them to a PaperPortfolio).
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}
    if config.strategy not in STRATEGIES:
        return {"error": f"unknown strategy '{config.strategy}'"}

    strat_fn = STRATEGIES[config.strategy]
    targets = {}
    signals = {}

    for sym in config.universe:
        prices = price_history.get(sym, [])
        if len(prices) < 60:
            continue
        prices = [float(p) for p in prices if p is not None]

        # Strategy returns a position series in [-1, 1]; take the latest
        try:
            positions = strat_fn(prices, **config.params)
        except TypeError:
            positions = strat_fn(prices)
        signal = positions[-1] if positions else 0.0
        signals[sym] = round(float(signal), 3)

        # Convert signal [-1,1] -> target dollar position -> shares
        price = current_prices.get(sym)
        if not price or price <= 0:
            continue
        max_dollars = config.capital * config.max_position_pct
        target_dollars = signal * max_dollars
        target_shares = target_dollars / price
        targets[sym] = round(float(target_shares), 4)

    return {
        "algo_id":   config.algo_id,
        "ts":        time.time(),
        "signals":   signals,
        "targets":   targets,
    }


# ── Built-in algo templates the UI can instantiate ──────────────────
def default_algo_templates() -> list[dict]:
    """Templates a user can spin up with one click."""
    return [
        {
            "name":     "Mean Reversion Basket",
            "strategy": "zscore_reversion",
            "universe": ["SPY", "QQQ", "IWM"],
            "params":   {"window": 20, "entry": 1.5, "exit": 0.5},
            "blurb":    "Fades 20-day z-score extremes on major index ETFs.",
        },
        {
            "name":     "Momentum Rotation",
            "strategy": "momentum",
            "universe": ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN"],
            "params":   {"lookback": 60},
            "blurb":    "Long names with positive 60-day trend, short the rest.",
        },
        {
            "name":     "MA Crossover Trend",
            "strategy": "ma_crossover",
            "universe": ["SPY", "TSLA", "NVDA"],
            "params":   {"fast": 10, "slow": 50},
            "blurb":    "Classic 10/50 moving-average trend follower.",
        },
        {
            "name":     "Bollinger Fade",
            "strategy": "bollinger_reversion",
            "universe": ["SPY", "QQQ"],
            "params":   {"window": 20, "n_std": 2.0},
            "blurb":    "Buys lower band, sells upper band on index ETFs.",
        },
    ]


def list_strategies() -> dict:
    """Available strategies with their tunable params (for the algo builder UI)."""
    return STRATEGY_META
