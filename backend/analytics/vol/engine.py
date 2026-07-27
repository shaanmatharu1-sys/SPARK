"""
analytics/vol/engine.py
Volatility surface analytics, built on the C++ Greeks engine.

From an options chain (strikes, expirations, mid prices) plus spot, computes:
  - Per-contract implied vol (via C++ Newton-Raphson solver)
  - A fitted raw-SVI smile per expiration (analytics/vol/svi.py) — smooth,
    interpolable, and checked for butterfly (within-slice) and calendar
    (across-expiry) arbitrage, instead of just the raw scattered IV points
  - ATM term structure (IV by expiration, from the fitted smile when available)
  - Skew: risk reversal & butterfly per expiration, read off the fitted smile
  - Surface grid (expiration x moneyness) for 3D plotting
  - Summary metrics: ATM IV, skew slope, term-structure slope, arbitrage flags
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

from services.fred_client import interpolate_treasury_rate
from analytics.vol.svi import (
    fit_svi_slice, svi_smile, butterfly_arbitrage_check, calendar_arbitrage_check,
)

DEFAULT_RISK_FREE = 0.05  # fallback only, when no live Treasury curve is supplied
_SKEW_K = 0.25  # log-moneyness offset used as the risk-reversal/butterfly read points


def _years_to_exp(exp_date: str) -> float:
    try:
        exp = datetime.strptime(exp_date, "%Y-%m-%d")
        days = (exp - datetime.now()).days
        return max(days / 365.0, 1e-4)
    except Exception:
        return None


def build_surface(spot: float, contracts: list[dict], curve: dict = None,
                  dividend_yield: float = 0.0) -> dict:
    """
    contracts: list of {strike, expiration, mid, type('call'/'put')}
    curve: live Treasury yield curve from services.fred_client.fetch_yield_curve()
           (percent values, e.g. {"3M": 5.25, "1Y": 4.9, ...}). Each contract's
           IV is solved with the rate for ITS OWN time-to-expiry, interpolated
           from this curve — not a single flat rate for every expiration.
           Falls back to DEFAULT_RISK_FREE if no curve is supplied.
    dividend_yield: continuous dividend yield (decimal) for the underlying,
           passed to the Merton-adjusted solver; 0.0 for non-payers.
    Returns full vol surface analytics.
    """
    if not HAS_GREEKS:
        return {"error": "greeks_module not compiled"}
    if not spot or spot <= 0 or not contracts:
        return {"error": "need valid spot and contracts"}

    # 1. Solve IV per contract, and stash the log-moneyness/total-variance
    #    coordinates (relative to the forward, not spot) that the SVI fit
    #    needs — computed once here rather than re-derived per slice.
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
        r = interpolate_treasury_rate(curve, T) if curve else DEFAULT_RISK_FREE
        iv = gm.implied_volatility(market_price=mid, S=spot, K=K, T=T,
                                   r=r, is_call=is_call, q=dividend_yield)
        if iv and iv > 0:
            forward = float(spot * np.exp((r - dividend_yield) * T))
            points.append({
                "strike":     K,
                "expiration": exp,
                "T":          round(T, 4),
                "moneyness":  round(K / spot, 4),
                "iv":         round(iv, 4),
                "type":       typ,
                "mid":        mid,
                "_k":         float(np.log(K / forward)),
                "_w":         float(iv * iv * T),
                "_forward":   forward,
            })

    if not points:
        return {"error": "no IVs could be solved", "n_contracts": len(contracts)}

    # 2. Group by expiration: fit a raw-SVI smile per slice, derive term
    #    structure / skew from the smooth fit (falling back to the raw
    #    nearest-strike/bucket-average reads when a slice has too few
    #    strikes to fit — 5 points minimum for 5 SVI parameters).
    by_exp = {}
    for p in points:
        by_exp.setdefault(p["expiration"], []).append(p)

    term_structure = []
    skew_metrics = []
    svi_slices = []  # {expiration, T, fit} for valid fits, used for calendar check
    for exp, pts in sorted(by_exp.items()):
        pts_sorted = sorted(pts, key=lambda x: x["moneyness"])
        # Raw ATM: contract closest to moneyness 1.0 (fallback + sanity anchor)
        atm_raw = min(pts_sorted, key=lambda x: abs(x["moneyness"] - 1.0))
        T = atm_raw["T"]
        forward = atm_raw["_forward"]

        fit = fit_svi_slice([p["_k"] for p in pts_sorted], [p["_w"] for p in pts_sorted])

        svi_fit_out = None
        smile = None
        atm_iv = atm_raw["iv"]
        put_iv = call_iv = None

        if fit:
            arb = butterfly_arbitrage_check(fit)
            svi_fit_out = {
                "params":         fit["params"],
                "r_squared":      fit["r_squared"],
                "rmse_variance":  fit["rmse_variance"],
                "arbitrage_free": arb["arbitrage_free"],
                "min_g":          arb["min_g"],
            }
            svi_slices.append({"expiration": exp, "T": T, "fit": fit})

            k_lo = min(min(p["_k"] for p in pts_sorted), -_SKEW_K) - 0.05
            k_hi = max(max(p["_k"] for p in pts_sorted), _SKEW_K) + 0.05
            k_grid = np.linspace(k_lo, k_hi, 41)
            smile = [
                {"moneyness": round(float(np.exp(pt["log_moneyness"])) * forward / spot, 4),
                 "iv": pt["iv"]}
                for pt in svi_smile(fit, k_grid, T)
            ]
            atm_pt, put_pt, call_pt = svi_smile(fit, np.array([0.0, -_SKEW_K, _SKEW_K]), T)
            atm_iv, put_iv, call_iv = atm_pt["iv"], put_pt["iv"], call_pt["iv"]

        term_structure.append({
            "expiration":  exp,
            "T":           T,
            "atm_iv":      atm_iv,
            "atm_iv_raw":  atm_raw["iv"],
            "n_strikes":   len(pts_sorted),
            "svi_fit":     svi_fit_out,
        })

        # Skew from the fitted smile (log-moneyness +/-0.25 proxy for the
        # put/call wings) when available; else the old OTM-bucket average.
        if put_iv is None or call_iv is None:
            downside = [p for p in pts_sorted if 0.80 <= p["moneyness"] <= 0.98]
            upside   = [p for p in pts_sorted if 1.02 <= p["moneyness"] <= 1.20]
            if downside and upside:
                put_iv  = float(np.mean([p["iv"] for p in downside]))
                call_iv = float(np.mean([p["iv"] for p in upside]))

        if put_iv is not None and call_iv is not None:
            skew_metrics.append({
                "expiration":    exp,
                "T":             T,
                "risk_reversal": round(put_iv - call_iv, 4),   # put skew positive
                "butterfly":     round((put_iv + call_iv) / 2 - atm_iv, 4),
                "put_iv":        round(put_iv, 4),
                "call_iv":       round(call_iv, 4),
                "atm_iv":        atm_iv,
                "from_svi_fit":  fit is not None,
            })

        term_structure[-1]["smile"] = smile

    # 3. Cross-expiry calendar-arbitrage check on the fitted slices
    calendar_violations = calendar_arbitrage_check(svi_slices) if len(svi_slices) > 1 else []
    if calendar_violations:
        logger.info(f"[vol] calendar-arbitrage violations detected: {calendar_violations}")

    # 4. Summary metrics
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
    summary["calendar_arbitrage_free"] = len(calendar_violations) == 0
    summary["calendar_arbitrage_violations"] = calendar_violations
    summary["n_svi_fits"] = len(svi_slices)

    return {
        "spot":           spot,
        "n_points":       len(points),
        "term_structure": term_structure,
        "skew":           skew_metrics,
        "surface_points": [{k: v for k, v in p.items() if not k.startswith("_")}
                          for p in points],
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
