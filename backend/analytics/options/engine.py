"""
analytics/options/engine.py
Options quant research:
  1. Strategy payoff modeling (spreads, straddles, etc.)
  2. IV rank / IV percentile
  3. Put/call flow signals
  4. Vol surface helpers (skew, term structure)
  5. Dealer gamma-exposure (GEX) proxy from open interest

Uses the C++ greeks_module for pricing/Greeks.
"""
import sys
import os
import math
import logging
import datetime

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
                   call_oi: float = None, put_oi: float = None,
                   pcr_history: list[float] = None) -> dict:
    """
    Put/call ratio + a sentiment read against ITS OWN trailing history for
    this symbol (percentile-based, the same approach iv_rank_percentile
    already uses correctly) rather than fixed thresholds like `> 1.2` —
    those numbers mean very different things for a name that normally
    trades PCR 0.5 vs one that normally trades PCR 1.5.
    pcr_history: past daily pcr_volume observations, oldest -> newest
    (caller maintains this — see routers/research_ext.py's options_flow,
    same rolling-cache pattern as the IV-rank history).
    """
    pcr_vol = put_volume / call_volume if call_volume else None
    pcr_oi = (put_oi / call_oi) if (call_oi and put_oi) else None

    sentiment = "neutral"
    pcr_percentile = None
    hist = [v for v in (pcr_history or []) if v is not None and v > 0]
    if pcr_vol is not None and len(hist) >= 20:
        pcr_percentile = round(sum(1 for v in hist if v < pcr_vol) / len(hist) * 100, 1)
        # High P/C ratio = bearish positioning (often contrarian-bullish at
        # extremes) — "high"/"low" now means relative to THIS symbol's own
        # range, not an arbitrary constant applied to every name.
        if pcr_percentile > 80:   sentiment = "bearish_positioning"
        elif pcr_percentile < 20: sentiment = "bullish_positioning"
    elif pcr_vol is not None:
        # Not enough history yet — fall back to the old fixed-threshold read
        # (rough, but better than no read at all while history builds).
        if pcr_vol > 1.2:   sentiment = "bearish_positioning"
        elif pcr_vol < 0.7: sentiment = "bullish_positioning"

    return {
        "pcr_volume": round(pcr_vol, 3) if pcr_vol else None,
        "pcr_oi":     round(pcr_oi, 3) if pcr_oi else None,
        "pcr_percentile": pcr_percentile,
        "history_days": len(hist),
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


# ── 5. Dealer gamma-exposure (GEX) proxy ─────────────────────────────────────
def _years_to_exp(exp_date: str) -> float | None:
    try:
        exp = datetime.datetime.strptime(exp_date, "%Y-%m-%d")
        days = (exp - datetime.datetime.now()).days
        return max(days / 365.0, 1e-4)
    except Exception:
        return None


def gamma_exposure_profile(contracts: list[dict], spot: float, r: float = 0.05,
                           dividend_yield: float = 0.0) -> dict:
    """
    Dealer gamma-exposure (GEX) proxy: converts each strike's open interest
    into a dollar-gamma exposure using OUR OWN Greeks (nobody publishes real
    dealer books for free — this is a market-wide positioning proxy, the
    same kind public GEX trackers publish, not verified dealer data).

    Customer-flow convention (the standard one public GEX trackers use):
    call open interest contributes POSITIVE dealer gamma, put open interest
    NEGATIVE — i.e. assumes dealers are net long gamma against calls and net
    short gamma against puts. A simplifying assumption, not a fact about any
    specific dealer's book.

    contracts: [{strike, type('call'/'put'), open_interest, iv, expiration}]
    Returns per-strike GEX, the total, a long/short-gamma regime read, and
    the "flip" strike where cumulative GEX (walking strikes ascending)
    changes sign — the level markets often show more/less volatility around,
    since dealers hedging long gamma dampen moves and short gamma amplifies
    them.
    """
    if not HAS_GREEKS:
        return {"error": "greeks_module not compiled"}
    if not spot or spot <= 0:
        return {"error": "invalid spot"}

    by_strike = {}
    for c in contracts:
        K, typ = c.get("strike"), c.get("type")
        oi, iv, exp = c.get("open_interest"), c.get("iv"), c.get("expiration")
        if not K or not oi or not iv or iv <= 0 or not exp:
            continue
        T = _years_to_exp(exp)
        if not T:
            continue
        is_call = str(typ).lower() == "call"
        try:
            gr = g.compute_greeks(S=spot, K=K, T=T, r=r, sigma=iv,
                                  is_call=is_call, q=dividend_yield)
        except Exception:
            continue
        # Dollar gamma per 1% underlying move, scaled by OI and the 100-share
        # contract multiplier.
        dollar_gamma = gr.gamma * oi * 100 * spot * spot * 0.01
        by_strike[K] = by_strike.get(K, 0.0) + (dollar_gamma if is_call else -dollar_gamma)

    if not by_strike:
        return {"error": "no usable contracts (need strike, type, open_interest, iv, expiration)"}

    strikes = sorted(by_strike)
    total_gex = sum(by_strike.values())

    cumulative = 0.0
    flip_strike = None
    prev_cum = prev_strike = None
    for k in strikes:
        cumulative += by_strike[k]
        if prev_cum is not None and (prev_cum < 0) != (cumulative < 0):
            span = cumulative - prev_cum
            frac = (-prev_cum / span) if span else 0.0
            flip_strike = round(prev_strike + frac * (k - prev_strike), 2)
        prev_cum, prev_strike = cumulative, k

    regime = "long_gamma" if total_gex > 0 else "short_gamma"
    return {
        "spot":        spot,
        "total_gex":   round(total_gex, 0),
        "regime":      regime,
        "flip_strike": flip_strike,
        "interpretation": (
            "Net dealer gamma is positive (long gamma): dealer hedging tends to "
            "buy dips / sell rallies, which historically dampens realized volatility."
            if regime == "long_gamma" else
            "Net dealer gamma is negative (short gamma): dealer hedging tends to "
            "sell into drops / buy into rallies, which historically amplifies moves."
        ),
        "profile":     [{"strike": k, "gex": round(by_strike[k], 0)} for k in strikes],
        "n_strikes":   len(strikes),
    }
