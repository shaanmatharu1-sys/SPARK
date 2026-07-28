import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createChartEngine } from '../../lib/canvasChart'
import { useBars } from '../../hooks/useMarketData'
import { useWebSocket } from '../../hooks/useWebSocket'
import { sma, ema, rsi, macd, bollingerBands, vwap, atr } from '../../lib/indicators'
import { useDrawingTools } from './ChartDrawingLayer'

const TIMESPANS = [
  { label: '1m',  multiplier: 1,  timespan: 'minute', limit: 390 },
  { label: '5m',  multiplier: 5,  timespan: 'minute', limit: 390 },
  { label: '30m', multiplier: 30, timespan: 'minute', limit: 390 },
  { label: '1D',  multiplier: 1,  timespan: 'minute', limit: 390 },
  // 5-min bars capped at limit=390 (same as 1D) only spans ~2 trading days once
  // extended-hours bars are included — bound this by an explicit 7-calendar-day
  // getFromDate (like YTD/All below) instead of relying on limit x bar-size math,
  // and raise the limit so a full week of 5-min bars (even 24h-inclusive) fits.
  { label: '1W',  multiplier: 5,  timespan: 'minute', limit: 1000, getFromDate: () => {
      const d = new Date(); d.setDate(d.getDate() - 7); return d.toISOString().slice(0, 10)
    } },
  { label: '1M',  multiplier: 1,  timespan: 'day',    limit: 30 },
  { label: '3M',  multiplier: 1,  timespan: 'day',    limit: 65 },
  { label: 'YTD', multiplier: 1,  timespan: 'day',    limit: 366, getFromDate: () => `${new Date().getFullYear()}-01-01` },
  { label: '1Y',  multiplier: 1,  timespan: 'week',   limit: 52 },
  // "All Time" depth depends on the live Polygon plan's historical entitlement —
  // this asks for as far back as the API will give us, not a guaranteed range.
  { label: 'All', multiplier: 1,  timespan: 'month',  limit: 1000, getFromDate: () => '1990-01-01' },
]
const DEFAULT_TIMESPAN = TIMESPANS.find(t => t.label === '1D')

const INDICATORS = [
  { key: 'sma',    label: 'SMA 20' },
  { key: 'ema',    label: 'EMA 20' },
  { key: 'bbands', label: 'BB 20' },
  { key: 'vwap',   label: 'VWAP' },
  { key: 'rsi',    label: 'RSI 14' },
  { key: 'macd',   label: 'MACD' },
  { key: 'atr',    label: 'ATR 14' },
]

const CHART_TYPES = [
  { key: 'candle', label: 'Candles' },
  { key: 'bar',    label: 'Bars' },
  { key: 'line',   label: 'Line' },
]

// Canvas can't read CSS custom properties, so these mirror the theme tokens
// noted alongside each one (matches the convention already used across this
// codebase's other canvas components — SupplyMap, Network, etc).
const COLORS = {
  grid:             '#1A3354', // var(--border)
  border:           '#1A3354', // var(--border)
  text:             '#E8EAED', // var(--text-primary)
  dimText:          '#5E789A', // var(--text-dim)
  up:               '#3FB68B', // var(--green)
  down:             '#E0556B', // var(--red)
  volUp:            '#3FB68B4D', // var(--green) ~30% alpha
  volDown:          '#E0556B4D', // var(--red) ~30% alpha
  line:             '#6BA3D4', // var(--steel-bright)
  crosshair:        '#6BA3D480', // var(--steel-bright) ~50% alpha
  crosshairLabelBg: '#16314F', // var(--bg-raised)
}

function zip(times, values) {
  const out = []
  for (let i = 0; i < times.length; i++) {
    if (values[i] === undefined || isNaN(values[i])) continue
    out.push({ t: times[i], v: values[i] })
  }
  return out
}

function pctChange(closes) {
  const base = closes.find(c => c != null)
  if (!base) return closes.map(() => NaN)
  return closes.map(c => (c == null ? NaN : (c / base - 1) * 100))
}

