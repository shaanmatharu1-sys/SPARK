"""
analytics/options/engine.py
Options quant research:
  1. Strategy payoff modeling (spreads, straddles, etc.)
  2. IV rank / IV percentile
  3. Put/call flow signals
  4. Vol surface helpers (skew, term structure)

Uses the C++ greeks_module for pricing/Greeks.
"""
import sys
import os
import math
import logging

logger = logging.getLogger(__name__)

_greeks_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "greeks")
sys.path.insert(0, os.path.abspath(_greeks_path))

try:
    import greeks_module as g
    HAS_GREEKS = True
except ImportError:
    HAS_GREEKS = False


# ── 1. Strategy payoff modeling ──────────────────────────────────────────────
def payoff_diagram(legs: list[dict], spot: float, price_range: float = 0.30,
                   points: int = 61) -> dict:
    """
    Compute payoff at expiration for a multi-leg options strategy.
    legs: [{type: 'call'|'put'|'stock', strike, premium, qty (+long/-short)}]
    Returns payoff curve + break-evens + max profit/loss.
    """
    lo = spot * (1 - price_range)
    hi = spot * (1 + price_range)
    step = (hi - lo) / (points - 1)
    prices = [lo + i * step for i in range(points)]

    def leg_payoff(leg, S):
        qty = leg.get("qty", 1)
        prem = leg.get("premium", 0)
        t = leg.get("type")
        if t == "stock":
            return qty * (S - leg.get("strike", spot))  # strike = entry price
        k = leg["strike"]
        intrinsic = max(S - k, 0) if t == "call" else max(k - S, 0)
        # long pays premium (cost), short collects it
        return qty * intrinsic - qty * prem

    curve = []
    for S in prices:
        total = sum(leg_payoff(leg, S) for leg in legs)
        curve.append({"price": round(S, 2), "payoff": round(total, 2)})

    payoffs = [c["payoff"] for c in curve]
    max_profit = max(payoffs)
    max_loss = min(payoffs)

    # Break-evens: where payoff crosses zero
    breakevens = []
    for i in range(1, len(curve)):
        p0, p1 = curve[i-1]["payoff"], curve[i]["payoff"]
        if (p0 <= 0 < p1) or (p0 >= 0 > p1):
            x0, x1 = curve[i-1]["price"], curve[i]["price"]
            be = x0 + (x1 - x0) * abs(p0) / (abs(p0) + abs(p1)) if (p1 - p0) else x0
            breakevens.append(round(be, 2))

    net_premium = sum(leg.get("qty", 1) * leg.get("premium", 0)
                      for leg in legs if leg.get("type") in ("call", "put"))

    return {
        "curve":       curve,
        "max_profit":  round(max_profit, 2) if max_profit < 1e8 else None,
        "max_loss":    round(max_loss, 2),
        "breakevens":  breakevens,
        "net_premium": round(net_premium, 2),
        "spot":        spot,
    }


# Strategy templates that build legs from a few inputs
def build_strategy(name: str, spot: float, params: dict) -> list[dict]:
    """Construct legs for common strategies."""
    p = params
    if name == "long_call":
        return [{"type": "call", "strike": p["strike"], "premium": p["premium"], "qty": 1}]
    if name == "long_put":
        return [{"type": "put", "strike": p["strike"], "premium": p["premium"], "qty": 1}]
    if name == "covered_call":
        return [{"type": "stock", "strike": spot, "premium": 0, "qty": 1},
                {"type": "call", "strike": p["strike"], "premium": p["premium"], "qty": -1}]
    if name == "bull_call_spread":
        return [{"type": "call", "strike": p["long_strike"], "premium": p["long_premium"], "qty": 1},
                {"type": "call", "strike": p["short_strike"], "premium": p["short_premium"], "qty": -1}]
    if name == "bear_put_spread":
        return [{"type": "put", "strike": p["long_strike"], "premium": p["long_premium"], "qty": 1},
                {"type": "put", "strike": p["short_strike"], "premium": p["short_premium"], "qty": -1}]
    if name == "long_straddle":
        return [{"type": "call", "strike": p["strike"], "premium": p["call_premium"], "qty": 1},
                {"type": "put", "strike": p["strike"], "premium": p["put_premium"], "qty": 1}]
    if name == "long_strangle":
        return [{"type": "call", "strike": p["call_strike"], "premium": p["call_premium"], "qty": 1},
                {"type": "put", "strike": p["put_strike"], "premium": p["put_premium"], "qty": 1}]
    if name == "iron_condor":
        return [{"type": "put", "strike": p["put_long"], "premium": p["put_long_prem"], "qty": 1},
                {"type": "put", "strike": p["put_short"], "premium": p["put_short_prem"], "qty": -1},
                {"type": "call", "strike": p["call_short"], "premium": p["call_short_prem"], "qty": -1},
                {"type": "call", "strike": p["call_long"], "premium": p["call_long_prem"], "qty": 1}]
    return []


