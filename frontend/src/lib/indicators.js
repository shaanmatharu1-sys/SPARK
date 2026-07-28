// lib/indicators.js — client-side technical-indicator math, mirroring
// backend/analytics/indicators.py formula-for-formula.
//
// Computed client-side (not via a backend round-trip) so indicator overlays
// stay perfectly time-aligned with the candles already loaded for the chart,
// and so live-tick updates are a cheap local recompute rather than a network
// call on every tick.

export function sma(prices, window) {
  const out = new Array(prices.length).fill(NaN)
  for (let i = window - 1; i < prices.length; i++) {
    let sum = 0
    for (let j = i - window + 1; j <= i; j++) sum += prices[j]
    out[i] = sum / window
  }
  return out
}

export function ema(prices, window) {
  const out = new Array(prices.length).fill(NaN)
  if (prices.length < window) return out
  const k = 2 / (window + 1)
  let seed = 0
  for (let i = 0; i < window; i++) seed += prices[i]
  seed /= window
  out[window - 1] = seed
  let prev = seed
  for (let i = window; i < prices.length; i++) {
    prev = prices[i] * k + prev * (1 - k)
    out[i] = prev
  }
  return out
}

export function rsi(prices, window = 14) {
  const out = new Array(prices.length).fill(NaN)
  const gains = [], losses = []
  for (let i = 1; i < prices.length; i++) {
    const ch = prices[i] - prices[i - 1]
    gains.push(Math.max(ch, 0)); losses.push(Math.max(-ch, 0))
    if (i >= window) {
      const ag = gains.slice(-window).reduce((a, b) => a + b, 0) / window
      const al = losses.slice(-window).reduce((a, b) => a + b, 0) / window
      const rs = al > 0 ? ag / al : 999
      out[i] = 100 - 100 / (1 + rs)
    }
  }
  return out
}

export function macd(prices, fast = 12, slow = 26, signal = 9) {
  const emaFast = ema(prices, fast)
  const emaSlow = ema(prices, slow)
  const macdLine = prices.map((_, i) =>
    (!isNaN(emaFast[i]) && !isNaN(emaSlow[i])) ? emaFast[i] - emaSlow[i] : NaN)
  const firstValid = macdLine.findIndex(v => !isNaN(v))
  const signalLine = new Array(prices.length).fill(NaN)
  if (firstValid !== -1) {
    const tail = ema(macdLine.slice(firstValid), signal)
    for (let i = 0; i < tail.length; i++) signalLine[firstValid + i] = tail[i]
  }
  const histogram = macdLine.map((m, i) =>
    (!isNaN(m) && !isNaN(signalLine[i])) ? m - signalLine[i] : NaN)
  return { macd: macdLine, signal: signalLine, histogram }
}

export function bollingerBands(prices, window = 20, numStd = 2) {
  const mid = sma(prices, window)
  const upper = new Array(prices.length).fill(NaN)
  const lower = new Array(prices.length).fill(NaN)
  for (let i = window - 1; i < prices.length; i++) {
    const m = mid[i]
    let variance = 0
    for (let j = i - window + 1; j <= i; j++) variance += (prices[j] - m) ** 2
    const sd = Math.sqrt(variance / window)
    upper[i] = m + numStd * sd
    lower[i] = m - numStd * sd
  }
  return { upper, mid, lower }
}

// Volume-weighted average price, reset at the start of each local calendar
// day — the standard intraday reference level. bars: [{t, h, l, c, v}].
export function vwap(bars) {
  const out = new Array(bars.length).fill(NaN)
  let cumPV = 0, cumV = 0, lastDay = null
  for (let i = 0; i < bars.length; i++) {
    const b = bars[i]
    const day = new Date(b.t * 1000).toDateString()
    if (day !== lastDay) { cumPV = 0; cumV = 0; lastDay = day }
    const typical = (b.h + b.l + b.c) / 3
    const vol = b.v || 0
    cumPV += typical * vol
    cumV += vol
    out[i] = cumV > 0 ? cumPV / cumV : NaN
  }
  return out
}

// Average True Range (Wilder's smoothing) — used for stop-loss sizing and
// breakout confirmation. bars: [{t, h, l, c}].
export function atr(bars, window = 14) {
  const n = bars.length
  const out = new Array(n).fill(NaN)
  if (n < window + 1) return out
  const tr = new Array(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    const b = bars[i]
    tr[i] = i === 0 ? b.h - b.l : Math.max(
      b.h - b.l,
      Math.abs(b.h - bars[i - 1].c),
      Math.abs(b.l - bars[i - 1].c),
    )
  }
  let seed = 0
  for (let i = 1; i <= window; i++) seed += tr[i]
  out[window] = seed / window
  for (let i = window + 1; i < n; i++) out[i] = (out[i - 1] * (window - 1) + tr[i]) / window
  return out
}
