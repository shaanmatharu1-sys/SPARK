"""
analytics/vol/engine.py
Volatility surface analytics, built on the C++ Greeks engine.

From an options chain (strikes, expirations, mid prices) plus spot, computes:
  - Per-contract implied vol (via C++ Newton-Raphson solver)
  - ATM term structure (IV by expiration)
  - Skew: 25-delta risk reversal & butterfly per expiration
  - Surface grid (expiration x moneyness) for 3D plotting
  - Summary metrics: ATM IV, skew slope, term-structure slope
"""
import sys
import os
import logging
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

_greeks_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "greeks")
sys.path.insert(0, os.path.abspath(_greeks_path))

try:
    import greeks_module as gm
    HAS_GREEKS = True
except ImportError:
    HAS_GREEKS = False

RISK_FREE = 0.05


def _years_to_exp(exp_date: str) -> float:
    try:
        exp = datetime.strptime(exp_date, "%Y-%m-%d")
        days = (exp - datetime.now()).days
        return max(days / 365.0, 1e-4)
    except Exception:
        return None


def build_surface(spot: float, contracts: list[dict]) -> dict:
    """
    contracts: list of {strike, expiration, mid, type('call'/'put')}
    Returns full vol surface analytics.
    """
    if not HAS_GREEKS:
        return {"error": "greeks_module not compiled"}
    if not spot or spot <= 0 or not contracts:
        return {"error": "need valid spot and contracts"}

    # 1. Solve IV per contract
    points = []
    for c in contracts:
        K = c.get("strike")
        mid = c.get("mid")
        exp = c.get("expiration")
        typ = c.get("type", "call").lower()
        if not K or not mid or mid <= 0 or not exp:
            continue
        T = _years_to_exp(exp)
        if not T:
            continue
        is_call = typ == "call"
        iv = gm.implied_volatility(market_price=mid, S=spot, K=K, T=T,
                                   r=RISK_FREE, is_call=is_call)
        if iv and iv > 0:
            points.append({
                "strike":     K,
                "expiration": exp,
                "T":          round(T, 4),
                "moneyness":  round(K / spot, 4),
                "iv":         round(iv, 4),
                "type":       typ,
                "mid":        mid,
            })

    if not points:
        return {"error": "no IVs could be solved", "n_contracts": len(contracts)}

    # 2. Group by expiration for term structure & skew
    by_exp = {}
    for p in points:
        by_exp.setdefault(p["expiration"], []).append(p)

    term_structure = []
    skew_metrics = []
    for exp, pts in sorted(by_exp.items()):
        pts_sorted = sorted(pts, key=lambda x: x["moneyness"])
        # ATM IV: contract closest to moneyness 1.0
        atm = min(pts_sorted, key=lambda x: abs(x["moneyness"] - 1.0))
        T = atm["T"]

        term_structure.append({
            "expiration": exp,
            "T":          T,
            "atm_iv":     atm["iv"],
            "n_strikes":  len(pts_sorted),
        })

        # Skew: compare downside (OTM puts) vs upside (OTM calls)
        downside = [p for p in pts_sorted if 0.80 <= p["moneyness"] <= 0.98]
        upside   = [p for p in pts_sorted if 1.02 <= p["moneyness"] <= 1.20]
        if downside and upside:
            put_iv  = np.mean([p["iv"] for p in downside])
            call_iv = np.mean([p["iv"] for p in upside])
            rr = round(put_iv - call_iv, 4)   # risk reversal (put skew positive)
            bf = round((put_iv + call_iv) / 2 - atm["iv"], 4)  # butterfly
            skew_metrics.append({
                "expiration":    exp,
                "T":             T,
                "risk_reversal": rr,
                "butterfly":     bf,
                "put_iv":        round(put_iv, 4),
                "call_iv":       round(call_iv, 4),
                "atm_iv":        atm["iv"],
            })

    # 3. Summary metrics
    summary = {}
    if term_structure:
        ts_sorted = sorted(term_structure, key=lambda x: x["T"])
        summary["atm_iv_front"] = ts_sorted[0]["atm_iv"]
        summary["atm_iv_back"]  = ts_sorted[-1]["atm_iv"]
        # Term structure slope: contango (back>front) or backwardation
        if len(ts_sorted) > 1:
            summary["term_slope"] = round(ts_sorted[-1]["atm_iv"] - ts_sorted[0]["atm_iv"], 4)
            summary["term_shape"] = "contango" if summary["term_slope"] > 0 else "backwardation"
    if skew_metrics:
        front_skew = sorted(skew_metrics, key=lambda x: x["T"])[0]
        summary["front_risk_reversal"] = front_skew["risk_reversal"]
        summary["skew_direction"] = ("put skew" if front_skew["risk_reversal"] > 0
                                     else "call skew")

    return {
        "spot":           spot,
        "n_points":       len(points),
        "term_structure": term_structure,
        "skew":           skew_metrics,
        "surface_points": points,
        "summary":        summary,
    }


def iv_rank(current_iv: float, iv_history: list[float]) -> dict:
    """
    IV Rank & IV Percentile — where does current IV sit vs its trailing range?
    iv_history: list of past ATM IV observations.
    """
    if not iv_history or current_iv is None:
        return {"iv_rank": None, "iv_percentile": None}
    lo, hi = min(iv_history), max(iv_history)
    rank = (current_iv - lo) / (hi - lo) * 100 if hi > lo else 50.0
    pct = sum(1 for x in iv_history if x < current_iv) / len(iv_history) * 100
    return {
        "iv_rank":       round(rank, 1),
        "iv_percentile": round(pct, 1),
        "iv_high":       round(hi, 4),
        "iv_low":        round(lo, 4),
        "current_iv":    round(current_iv, 4),
    }