export default function PriceChart({ symbol = 'SPY', initialTimeframe }) {
  const containerRef = useRef(null)
  const canvasElRef   = useRef(null)
  const engineRef     = useRef(null)
  const lastBarTime   = useRef(null)
  const closesRef     = useRef([])
  const timesRef      = useRef([])
  const barsRef       = useRef([]) // full OHLCV, needed by volume-aware indicators (VWAP/ATR)

  const [ts, setTs] = useState(() => TIMESPANS.find(t => t.label === initialTimeframe) || DEFAULT_TIMESPAN)
  const [mode, setMode] = useState('candle')
  const [showVolume, setShowVolume] = useState(true)

  const fromDate = ts.getFromDate ? ts.getFromDate() : null
  const { data: bars, loading } = useBars(symbol, ts.multiplier, ts.timespan, ts.limit, fromDate)

  const [activeIndicators, setActiveIndicators] = useState({})
  const toggleIndicator = (key) => setActiveIndicators(a => ({ ...a, [key]: !a[key] }))

  const [compareInput, setCompareInput] = useState('')
  const [compareSymbol, setCompareSymbol] = useState(null)
  const { data: compareBars } = useBars(compareSymbol, ts.multiplier, ts.timespan, ts.limit, fromDate)

  const { canvasRef: drawCanvasRef, activeTool, selectTool, drawings, clearDrawings, onCanvasClick } =
    useDrawingTools(engineRef, engineRef, containerRef, symbol)

  // Live tick updates only make sense for the 1-minute intraday view — the websocket's
  // "AM" events are always 1-minute bars, so applying them to a 5m/30m/day/week series
  // would draw a spurious extra candle instead of updating the right bucket.
  const isIntraday = ts.timespan === 'minute' && ts.multiplier === 1

  // Rebuild every indicator overlay/sub-pane from the closes/times currently
  // in closesRef/timesRef. Called on bulk data load and whenever the active-
  // indicator toggles (or a live tick) change; cheap enough to just redo.
  const rebuildIndicators = useCallback(() => {
    const engine = engineRef.current
    const closes = closesRef.current, times = timesRef.current
    if (!engine || !closes.length) return

    const overlays = []
    if (activeIndicators.sma) overlays.push({ color: '#6BA3D4', points: zip(times, sma(closes, 20)) }) // var(--steel-bright)
    if (activeIndicators.ema) overlays.push({ color: '#E0C168', points: zip(times, ema(closes, 20)) }) // var(--gold-bright)
    if (activeIndicators.bbands) {
      const bb = bollingerBands(closes, 20, 2)
      overlays.push({ color: '#9B8Bd4', points: zip(times, bb.upper) }) // var(--purple)
      overlays.push({ color: '#9B8Bd4', points: zip(times, bb.lower) }) // var(--purple)
    }
    if (activeIndicators.vwap) {
      overlays.push({ color: '#5BB8C4', points: zip(times, vwap(barsRef.current)) }) // var(--cyan)
    }
    engine.setOverlays(overlays)

    const subPanes = []
    if (activeIndicators.rsi) {
      subPanes.push({
        label: 'RSI 14',
        series: [{ type: 'line', color: '#E0C168', points: zip(times, rsi(closes, 14)) }], // var(--gold-bright)
      })
    }
    if (activeIndicators.macd) {
      const m = macd(closes, 12, 26, 9)
      subPanes.push({
        label: 'MACD',
        series: [
          { type: 'histogram', points: zip(times, m.histogram), upColor: '#3FB68B99', downColor: '#E0556B99' }, // var(--green)/var(--red) ~60% alpha
          { type: 'line', color: '#6BA3D4', points: zip(times, m.macd) },   // var(--steel-bright)
          { type: 'line', color: '#C9A84C', points: zip(times, m.signal) }, // var(--gold)
        ],
      })
    }
    if (activeIndicators.atr) {
      subPanes.push({
        label: 'ATR 14',
        series: [{ type: 'line', color: '#E0556B', points: zip(times, atr(barsRef.current, 14)) }], // var(--red)
      })
    }
    engine.setSubPanes(subPanes)
  }, [activeIndicators])

  const onTick = useCallback((msg) => {
    if (msg.type !== 'bar' || msg.symbol !== symbol) return
    const engine = engineRef.current
    if (!engine) return
    const time = Math.floor(msg.ts / 1000)
    if (lastBarTime.current != null && time < lastBarTime.current) return
    lastBarTime.current = time
    engine.updateLastBar({ t: time, o: msg.open, h: msg.high, l: msg.low, c: msg.close, v: msg.volume })

    const closes = closesRef.current, times = timesRef.current, liveBars = barsRef.current
    const bar = { t: time, o: msg.open, h: msg.high, l: msg.low, c: msg.close, v: msg.volume }
    if (times.length && times[times.length - 1] === time) {
      closes[closes.length - 1] = msg.close
      liveBars[liveBars.length - 1] = bar
    } else {
      closes.push(msg.close); times.push(time); liveBars.push(bar)
    }
    rebuildIndicators()
  }, [symbol, rebuildIndicators])

  useWebSocket(isIntraday ? `/quotes/ws?symbols=${symbol}` : null, onTick, isIntraday)

  // Init the chart engine once per mount.
  useEffect(() => {
    if (!canvasElRef.current || !containerRef.current) return
    const engine = createChartEngine(canvasElRef.current, COLORS)
    engineRef.current = engine
    const ro = new ResizeObserver(() => engine.resize())
    ro.observe(containerRef.current)
    return () => { ro.disconnect(); engine.destroy() }
  }, [])

  useEffect(() => { engineRef.current?.setMode(mode) }, [mode])
  useEffect(() => { engineRef.current?.setShowVolume(showVolume) }, [showVolume])

  // Load bulk bar data into the engine.
  useEffect(() => {
    if (!bars || !engineRef.current) return
    const engineBars = bars.map(b => ({ t: b.t / 1000, o: b.o, h: b.h, l: b.l, c: b.c, v: b.v }))
    engineRef.current.setData(engineBars)
    lastBarTime.current = engineBars.length ? engineBars[engineBars.length - 1].t : null
    closesRef.current = engineBars.map(b => b.c)
    timesRef.current  = engineBars.map(b => b.t)
    barsRef.current   = engineBars
    rebuildIndicators()
  }, [bars])

  useEffect(() => { rebuildIndicators() }, [activeIndicators])

  // Compare/overlay: normalized (% change from first bar in range), drawn with
  // its own independently-scaled range so it doesn't distort the price axis.
  useEffect(() => {
    const engine = engineRef.current
    if (!engine) return
    if (!compareSymbol || !compareBars?.length) { engine.setCompareSeries(null); return }
    const closes = compareBars.map(b => b.c)
    const times  = compareBars.map(b => b.t / 1000)
    engine.setCompareSeries({ color: '#5BB8C4', points: zip(times, pctChange(closes)) }) // var(--cyan)
  }, [compareSymbol, compareBars])

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: 6 }}>
        <span className="title">{symbol} — Chart</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          {CHART_TYPES.map(c => (
            <button key={c.key} className={`btn ${mode === c.key ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px' }}
              onClick={() => setMode(c.key)}>
              {c.label}
            </button>
          ))}
          <button className={`btn ${showVolume ? 'active' : ''}`}
            style={{ fontSize: 9, padding: '2px 7px' }}
            onClick={() => setShowVolume(v => !v)}>
            Vol
          </button>

          {INDICATORS.map(i => (
            <button
              key={i.key}
              onClick={() => toggleIndicator(i.key)}
              className={`btn ${activeIndicators[i.key] ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px' }}
            >
              {i.label}
            </button>
          ))}
          <input
            className="input"
            placeholder="+ Compare"
            value={compareInput}
            onChange={e => setCompareInput(e.target.value.toUpperCase())}
            onKeyDown={e => {
              if (e.key === 'Enter') setCompareSymbol(compareInput || null)
              if (e.key === 'Escape') { setCompareInput(''); setCompareSymbol(null) }
            }}
            style={{ width: 70, fontSize: 10, padding: '2px 6px' }}
          />
          {compareSymbol && (
            <span style={{ fontSize: 9, color: '#5BB8C4' }}>
              ● {compareSymbol}
              <span style={{ cursor: 'pointer', marginLeft: 4, color: 'var(--text-dim)' }}
                onClick={() => { setCompareSymbol(null); setCompareInput('') }}>✕</span>
            </span>
          )}
          <div style={{ display: 'flex', gap: 4, marginLeft: 6, alignItems: 'center' }}>
            {[{ key: 'trend', label: 'Trend' }, { key: 'ray', label: 'H-Ray' }, { key: 'fib', label: 'Fib' }].map(t => (
              <button key={t.key} className={`btn ${activeTool === t.key ? 'active' : ''}`}
                style={{ fontSize: 9, padding: '2px 7px' }}
                onClick={() => selectTool(t.key)}>
                {t.label}
              </button>
            ))}
            {drawings.length > 0 && (
              <button className="btn" style={{ fontSize: 9, padding: '2px 7px' }} onClick={clearDrawings}>
                Clear
              </button>
            )}
          </div>
          <div style={{ display: 'flex', gap: 4, marginLeft: 6, flexWrap: 'wrap' }}>
            {TIMESPANS.map(t => (
              <button
                key={t.label}
                onClick={() => setTs(t)}
                style={{
                  background:  ts.label === t.label ? 'var(--blue)' : 'transparent',
                  color:       ts.label === t.label ? '#fff' : 'var(--text-secondary)',
                  border:      '1px solid var(--border-accent)',
                  borderRadius: 3,
                  padding:     '2px 7px',
                  fontSize:    9,
                  cursor:      'pointer',
                  fontFamily:  'var(--font-mono)',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div
        ref={containerRef}
        style={{ flex: 1, position: 'relative' }}
      >
        <canvas
          ref={canvasElRef}
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
        />
        <canvas
          ref={drawCanvasRef}
          onClick={onCanvasClick}
          style={{
            position: 'absolute', inset: 0, width: '100%', height: '100%', zIndex: 5,
            pointerEvents: activeTool ? 'auto' : 'none',
            cursor: activeTool ? 'crosshair' : 'default',
          }}
        />
        {loading && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--text-dim)', fontSize: 11, pointerEvents: 'none',
          }}>
            Loading...
          </div>
        )}
      </div>
    </div>
  )
}
