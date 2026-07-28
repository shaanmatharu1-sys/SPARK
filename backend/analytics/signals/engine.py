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

from analytics.indicators import atr as _atr, adx as _adx, rsi as _rsi

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


def compute_signals(prices: list[float], symbol: str = "",
                    highs: list[float] = None, lows: list[float] = None,
                    volumes: list[float] = None, weekly_prices: list[float] = None,
                    market_regime: dict = None) -> dict:
    """
    Compute the full statistical signal panel for a price series.
    Expects a list of closes (oldest -> newest), >= 60 points ideal.

    Optional inputs widen the composite beyond price-only z-score/momentum/BB%B:
      highs/lows    -> ATR (vol-normalized S/R distance) + ADX (trend strength,
                        confirms/overrides the Hurst-based regime call)
      volumes       -> volume-confirmation: mean-reversion extremes on thin
                        volume are dampened, on heavy volume amplified
      weekly_prices -> multi-timeframe check: dampens conviction (doesn't flip
                        sign) when the daily signal disagrees with the weekly trend
      market_regime -> {"vix_regime": ..., "yield_curve_shape": ...} from
                        analytics/regime/engine.py — shifts momentum vs.
                        mean-reversion weighting with the broader market tape
                        instead of only ever looking at this one symbol
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

    # ── ATR / trend strength (ADX) / support-resistance — needs OHLC ──
    atr_14 = adx_14 = support_20d = resistance_20d = None
    dist_to_support_atr = dist_to_resistance_atr = None
    if highs and lows and len(highs) == n and len(lows) == n:
        atr_series = _atr(highs, lows, prices, 14)
        adx_series = _adx(highs, lows, prices, 14)
        atr_14 = atr_series[-1] if atr_series and not _isnan(atr_series[-1]) else None
        adx_14 = adx_series[-1] if adx_series and not _isnan(adx_series[-1]) else None
        window = min(20, n)
        support_20d = min(lows[-window:])
        resistance_20d = max(highs[-window:])
        if atr_14 and atr_14 > 0:
            dist_to_support_atr = round((prices[-1] - support_20d) / atr_14, 2)
            dist_to_resistance_atr = round((resistance_20d - prices[-1]) / atr_14, 2)

    # ── Volume confirmation: extremes on thin volume are weaker signals ──
    volume_ratio = None
    if volumes and len(volumes) == n and n >= 20:
        avg_vol_20 = sum(volumes[-20:]) / 20
        if avg_vol_20 > 0:
            volume_ratio = round(volumes[-1] / avg_vol_20, 2)

    # ── RSI divergence (diagnostic): price makes a new 14-bar extreme that
    # RSI doesn't confirm — a classic early-reversal tell ──
    rsi_divergence = None
    if n >= 20:
        rsi_series = _rsi(prices, 14)
        window = prices[-14:]
        rsi_window = rsi_series[-14:]
        if all(v == v for v in rsi_window):
            if prices[-1] <= min(window) and rsi_window[-1] > min(rsi_window):
                rsi_divergence = "bullish"
            elif prices[-1] >= max(window) and rsi_window[-1] < max(rsi_window):
                rsi_divergence = "bearish"

    # ── Multi-timeframe confirmation: does the weekly trend agree with the
    # daily 20d momentum? Doesn't flip the signal, just dampens conviction
    # when timeframes disagree (e.g. daily LONG signal, weekly downtrend) ──
    weekly_momentum_aligned = None
    if weekly_prices and len(weekly_prices) >= 5 and mom.get("20d", {}).get("return") is not None:
        wk_ret = weekly_prices[-1] / weekly_prices[-5] - 1.0
        daily_ret = mom["20d"]["return"]
        if abs(wk_ret) > 0.01 and abs(daily_ret) > 0.01:
            weekly_momentum_aligned = (wk_ret > 0) == (daily_ret > 0)

    # ── Composite signal score ──
    composite = _composite_score(
        z_now, mom, hurst, bb_pct,
        adx_14=adx_14, volume_ratio=volume_ratio,
        weekly_aligned=weekly_momentum_aligned, market_regime=market_regime,
    )

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
        "regime":           _classify_regime(hurst, adx_14),
        "bollinger_pct_b":  round(bb_pct, 3) if bb_pct is not None else None,
        "adx_14":           round(adx_14, 2) if adx_14 is not None else None,
        "atr_14":           round(atr_14, 4) if atr_14 is not None else None,
        "support_20d":      round(support_20d, 4) if support_20d is not None else None,
        "resistance_20d":   round(resistance_20d, 4) if resistance_20d is not None else None,
        "dist_to_support_atr":    dist_to_support_atr,
        "dist_to_resistance_atr": dist_to_resistance_atr,
        "volume_ratio_20d": volume_ratio,
        "rsi_divergence":   rsi_divergence,
        "weekly_momentum_aligned": weekly_momentum_aligned,
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


def _classify_regime(hurst, adx_14=None) -> str:
    # A strong ADX reading (established trend strength) confirms/overrides a
    # borderline or conflicting Hurst read rather than two independent,
    # sometimes-contradictory regime opinions being computed and never reconciled.
    if adx_14 is not None and adx_14 > 25:
        return "trending"
    if hurst is None or _isnan(hurst):
        return "unknown"
    if hurst < 0.45: return "mean-reverting"
    if hurst > 0.55: return "trending"
    return "random-walk"


def _composite_score(z, mom, hurst, bb_pct, adx_14=None, volume_ratio=None,
                     weekly_aligned=None, market_regime=None) -> float:
    """
    Combine signals into a [-1, 1] score.
    Logic adapts to regime: in mean-reverting regimes, fade z-score;
    in trending regimes, follow momentum. ADX confirms/strengthens the
    trending call; volume scales conviction on the mean-reversion legs;
    a misaligned weekly trend and an elevated-VIX market backdrop both
    dampen (never flip) the final conviction.
    """
    score = 0.0
    weights_used = 0.0

    strong_trend = adx_14 is not None and adx_14 > 25
    regime_trending = strong_trend or (hurst is not None and not _isnan(hurst) and hurst > 0.55)
    regime_reverting = (not strong_trend) and hurst is not None and not _isnan(hurst) and hurst < 0.45

    # Market-wide regime feedback: an elevated-VIX, risk-off tape favors
    # mean-reversion over momentum chasing; a low-VIX tape favors trend
    # continuation — shifts the mean-reversion/momentum weight split rather
    # than only ever looking at this one symbol's own price series.
    mr_mult, mom_mult = 1.0, 1.0
    vix_regime = (market_regime or {}).get("vix_regime")
    if vix_regime == "elevated": mr_mult, mom_mult = 1.3, 0.7
    elif vix_regime == "low":    mr_mult, mom_mult = 0.8, 1.3

    # Volume confirmation: a z-score/BB extreme on heavy volume is a
    # stronger tell than the same extreme on thin volume.
    vol_conviction = 1.0
    if volume_ratio is not None:
        if volume_ratio > 1.5: vol_conviction = min(1.4, 1.0 + (volume_ratio - 1.5) * 0.2)
        elif volume_ratio < 0.5: vol_conviction = max(0.6, volume_ratio)

    # Z-score component (mean-reversion): negative z -> long signal
    if z is not None:
        z_clamped = max(-3, min(3, z))
        mr_signal = -z_clamped / 3.0 * vol_conviction
        w = (0.5 if regime_reverting else (0.15 if regime_trending else 0.3)) * mr_mult
        score += w * mr_signal
        weights_used += w

    # Momentum component (trend-following) — blends 5d/20d/60d risk-adjusted
    # momentum instead of only the 20d lookback, so faster and slower signals
    # both have a voice (20d still dominant, since it's the regime anchor).
    mom_parts, mom_weights = [], {"5d": 0.2, "20d": 0.5, "60d": 0.3}
    for lb, w_lb in mom_weights.items():
        ra = mom.get(lb, {}).get("risk_adj")
        if ra is not None:
            mom_parts.append(w_lb * max(-2, min(2, ra)) / 2.0)
    if mom_parts:
        mom_signal = sum(mom_parts) / sum(mom_weights[lb] for lb in mom_weights if mom.get(lb, {}).get("risk_adj") is not None)
        w = (0.5 if regime_trending else (0.15 if regime_reverting else 0.3)) * mom_mult
        score += w * mom_signal
        weights_used += w

    # Bollinger %B (mean-reversion at extremes)
    if bb_pct is not None:
        if bb_pct > 1.0:   bb_signal = -1.0
        elif bb_pct < 0.0: bb_signal = 1.0
        else:              bb_signal = (0.5 - bb_pct) * 2
        w = 0.2 * mr_mult
        score += w * bb_signal * vol_conviction
        weights_used += w

    result = score / weights_used if weights_used > 0 else 0.0

    # Multi-timeframe check: daily signal disagreeing with the weekly trend
    # dampens conviction rather than being ignored (or, worse, trusted blindly).
    if weekly_aligned is False:
        result *= 0.7

    return max(-1.0, min(1.0, result))


def _score_to_label(score: float) -> str:
    if score >  0.5:  return "STRONG_LONG"
    if score >  0.2:  return "LONG"
    if score < -0.5:  return "STRONG_SHORT"
    if score < -0.2:  return "SHORT"
    return "NEUTRAL"
