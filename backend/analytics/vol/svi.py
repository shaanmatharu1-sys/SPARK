"""
analytics/vol/svi.py
Raw-SVI (Stochastic Volatility Inspired) parametric vol smile, per Gatheral
(2004) and the arbitrage-free refinements in Gatheral & Jacquier (2013).

Why: the previous vol surface was just the raw scattered per-contract IVs —
noisy, with no interpolation between strikes and no way to tell whether the
market-implied smile is internally consistent (butterfly arbitrage) or
whether variance is decreasing with time (calendar arbitrage), which
shouldn't happen in a frictionless market.

Raw SVI total-variance parameterization, one slice per expiration:
    w(k) = a + b * ( rho * (k - m) + sqrt((k - m)^2 + sigma^2) )
where:
    k = log-moneyness = ln(K / F), F = forward price = S * exp((r - q) * T)
    w = total implied variance = iv^2 * T   (NOT iv itself — iv = sqrt(w / T))
    a       : overall variance level
    b       : angle between the put and call wings (b >= 0)
    rho     : rotation / skew (-1 < rho < 1)
    m       : horizontal shift of the smile's minimum
    sigma   : smile curvature at the minimum (sigma > 0)
"""
import numpy as np
from scipy.optimize import least_squares

# Bounds keep the fit numerically well-behaved and reject degenerate slices
# (e.g. b=0 would be a flat, non-smiling curve; |rho|->1 is a degenerate wing).
_BOUNDS_LO = np.array([-2.0,  1e-6, -0.999, -3.0, 1e-4])
_BOUNDS_HI = np.array([ 5.0,  10.0,  0.999,  3.0, 5.0])
_PARAM_NAMES = ("a", "b", "rho", "m", "sigma")


def raw_svi_variance(k, params) -> np.ndarray:
    """Total implied variance w(k) under the raw-SVI parameterization."""
    a, b, rho, m, sigma = params
    x = np.asarray(k, dtype=float) - m
    s = np.sqrt(x * x + sigma * sigma)
    return a + b * (rho * x + s)


def _svi_derivatives(k, params):
    """Analytic w, w', w'' at each k — used for the butterfly-arbitrage check."""
    a, b, rho, m, sigma = params
    x = np.asarray(k, dtype=float) - m
    s = np.sqrt(x * x + sigma * sigma)
    w = a + b * (rho * x + s)
    w1 = b * (rho + x / s)
    w2 = b * sigma * sigma / (s ** 3)
    return w, w1, w2


def _initial_guess(k: np.ndarray, w: np.ndarray) -> np.ndarray:
    w_min = max(float(np.min(w)), 1e-4)
    k_at_min = float(k[np.argmin(w)])
    return np.array([w_min * 0.9, 0.1, -0.3, k_at_min, max(0.1, float(np.std(k)) or 0.1)])


def fit_svi_slice(log_moneyness: list[float], total_variance: list[float]) -> dict | None:
    """
    Fit one raw-SVI slice (one expiration) by nonlinear least squares.
    Needs >= 5 points (5 free parameters) to be identifiable.
    Returns params + fit diagnostics, or None if the slice can't be fit.
    """
    k = np.asarray(log_moneyness, dtype=float)
    w = np.asarray(total_variance, dtype=float)
    mask = np.isfinite(k) & np.isfinite(w) & (w > 0)
    k, w = k[mask], w[mask]
    if len(k) < 5:
        return None

    x0 = np.clip(_initial_guess(k, w), _BOUNDS_LO, _BOUNDS_HI)

    def residuals(p):
        return raw_svi_variance(k, p) - w

    try:
        result = least_squares(residuals, x0, bounds=(_BOUNDS_LO, _BOUNDS_HI),
                               method="trf", max_nfev=2000)
    except Exception:
        return None
    if not result.success:
        return None

    params = result.x
    fitted = raw_svi_variance(k, params)
    ss_res = float(np.sum((w - fitted) ** 2))
    ss_tot = float(np.sum((w - np.mean(w)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else None
    rmse_iv = None
    T_implied = None  # caller supplies T; RMSE in variance units reported here
    rmse_w = float(np.sqrt(np.mean((w - fitted) ** 2)))

    return {
        "params": {name: round(float(v), 6) for name, v in zip(_PARAM_NAMES, params)},
        "n_points": int(len(k)),
        "rmse_variance": round(rmse_w, 6),
        "r_squared": round(r_squared, 4) if r_squared is not None else None,
        "_raw_params": params,  # kept for internal reuse (arbitrage checks, smile eval)
    }


def svi_smile(fit: dict, k_grid: np.ndarray, T: float) -> list[dict]:
    """Evaluate a fitted SVI slice on a grid of log-moneyness -> smooth IV curve."""
    params = fit["_raw_params"]
    w = raw_svi_variance(k_grid, params)
    w = np.clip(w, 1e-8, None)
    iv = np.sqrt(w / T)
    return [{"log_moneyness": round(float(ki), 4), "iv": round(float(ivi), 4)}
            for ki, ivi in zip(k_grid, iv)]


def butterfly_arbitrage_check(fit: dict, k_grid: np.ndarray = None) -> dict:
    """
    Gatheral's g(k) function: the slice is free of butterfly arbitrage
    (the implied risk-neutral density is non-negative everywhere) iff
    g(k) >= 0 for all k. This is the exact local no-arbitrage condition,
    not just the sufficient-but-not-necessary b(1+|rho|) <= 4/T bound.
    """
    params = fit["_raw_params"]
    if k_grid is None:
        k_grid = np.linspace(-1.5, 1.5, 121)
    w, w1, w2 = _svi_derivatives(k_grid, params)
    w = np.clip(w, 1e-8, None)
    g = (1.0 - (k_grid * w1) / (2.0 * w)) ** 2 \
        - (w1 ** 2 / 4.0) * (1.0 / w + 0.25) \
        + w2 / 2.0
    min_g = float(np.min(g))
    return {
        "arbitrage_free": bool(min_g >= -1e-6),
        "min_g": round(min_g, 6),
    }


def calendar_arbitrage_check(slice_fits: list[dict], k_grid: np.ndarray = None) -> list[dict]:
    """
    Total variance must be non-decreasing in T at every log-moneyness
    (Gatheral & Jacquier's calendar-spread-arbitrage condition) — a shorter-
    dated option can't imply LESS total variance than a longer-dated one at
    the same strike, or a calendar spread would be a risk-free arbitrage.
    slice_fits: [{expiration, T, fit}], sorted ascending by T.
    Returns violations between consecutive expiry pairs (empty if clean).
    """
    if k_grid is None:
        k_grid = np.linspace(-1.0, 1.0, 41)
    violations = []
    ordered = sorted(slice_fits, key=lambda s: s["T"])
    for prev, nxt in zip(ordered, ordered[1:]):
        w_prev = raw_svi_variance(k_grid, prev["fit"]["_raw_params"])
        w_next = raw_svi_variance(k_grid, nxt["fit"]["_raw_params"])
        gap = w_prev - w_next  # positive = violation (variance decreased with time)
        worst = float(np.max(gap))
        if worst > 1e-6:
            violations.append({
                "front": prev["expiration"], "back": nxt["expiration"],
                "max_violation": round(worst, 6),
            })
    return violations