STRATEGY_LIST = [
    {"id": "long_call",        "name": "Long Call",        "outlook": "bullish"},
    {"id": "long_put",         "name": "Long Put",         "outlook": "bearish"},
    {"id": "covered_call",     "name": "Covered Call",     "outlook": "neutral-bullish"},
    {"id": "bull_call_spread", "name": "Bull Call Spread", "outlook": "bullish"},
    {"id": "bear_put_spread",  "name": "Bear Put Spread",  "outlook": "bearish"},
    {"id": "long_straddle",    "name": "Long Straddle",    "outlook": "volatility"},
    {"id": "long_strangle",    "name": "Long Strangle",    "outlook": "volatility"},
    {"id": "iron_condor",      "name": "Iron Condor",      "outlook": "range-bound"},
]


# ── 2. IV rank / IV percentile ───────────────────────────────────────────────
def iv_rank_percentile(current_iv: float, iv_history: list[float]) -> dict:
    """
    IV Rank  = (current - min) / (max - min) over the lookback window.
    IV %ile  = fraction of history below current IV.
    """
    hist = [v for v in iv_history if v is not None and v > 0]
    if not hist or current_iv is None:
        return {"iv_rank": None, "iv_percentile": None}
    lo, hi = min(hist), max(hist)
    iv_rank = (current_iv - lo) / (hi - lo) * 100 if hi > lo else 0.0
    below = sum(1 for v in hist if v < current_iv)
    iv_pct = below / len(hist) * 100
    return {
        "current_iv":    round(current_iv * 100, 2),
        "iv_rank":       round(iv_rank, 1),
        "iv_percentile": round(iv_pct, 1),
        "iv_high":       round(hi * 100, 2),
        "iv_low":        round(lo * 100, 2),
        "regime":        ("high" if iv_rank > 66 else "low" if iv_rank < 33 else "mid"),
    }


# ── 3. Put/call flow signal ──────────────────────────────────────────────────
def putcall_signal(call_volume: float, put_volume: float,
                   call_oi: float = None, put_oi: float = None) -> dict:
    """Put/call ratio + a simple sentiment read."""
    pcr_vol = put_volume / call_volume if call_volume else None
    pcr_oi = (put_oi / call_oi) if (call_oi and put_oi) else None

    # High P/C ratio = bearish positioning (often contrarian-bullish at extremes)
    sentiment = "neutral"
    if pcr_vol is not None:
        if pcr_vol > 1.2:   sentiment = "bearish_positioning"
        elif pcr_vol < 0.7: sentiment = "bullish_positioning"

    return {
        "pcr_volume": round(pcr_vol, 3) if pcr_vol else None,
        "pcr_oi":     round(pcr_oi, 3) if pcr_oi else None,
        "call_volume": call_volume,
        "put_volume":  put_volume,
        "sentiment":   sentiment,
    }


# ── 4. Skew & term structure ─────────────────────────────────────────────────
def vol_skew(strikes_ivs: list[dict], spot: float) -> dict:
    """
    Measure put/call skew from a list of {strike, iv, type}.
    25-delta skew proxy: IV at ~10% OTM put minus ~10% OTM call.
    """
    otm_puts = [s for s in strikes_ivs if s["type"] == "put" and s["strike"] < spot]
    otm_calls = [s for s in strikes_ivs if s["type"] == "call" and s["strike"] > spot]
    if not otm_puts or not otm_calls:
        return {"skew": None}

    # nearest to 10% OTM
    target_put = spot * 0.90
    target_call = spot * 1.10
    put_iv = min(otm_puts, key=lambda s: abs(s["strike"] - target_put))["iv"]
    call_iv = min(otm_calls, key=lambda s: abs(s["strike"] - target_call))["iv"]

    skew = (put_iv - call_iv) * 100
    return {
        "put_iv":  round(put_iv * 100, 2),
        "call_iv": round(call_iv * 100, 2),
        "skew":    round(skew, 2),
        "read":    ("put_skew (downside fear)" if skew > 2 else
                    "call_skew (upside demand)" if skew < -2 else "flat"),
    }
