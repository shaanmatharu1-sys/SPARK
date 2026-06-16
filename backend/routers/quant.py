"""
routers/quant.py — Quant analytics endpoints: signals + backtesting
"""
from fastapi import APIRouter, Query
from services.polygon_client import fetch_agg_bars
from analytics.signals.engine import compute_signals
from analytics.backtest.strategies import run_strategy, STRATEGY_META
from analytics.backtest.strategies import run_custom, INDICATOR_META
from fastapi import Body
import datetime

router = APIRouter(prefix="/quant", tags=["quant"])


async def _get_closes(symbol: str, days: int = 365, timespan: str = "day") -> list[float]:
    """Pull close prices from Polygon agg bars."""
    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    bars = await fetch_agg_bars(symbol.upper(), 1, timespan, start, today, limit=5000)
    return [b["c"] for b in bars if b.get("c") is not None]


@router.get("/signals/{symbol}")
async def get_signals(symbol: str, days: int = Query(default=365)):
    """
    GET /quant/signals/AAPL — Full statistical signal panel.
    z-score, momentum, vol regime, mean-reversion diagnostics, composite score.
    """
    closes = await _get_closes(symbol, days)
    if len(closes) < 30:
        return {"error": "insufficient price history", "symbol": symbol, "n": len(closes)}
    return compute_signals(closes, symbol.upper())


@router.get("/strategies")
async def list_strategies():
    """GET /quant/strategies — Available backtest strategies and their params."""
    return STRATEGY_META


@router.get("/indicators")
async def list_indicators():
    """GET /quant/indicators — Indicators available for build-your-own algo."""
    return INDICATOR_META


@router.post("/backtest/{symbol}/custom")
async def backtest_custom(
    symbol: str,
    days:     int = Query(default=730),
    cost_bps: float = Query(default=1.0),
    rules: dict = Body(...),
):
    """
    POST /quant/backtest/AAPL/custom — Build-your-own-algo backtest.
    Body: {"entry": [{indicator, op, value, param}], "exit": [...]}
    """
    closes = await _get_closes(symbol, days, "day")
    if len(closes) < 60:
        return {"error": "need >= 60 price points", "symbol": symbol, "n": len(closes)}
    result = run_custom(closes, rules.get("entry", []), rules.get("exit", []),
                        cost_bps=cost_bps)
    result["symbol"] = symbol.upper()
    return result


@router.get("/backtest/{symbol}")
async def backtest(
    symbol:    str,
    strategy:  str   = Query(default="zscore_reversion"),
    days:      int   = Query(default=365),
    cost_bps:  float = Query(default=1.0),
    timespan:  str   = Query(default="day"),
):
    """
    GET /quant/backtest/AAPL?strategy=momentum&days=730&cost_bps=2
    Runs a strategy backtest and returns equity curve + full performance stats.
    """
    ppy = 252.0 if timespan == "day" else 252.0 * 390  # rough for minute bars
    closes = await _get_closes(symbol, days, timespan)
    if len(closes) < 60:
        return {"error": "need >= 60 price points", "symbol": symbol, "n": len(closes)}

    result = run_strategy(strategy, closes, cost_bps=cost_bps, ppy=ppy)
    result["symbol"] = symbol.upper()
    return result


@router.get("/backtest/{symbol}/compare")
async def backtest_compare(
    symbol:   str,
    days:     int   = Query(default=365),
    cost_bps: float = Query(default=1.0),
):
    """
    GET /quant/backtest/AAPL/compare — Run ALL strategies on one symbol,
    return equity curves + stats for side-by-side comparison.
    """
    closes = await _get_closes(symbol, days)
    if len(closes) < 60:
        return {"error": "need >= 60 price points", "symbol": symbol, "n": len(closes)}

    results = {}
    for strat in STRATEGY_META:
        r = run_strategy(strat, closes, cost_bps=cost_bps)
        if "error" not in r:
            results[strat] = {
                "name":         STRATEGY_META[strat]["name"],
                "equity_curve": r["equity_curve"],
                "stats":        r["stats"],
            }

    # Buy & hold benchmark
    bh_equity = [round(closes[i] / closes[0], 5) for i in range(len(closes))]
    results["buy_hold"] = {
        "name": "Buy & Hold",
        "equity_curve": bh_equity,
        "stats": _buy_hold_stats(closes),
    }

    return {"symbol": symbol.upper(), "n_periods": len(closes), "results": results}


def _buy_hold_stats(closes: list[float]) -> dict:
    import sys, os
    _qp = os.path.join(os.path.dirname(__file__), "..", "cpp_ext", "quant")
    sys.path.insert(0, os.path.abspath(_qp))
    import quant_module as q
    rets = q.simple_returns(closes)
    return q.perf_stats(rets, 0.0, 252.0).to_dict()
