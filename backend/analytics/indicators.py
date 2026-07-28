"""
analytics/indicators.py — Shared technical-indicator math.

SMA/RSI were previously buried inside backtest/strategies.py, used only to
drive custom-backtest entry/exit rules. They're pulled out here (and
strategies.py now imports them from here, unchanged behavior) so the same
math can back a plottable chart series via routers/quant.py, without
duplicating the formulas.

All functions take a flat list of closing prices and return a same-length,
NaN-padded list (or dict of such lists) — the caller zips these against bar
timestamps to produce a chart-ready series.
"""


def sma(prices: list[float], window: int) -> list[float]:
    out = [float('nan')] * len(prices)
    for i in range(window - 1, len(prices)):
        out[i] = sum(prices[i - window + 1:i + 1]) / window
    return out


def ema(prices: list[float], window: int) -> list[float]:
    out = [float('nan')] * len(prices)
    if len(prices) < window:
        return out
    k = 2 / (window + 1)
    seed = sum(prices[:window]) / window
    out[window - 1] = seed
    prev = seed
    for i in range(window, len(prices)):
        prev = prices[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(prices: list[float], window: int = 14) -> list[float]:
    out = [float('nan')] * len(prices)
    gains, losses = [], []
    for i in range(1, len(prices)):
        ch = prices[i] - prices[i - 1]
        gains.append(max(ch, 0)); losses.append(max(-ch, 0))
        if i >= window:
            ag = sum(gains[-window:]) / window; al = sum(losses[-window:]) / window
            rs = ag / al if al > 0 else 999
            out[i] = 100 - 100 / (1 + rs)
    return out


def macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    macd_line = [
        (f - s) if (f == f and s == s) else float('nan')
        for f, s in zip(ema_fast, ema_slow)
    ]
    # Signal line = EMA of the MACD line, computed only over its valid (non-NaN) tail.
    first_valid = next((i for i, v in enumerate(macd_line) if v == v), None)
    signal_line = [float('nan')] * len(prices)
    if first_valid is not None:
        valid_tail = macd_line[first_valid:]
        sig_tail = ema(valid_tail, signal)
        signal_line[first_valid:] = sig_tail
    histogram = [
        (m - s) if (m == m and s == s) else float('nan')
        for m, s in zip(macd_line, signal_line)
    ]
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def atr(highs: list[float], lows: list[float], closes: list[float], window: int = 14) -> list[float]:
    """Average True Range (Wilder's smoothing) from OHLC."""
    n = len(closes)
    out = [float('nan')] * n
    if n < window + 1:
        return out
    tr = [0.0] * n
    for i in range(n):
        tr[i] = (highs[i] - lows[i]) if i == 0 else max(
            highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])
        )
    seed = sum(tr[1:window + 1]) / window
    out[window] = seed
    prev = seed
    for i in range(window + 1, n):
        prev = (prev * (window - 1) + tr[i]) / window
        out[i] = prev
    return out


def adx(highs: list[float], lows: list[float], closes: list[float], window: int = 14) -> list[float]:
    """Average Directional Index (Wilder) — trend-strength, independent of direction."""
    n = len(closes)
    out = [float('nan')] * n
    if n < 2 * window + 1:
        return out

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up, down = highs[i] - highs[i - 1], lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

    def _wilder_smooth(series):
        sm = [float('nan')] * n
        seed = sum(series[1:window + 1])
        sm[window] = seed
        prev = seed
        for i in range(window + 1, n):
            prev = prev - (prev / window) + series[i]
            sm[i] = prev
        return sm

    tr_s, pdm_s, mdm_s = _wilder_smooth(tr), _wilder_smooth(plus_dm), _wilder_smooth(minus_dm)

    dx = [float('nan')] * n
    for i in range(window, n):
        if tr_s[i] and tr_s[i] > 0:
            pdi, mdi = 100 * pdm_s[i] / tr_s[i], 100 * mdm_s[i] / tr_s[i]
            denom = pdi + mdi
            dx[i] = 100 * abs(pdi - mdi) / denom if denom > 0 else 0.0

    dx_window = dx[window:window + window]
    if len(dx_window) < window or any(d != d for d in dx_window):
        return out
    adx_seed = sum(dx_window) / window
    idx0 = window + window - 1
    out[idx0] = adx_seed
    prev = adx_seed
    for i in range(idx0 + 1, n):
        if dx[i] == dx[i]:
            prev = (prev * (window - 1) + dx[i]) / window
            out[i] = prev
    return out


def bollinger_bands(prices: list[float], window: int = 20, num_std: float = 2.0) -> dict:
    mid = sma(prices, window)
    upper = [float('nan')] * len(prices)
    lower = [float('nan')] * len(prices)
    for i in range(window - 1, len(prices)):
        wpts = prices[i - window + 1:i + 1]
        m = mid[i]
        sd = (sum((x - m) ** 2 for x in wpts) / window) ** 0.5
        upper[i] = m + num_std * sd
        lower[i] = m - num_std * sd
    return {"upper": upper, "mid": mid, "lower": lower}
