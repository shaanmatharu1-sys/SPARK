"""
analytics/regime/engine.py

Market-wide regime dashboard. Reuses analytics/signals/engine.py's existing
per-symbol regime math (Hurst-based trending/mean-reverting/random-walk
classification, vol regime, composite score) — this module doesn't
reimplement any of that, it just runs it across a market-wide set (SPY,
QQQ, IWM, the 11 sector ETFs) and aggregates into "what % of the market is
in which regime right now."

Breadth (advance/decline, % of the universe trending up over the last 20
sessions) is computed from the SAME cached raw per-symbol returns that
analytics/relationships/engine.py populates for the Ties feature — no
separate ~500-symbol fetch, since that data is already warm.

Macro context (VIX level/regime, yield-curve shape) reuses
services/fred_client.py's existing fetch_macro_dashboard/fetch_yield_curve
rather than re-deriving those from scratch.

Precomputed on a schedule and cached, same "compute once, serve from
cache" contract as the Ties feature — a per-request market-wide compute
would be needlessly slow for every dashboard load.
"""
import asyncio
import datetime
import logging

logger = logging.getLogger(__name__)

from analytics.signals.engine import compute_signals
from analytics.relationships.engine import RETURNS_CACHE_KEY
from services.polygon_client import fetch_agg_bars
from services.fred_client import fetch_macro_dashboard, fetch_yield_curve
from cache.redis_client import cache_get, cache_set
from config import SECTOR_ETFS

REGIME_CACHE_KEY = "regime:snapshot"
REGIME_UNIVERSE = ["SPY", "QQQ", "IWM"] + list(SECTOR_ETFS)

# Rolling history of regime snapshots — the single cached snapshot above is
# overwritten every precompute, so a shift like "60% trending -> 20% trending
# over two weeks" was previously invisible. Appending each precompute here
# (same "compute once on the schedule, serve from cache" contract) lets the
# frontend chart regime breadth / advance-decline / VIX over time instead of
# only ever showing the latest instant.
REGIME_HISTORY_KEY = "regime:history"
MAX_HISTORY_POINTS = 720  # ~30 days at hourly cadence


async def _closes_for(symbol: str, days: int = 365) -> list[float]:
    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    bars = await fetch_agg_bars(symbol.upper(), 1, "day", start, today, limit=5000)
    return [b["c"] for b in bars if b.get("c") is not None]


def _vix_regime(level):
    if level is None:
        return "unknown"
    if level < 15:
        return "low"
    if level > 25:
        return "elevated"
    return "normal"


async def precompute_market_regime():
    """Scheduled job: compute the market-wide regime snapshot and cache it."""
    sem = asyncio.Semaphore(8)

    async def one(sym):
        async with sem:
            try:
                closes = await _closes_for(sym)
            except Exception:
                return sym, None
            if len(closes) < 60:
                return sym, None
            return sym, compute_signals(closes, sym)

    results = await asyncio.gather(*[one(s) for s in REGIME_UNIVERSE])

    per_symbol = []
    counts = {"trending": 0, "mean-reverting": 0, "random-walk": 0, "unknown": 0}
    for sym, sig in results:
        if not sig or sig.get("error"):
            continue
        regime = sig.get("regime", "unknown")
        counts[regime] = counts.get(regime, 0) + 1
        per_symbol.append({
            "symbol": sym, "regime": regime, "vol_regime": sig.get("vol_regime"),
            "composite_score": sig.get("composite_score"), "hurst": sig.get("hurst"),
        })
    total = sum(counts.values()) or 1
    regime_breadth_pct = {k: round(v / total * 100, 1) for k, v in counts.items()}

    # Breadth from the shared cached universe returns (populated by
    # analytics/relationships/engine.py's precompute_relationships).
    market_breadth = None
    cached_returns = await cache_get(RETURNS_CACHE_KEY)
    if cached_returns:
        returns_map = cached_returns["returns"]
        n = len(returns_map)
        advancers = sum(1 for r in returns_map.values() if r and r[-1] > 0)
        decliners = sum(1 for r in returns_map.values() if r and r[-1] < 0)
        pct_up_20d = sum(1 for r in returns_map.values() if r and len(r) >= 20 and sum(r[-20:]) > 0)
        market_breadth = {
            "universe_size": n,
            "advancers": advancers,
            "decliners": decliners,
            "advance_decline_ratio": round(advancers / decliners, 2) if decliners else None,
            "pct_positive_20d_return": round(pct_up_20d / n * 100, 1) if n else None,
        }

    macro = await fetch_macro_dashboard()
    curve = await fetch_yield_curve()
    vix = (macro or {}).get("VIXCLS", {})
    vix_level = vix.get("value")
    spread = curve.get("2s10s") if curve else None

    payload = {
        "computed_at": datetime.datetime.utcnow().isoformat(),
        "regime_breadth_pct": regime_breadth_pct,
        "per_symbol": sorted(per_symbol, key=lambda x: x["symbol"]),
        "market_breadth": market_breadth,
        "macro": {
            "vix": vix_level,
            "vix_regime": _vix_regime(vix_level),
            "yield_curve_2s10s": spread,
            "yield_curve_shape": "inverted" if spread is not None and spread < 0 else "normal",
        },
    }
    await cache_set(REGIME_CACHE_KEY, payload, ttl=3600)
    await _append_history(payload)
    logger.info(f"[Regime] Precomputed market regime across {len(per_symbol)} symbols")
    return payload


async def _append_history(payload: dict):
    history = await cache_get(REGIME_HISTORY_KEY) or []
    mb = payload.get("market_breadth") or {}
    history.append({
        "computed_at":             payload["computed_at"],
        "regime_breadth_pct":      payload["regime_breadth_pct"],
        "advance_decline_ratio":   mb.get("advance_decline_ratio"),
        "pct_positive_20d_return": mb.get("pct_positive_20d_return"),
        "advancers":               mb.get("advancers"),
        "decliners":               mb.get("decliners"),
        "vix":                     payload.get("macro", {}).get("vix"),
    })
    history = history[-MAX_HISTORY_POINTS:]
    await cache_set(REGIME_HISTORY_KEY, history, ttl=86400 * 30)


async def get_market_regime():
    """Read the cached market-regime snapshot, computing once if cold."""
    cached = await cache_get(REGIME_CACHE_KEY)
    if cached:
        return cached
    return await precompute_market_regime()


async def get_regime_history() -> list[dict]:
    """Rolling history of regime snapshots for time-series charting."""
    return await cache_get(REGIME_HISTORY_KEY) or []
