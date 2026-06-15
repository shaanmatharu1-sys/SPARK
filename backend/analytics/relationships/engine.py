"""
analytics/relationships/engine.py

Builds a company-centric relationship map (Bloomberg SPLC-style): pick ONE company
and see the companies tied to it, surfaced automatically from the full universe.

Ties are layered from two free signals:
  1. Price correlation  — how closely returns co-move (statistical tie)
  2. GICS co-membership  — same sub-industry / sector (economic tie)

A blended score ranks the universe against the chosen company. Because computing
correlations across ~500 names is expensive, the correlation matrix is PRECOMPUTED
on a schedule and cached; a click then reads cached ties instantly.

NOTE: These are statistical + classification ties, NOT disclosed supplier/customer
relationships (which require paid data like FactSet Revere). The layout mirrors SPLC;
the data is the free analogue.
"""
import sys
import os
import json
import logging
import datetime
import asyncio

logger = logging.getLogger(__name__)

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))
try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False

from data_universe import UNIVERSE, SYMBOLS
from cache.redis_client import cache_get, cache_set
from services.polygon_client import fetch_agg_bars

REL_CACHE_KEY = "relationships:matrix"
RETURNS_CACHE_KEY = "relationships:returns"


async def _fetch_returns_for(symbols, days=180):
    """Fetch daily closes and convert to returns for each symbol (best-effort)."""
    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    async def one(sym):
        try:
            bars = await fetch_agg_bars(sym, 1, "day", start, today, limit=5000)
            closes = [b["c"] for b in bars if b.get("c") is not None]
            if len(closes) >= 30:
                return sym, q.simple_returns(closes)
        except Exception:
            pass
        return sym, None

    # Throttle concurrency so we don't hammer Polygon
    out = {}
    sem = asyncio.Semaphore(8)
    async def guarded(sym):
        async with sem:
            return await one(sym)
    results = await asyncio.gather(*[guarded(s) for s in symbols])
    for sym, rets in results:
        if rets is not None:
            out[sym] = rets
    return out


async def precompute_relationships(days=180):
    """
    Scheduled job: fetch returns for the universe, compute the correlation matrix,
    and cache it. Run periodically (e.g. every few hours) — NOT per request.
    """
    if not HAS_QUANT:
        logger.warning("[Relationships] quant_module missing; skipping precompute")
        return

    logger.info(f"[Relationships] Precomputing ties for {len(SYMBOLS)} symbols...")
    returns = await _fetch_returns_for(SYMBOLS, days=days)
    syms = list(returns.keys())
    if len(syms) < 10:
        logger.warning(f"[Relationships] Only {len(syms)} symbols had data; aborting")
        return

    # Align lengths
    min_len = min(len(returns[s]) for s in syms)
    aligned = {s: returns[s][-min_len:] for s in syms}

    # Pairwise correlation matrix (upper triangle, store as dict-of-dicts)
    corr = {s: {} for s in syms}
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            a, b = syms[i], syms[j]
            c = q.correlation(aligned[a], aligned[b])
            if c == c:  # not NaN
                corr[a][b] = round(c, 3)
                corr[b][a] = round(c, 3)

    payload = {
        "computed_at": datetime.datetime.utcnow().isoformat(),
        "symbols": syms,
        "corr": corr,
    }
    # Cache for 12h; refreshed on schedule
    await cache_set(REL_CACHE_KEY, payload, ttl=43200)
    logger.info(f"[Relationships] Cached ties for {len(syms)} symbols")
    return payload


def _blended_ties(center, corr_row, top_n=14):
    """
    Rank universe against `center` by a blended tie score:
      score = 0.6 * |correlation| + 0.4 * classification_affinity
    classification affinity: same sub-industry = 1.0, same sector = 0.5, else 0.
    Returns dict with supplier-side (positive corr) and customer-side split is not
    meaningful for statistical data, so we split by same-group vs cross-group.
    """
    c_sector = UNIVERSE.get(center, {}).get("sector")
    c_sub = UNIVERSE.get(center, {}).get("sub")

    scored = []
    for other, corr in corr_row.items():
        if other == center:
            continue
        o = UNIVERSE.get(other, {})
        if o.get("sub") == c_sub:
            affinity = 1.0
        elif o.get("sector") == c_sector:
            affinity = 0.5
        else:
            affinity = 0.0
        score = 0.6 * abs(corr) + 0.4 * affinity
        scored.append({
            "symbol": other,
            "name": o.get("name", other),
            "sector": o.get("sector", "Unknown"),
            "sub": o.get("sub", ""),
            "corr": corr,
            "affinity": affinity,
            "score": round(score, 3),
            "same_group": o.get("sub") == c_sub,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


async def get_company_ties(center: str, top_n: int = 14):
    """
    Return the relationship web for ONE company: its strongest ties across the
    universe, split into same-industry peers and cross-industry correlates.
    Reads the precomputed cache; triggers a compute if cache is cold.
    """
    center = center.upper()
    if center not in UNIVERSE:
        return {"error": f"{center} not in universe", "in_universe": False,
                "universe_size": len(SYMBOLS)}

    cached = await cache_get(REL_CACHE_KEY)
    if not cached:
        # Cold cache: compute now (slower first call)
        cached = await precompute_relationships()
        if not cached:
            return {"error": "could not compute relationships (no price data)"}

    corr_row = cached.get("corr", {}).get(center)
    if not corr_row:
        return {"error": f"no correlation data for {center} yet; try again shortly",
                "center": center, "computed_at": cached.get("computed_at")}

    ties = _blended_ties(center, corr_row, top_n=top_n)
    peers = [t for t in ties if t["same_group"]]
    correlates = [t for t in ties if not t["same_group"]]

    return {
        "center": center,
        "center_name": UNIVERSE[center]["name"],
        "center_sector": UNIVERSE[center]["sector"],
        "center_sub": UNIVERSE[center]["sub"],
        "peers": peers,             # same sub-industry (closest economic tie)
        "correlates": correlates,   # cross-industry, statistically tied
        "computed_at": cached.get("computed_at"),
        "universe_size": len(cached.get("symbols", [])),
    }
