"""
analytics/signals/engine.py
Statistical signal engine — wraps the C++ quant core into per-symbol signal panels.

Signals computed:
  - Price z-score (mean-reversion candidate)
  - Momentum (risk-adjusted, multi-lookback)
  - Realized vol + vol regime
  - Mean-reversion diagnostics (OU half-life, Hurst)
  - Bollinger %B
  - Composite signal score in [-1, 1]
"""
import sys
import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Import the compiled C++ quant module
_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError as e:
    logger.warning(f"[signals] C++ quant_module not compiled: {e}")
    HAS_QUANT = False


def compute_signals(prices: list[float], symbol: str = "") -> dict:
    """
    Compute the full statistical signal panel for a price series.
    Expects a list of closes (oldest -> newest), >= 60 points ideal.
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}
    if len(prices) < 30:
        return {"error": "insufficient data", "n": len(prices)}

    prices = [float(p) for p in prices if p is not None]
    n = len(prices)

    # ── Returns & vol ──
    log_rets = q.log_returns(prices)
    realized_vol_20 = q.realized_vol(log_rets[-20:], 252) if len(log_rets) >= 20 else None
    realized_vol_full = q.realized_vol(log_rets, 252)

    # ── Z-score (20-day) ──
    zscores = q.rolling_zscore(prices, 20)
    z_now = zscores[-1] if zscores and not _isnan(zscores[-1]) else None

    # ── Momentum: risk-adjusted return over multiple lookbacks ──
    mom = {}
    for lb in (5, 20, 60):
        if n > lb:
            ret = prices[-1] / prices[-1 - lb] - 1.0
            vol = q.realized_vol(log_rets[-lb:], 252) if len(log_rets) >= lb else None
            mom[f"{lb}d"] = {
                "return":     round(ret, 4),
                "risk_adj":   round(ret / vol, 3) if vol and vol > 0 else None,
            }

    # ── Mean-reversion diagnostics ──
    half_life = q.ou_half_life(prices[-min(n, 120):])
    hurst     = q.hurst_exponent(prices) if n >= 100 else None

    # ── Bollinger %B (20, 2σ) ──
    bb_pct = None
    if n >= 20:
        means = q.rolling_mean(prices, 20)
        stds  = q.rolling_std(prices, 20)
        if not _isnan(means[-1]) and not _isnan(stds[-1]) and stds[-1] > 0:
            upper = means[-1] + 2 * stds[-1]
            lower = means[-1] - 2 * stds[-1]
            bb_pct = (prices[-1] - lower) / (upper - lower) if upper != lower else 0.5

    # ── Vol regime classification ──
    vol_regime = _classify_vol_regime(realized_vol_20, realized_vol_full)

    # ── Composite signal score ──
    composite = _composite_score(z_now, mom, hurst, bb_pct)

    return {
        "symbol":           symbol,
        "n_obs":            n,
        "last_price":       round(prices[-1], 4),
        "zscore_20":        round(z_now, 3) if z_now is not None else None,
        "momentum":         mom,
        "realized_vol_20":  round(realized_vol_20, 4) if realized_vol_20 else None,
        "realized_vol_full":round(realized_vol_full, 4) if realized_vol_full else None,
        "vol_regime":       vol_regime,
        "ou_half_life":     round(half_life, 2) if half_life and half_life > 0 else None,
        "hurst":            round(hurst, 3) if hurst is not None and not _isnan(hurst) else None,
        "regime":           _classify_regime(hurst),
        "bollinger_pct_b":  round(bb_pct, 3) if bb_pct is not None else None,
        "composite_score":  round(composite, 3),
        "signal":           _score_to_label(composite),
    }


def _isnan(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x))


def _classify_vol_regime(vol_short, vol_long) -> str:
    if not vol_short or not vol_long or vol_long == 0:
        return "unknown"
    ratio = vol_short / vol_long
    if ratio > 1.3:  return "expanding"
    if ratio < 0.7:  return "contracting"
    return "stable"


def _classify_regime(hurst) -> str:
    if hurst is None or _isnan(hurst):
        return "unknown"
    if hurst < 0.45: return "mean-reverting"
    if hurst > 0.55: return "trending"
    return "random-walk"


def _composite_score(z, mom, hurst, bb_pct) -> float:
    """
    Combine signals into a [-1, 1] score.
    Logic adapts to regime: in mean-reverting regimes, fade z-score;
    in trending regimes, follow momentum.
    """
    score = 0.0
    weights_used = 0.0

    regime_trending = hurst is not None and not _isnan(hurst) and hurst > 0.55
    regime_reverting = hurst is not None and not _isnan(hurst) and hurst < 0.45

    # Z-score component (mean-reversion): negative z -> long signal
    if z is not None:
        z_clamped = max(-3, min(3, z))
        mr_signal = -z_clamped / 3.0
        w = 0.5 if regime_reverting else (0.15 if regime_trending else 0.3)
        score += w * mr_signal
        weights_used += w

    # Momentum component (trend-following)
    if mom.get("20d", {}).get("risk_adj") is not None:
        m = max(-2, min(2, mom["20d"]["risk_adj"]))
        mom_signal = m / 2.0
        w = 0.5 if regime_trending else (0.15 if regime_reverting else 0.3)
        score += w * mom_signal
        weights_used += w

    # Bollinger %B (mean-reversion at extremes)
    if bb_pct is not None:
        if bb_pct > 1.0:   bb_signal = -1.0
        elif bb_pct < 0.0: bb_signal = 1.0
        else:              bb_signal = (0.5 - bb_pct) * 2
        score += 0.2 * bb_signal
        weights_used += 0.2

    return score / weights_used if weights_used > 0 else 0.0


def _score_to_label(score: float) -> str:
    if score >  0.5:  return "STRONG_LONG"
    if score >  0.2:  return "LONG"
    if score < -0.5:  return "STRONG_SHORT"
    if score < -0.2:  return "SHORT"
    return "NEUTRAL"
