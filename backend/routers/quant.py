"""
routers/quant.py — Quant analytics endpoints: signals + backtesting
"""
from fastapi import APIRouter, Query
from services.polygon_client import fetch_agg_bars
from analytics.signals.engine import compute_signals
from analytics.backtest.strategies import run_strategy, STRATEGY_META
from analytics.backtest.strategies import run_custom, INDICATOR_META
from analytics import indicators as ind
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


@router.get("/indicators/{symbol}/series")
async def indicator_series(
    symbol:      str,
    types:       str   = Query(default="sma"),  # comma-separated: sma,ema,rsi,macd,bbands
    multiplier:  int   = Query(default=1),
    timespan:    str   = Query(default="day"),
    limit:       int   = Query(default=390),
    sma_period:  int   = Query(default=20),
    ema_period:  int   = Query(default=20),
    rsi_period:  int   = Query(default=14),
    macd_fast:   int   = Query(default=12),
    macd_slow:   int   = Query(default=26),
    macd_signal: int   = Query(default=9),
    bbands_period: int = Query(default=20),
    bbands_std:  float = Query(default=2.0),
):
    """
    GET /quant/indicators/AAPL/series?types=sma,rsi,macd&multiplier=1&timespan=minute&limit=390
    Time-aligned indicator series for charting — pass the SAME multiplier/timespan/limit
    the chart used for /quotes/{symbol}/bars so timestamps line up exactly.
    """
    bars = await fetch_agg_bars(symbol.upper(), multiplier, timespan, None, None, limit)
    closes = [b["c"] for b in bars if b.get("c") is not None]
    times  = [b["t"] for b in bars if b.get("c") is not None]

    def zip_series(values):
        return [{"t": t, "v": (v if v == v else None)} for t, v in zip(times, values)]

    out = {"symbol": symbol.upper(), "n": len(closes)}
    requested = {t.strip() for t in types.split(",") if t.strip()}

    if "sma" in requested:
        out["sma"] = zip_series(ind.sma(closes, sma_period))
    if "ema" in requested:
        out["ema"] = zip_series(ind.ema(closes, ema_period))
    if "rsi" in requested:
        out["rsi"] = zip_series(ind.rsi(closes, rsi_period))
    if "macd" in requested:
        m = ind.macd(closes, macd_fast, macd_slow, macd_signal)
        out["macd"] = {k: zip_series(v) for k, v in m.items()}
    if "bbands" in requested:
        bb = ind.bollinger_bands(closes, bbands_period, bbands_std)
        out["bbands"] = {k: zip_series(v) for k, v in bb.items()}

    return out


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
