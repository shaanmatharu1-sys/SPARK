import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts'
import { useBars } from '../../hooks/useMarketData'
import { useWebSocket } from '../../hooks/useWebSocket'
import { sma, ema, rsi, macd, bollingerBands } from '../../lib/indicators'
import { useDrawingTools } from './ChartDrawingLayer'

const TIMESPANS = [
  { label: '1D',  multiplier: 1,  timespan: 'minute', limit: 390 },
  { label: '1W',  multiplier: 5,  timespan: 'minute', limit: 390 },
  { label: '1M',  multiplier: 1,  timespan: 'day',    limit: 30 },
  { label: '3M',  multiplier: 1,  timespan: 'day',    limit: 65 },
  { label: '1Y',  multiplier: 1,  timespan: 'week',   limit: 52 },
]

const INDICATORS = [
  { key: 'sma',    label: 'SMA 20' },
  { key: 'ema',    label: 'EMA 20' },
  { key: 'bbands', label: 'BB 20' },
  { key: 'rsi',    label: 'RSI 14' },
  { key: 'macd',   label: 'MACD' },
]

function zip(times, values) {
  const out = []
  for (let i = 0; i < times.length; i++) {
    if (values[i] === undefined || isNaN(values[i])) continue
    out.push({ time: times[i], value: values[i] })
  }
  return out
}

function pctChange(closes) {
  const base = closes.find(c => c != null)
  if (!base) return closes.map(() => NaN)
  return closes.map(c => (c == null ? NaN : (c / base - 1) * 100))
}

export default function PriceChart({ symbol = 'SPY' }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const candleRef    = useRef(null)
  const volumeRef    = useRef(null)
  const lastBarTime  = useRef(null)
  const closesRef    = useRef([])   // full closes for the currently loaded bars
  const timesRef     = useRef([])   // matching time (seconds) for each close
  const indicatorSeriesRef = useRef({}) // { sma, ema, bbUpper, bbLower, rsi, macdLine, macdSignal, macdHist }
  const compareSeriesRef   = useRef(null)

  const [ts, setTs] = useState(TIMESPANS[0])
  const { data: bars, loading } = useBars(symbol, ts.multiplier, ts.timespan, ts.limit)

  const [activeIndicators, setActiveIndicators] = useState({})
  const toggleIndicator = (key) => setActiveIndicators(a => ({ ...a, [key]: !a[key] }))

  const [compareInput, setCompareInput] = useState('')
  const [compareSymbol, setCompareSymbol] = useState(null)
  const { data: compareBars } = useBars(compareSymbol, ts.multiplier, ts.timespan, ts.limit)

  const { canvasRef: drawCanvasRef, activeTool, selectTool, drawings, clearDrawings, onCanvasClick } =
    useDrawingTools(chartRef, candleRef, containerRef, symbol)

  // Live tick updates only make sense for the 1-minute intraday view — the websocket's
  // "AM" events are always 1-minute bars, so applying them to a 5m/day/week series
  // would draw a spurious extra candle instead of updating the right bucket.
  const isIntraday = ts.timespan === 'minute' && ts.multiplier === 1

  // Rebuild every indicator series (overlays + sub-panes) from the closes/times
  // currently in closesRef/timesRef. Called on bulk data load and whenever the
  // active-indicator toggles change; cheap enough to just redo from scratch.
  const rebuildIndicators = useCallback(() => {
    const chart = chartRef.current
    if (!chart) return
    const closes = closesRef.current
    const times  = timesRef.current
    if (!closes.length) return

    for (const s of Object.values(indicatorSeriesRef.current)) {
      if (s) { try { chart.removeSeries(s) } catch { /* already gone */ } }
    }
    indicatorSeriesRef.current = {}
    while (chart.panes().length > 1) chart.removePane(chart.panes().length - 1)

    if (activeIndicators.sma) {
      const s = chart.addSeries(LineSeries, {
        color: '#6BA3D4', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, // var(--steel-bright)
      })
      s.setData(zip(times, sma(closes, 20)))
      indicatorSeriesRef.current.sma = s
    }
    if (activeIndicators.ema) {
      const s = chart.addSeries(LineSeries, {
        color: '#E0C168', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, // var(--gold-bright)
      })
      s.setData(zip(times, ema(closes, 20)))
      indicatorSeriesRef.current.ema = s
    }
    if (activeIndicators.bbands) {
      const bb = bollingerBands(closes, 20, 2)
      const upper = chart.addSeries(LineSeries, {
        color: '#9B8Bd4', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, // var(--purple)
      })
      upper.setData(zip(times, bb.upper))
      const lower = chart.addSeries(LineSeries, {
        color: '#9B8Bd4', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, // var(--purple)
      })
      lower.setData(zip(times, bb.lower))
      indicatorSeriesRef.current.bbUpper = upper
      indicatorSeriesRef.current.bbLower = lower
    }
    if (activeIndicators.rsi) {
      const pane = chart.addPane()
      pane.setStretchFactor(0.3)
      const s = pane.addSeries(LineSeries, { color: '#E0C168', lineWidth: 1 }) // var(--gold-bright)
      s.setData(zip(times, rsi(closes, 14)))
      indicatorSeriesRef.current.rsi = s
    }
    if (activeIndicators.macd) {
      const pane = chart.addPane()
      pane.setStretchFactor(0.3)
      const m = macd(closes, 12, 26, 9)
      const hist = pane.addSeries(HistogramSeries, { priceFormat: { type: 'volume' } })
      hist.setData(zip(times, m.histogram).map(p => ({
        ...p, color: p.value >= 0 ? '#3FB68B60' : '#E0556B60', // var(--green)/var(--red) at ~38% alpha
      })))
      const line = pane.addSeries(LineSeries, { color: '#6BA3D4', lineWidth: 1 }) // var(--steel-bright)
      line.setData(zip(times, m.macd))
      const signal = pane.addSeries(LineSeries, { color: '#C9A84C', lineWidth: 1 }) // var(--gold)
      signal.setData(zip(times, m.signal))
      indicatorSeriesRef.current.macdHist = hist
      indicatorSeriesRef.current.macdLine = line
      indicatorSeriesRef.current.macdSignal = signal
    }
  }, [activeIndicators])

  const onTick = useCallback((msg) => {
    if (msg.type !== 'bar' || msg.symbol !== symbol) return
    if (!candleRef.current || !volumeRef.current) return
    const time = Math.floor(msg.ts / 1000)
    if (lastBarTime.current != null && time < lastBarTime.current) return
    lastBarTime.current = time
    candleRef.current.update({
      time, open: msg.open, high: msg.high, low: msg.low, close: msg.close,
    })
    volumeRef.current.update({
      time, value: msg.volume,
      // mirrors var(--green)/var(--red) at ~19% alpha — lightweight-charts can't read CSS vars
      color: msg.close >= msg.open ? '#3FB68B30' : '#E0556B30',
    })

    // Keep the local closes/times mirror in sync, then recompute just the
    // trailing indicator value(s) instead of a full network round-trip.
    const closes = closesRef.current, times = timesRef.current
    if (times.length && times[times.length - 1] === time) {
      closes[closes.length - 1] = msg.close
    } else {
      closes.push(msg.close); times.push(time)
    }
    const ind = indicatorSeriesRef.current
    if (ind.sma)  ind.sma.update({ time, value: sma(closes, 20).at(-1) })
    if (ind.ema)  ind.ema.update({ time, value: ema(closes, 20).at(-1) })
    if (ind.bbUpper) {
      const bb = bollingerBands(closes, 20, 2)
      ind.bbUpper.update({ time, value: bb.upper.at(-1) })
      ind.bbLower.update({ time, value: bb.lower.at(-1) })
    }
    if (ind.rsi) ind.rsi.update({ time, value: rsi(closes, 14).at(-1) })
    if (ind.macdLine) {
      const m = macd(closes, 12, 26, 9)
      const h = m.histogram.at(-1)
      ind.macdLine.update({ time, value: m.macd.at(-1) })
      ind.macdSignal.update({ time, value: m.signal.at(-1) })
      ind.macdHist.update({ time, value: h, color: h >= 0 ? '#3FB68B60' : '#E0556B60' })
    }
  }, [symbol])

  useWebSocket(isIntraday ? `/quotes/ws?symbols=${symbol}` : null, onTick, isIntraday)

  // Init chart
  useEffect(() => {
    if (!containerRef.current) return
    // lightweight-charts draws to its own internal canvas and can't read CSS custom
    // properties, so these hex values are hardcoded to mirror the theme tokens noted
    // alongside each one (var(--bg-panel), var(--text-dim), var(--border), etc).
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0F2138' }, // var(--bg-panel)
        textColor:  '#5E789A', // var(--text-dim)
      },
      grid: {
        vertLines:  { color: '#1A3354' }, // var(--border)
        horzLines:  { color: '#1A3354' }, // var(--border)
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#244873' }, // var(--border-bright)
      leftPriceScale: { visible: false, borderColor: '#244873' }, // used only when compare mode is active
      timeScale: {
        borderColor:     '#244873', // var(--border-bright)
        timeVisible:     true,
        secondsVisible:  false,
      },
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor:          '#3FB68B', // var(--green)
      downColor:        '#E0556B', // var(--red)
      borderUpColor:    '#3FB68B', // var(--green)
      borderDownColor:  '#E0556B', // var(--red)
      wickUpColor:      '#3FB68B', // var(--green)
      wickDownColor:    '#E0556B', // var(--red)
    })

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color:     '#6BA3D4', // var(--steel-bright)
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    chartRef.current   = chart
    candleRef.current  = candleSeries
    volumeRef.current  = volumeSeries

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width:  containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [])

  // Update data
  useEffect(() => {
    if (!bars || !candleRef.current) return
    const candles = bars.map(b => ({
      time:  b.t / 1000,
      open:  b.o,
      high:  b.h,
      low:   b.l,
      close: b.c,
    }))
    const volumes = bars.map(b => ({
      time:  b.t / 1000,
      value: b.v,
      // mirrors var(--green)/var(--red) at ~19% alpha — lightweight-charts can't read CSS vars
      color: b.c >= b.o ? '#3FB68B30' : '#E0556B30',
    }))
    candleRef.current.setData(candles)
    volumeRef.current.setData(volumes)
    chartRef.current?.timeScale().fitContent()
    lastBarTime.current = candles.length ? candles[candles.length - 1].time : null

    closesRef.current = candles.map(c => c.close)
    timesRef.current  = candles.map(c => c.time)
    rebuildIndicators()
  }, [bars])

  // Rebuild indicators when the toggle set changes (bars themselves unchanged)
  useEffect(() => { rebuildIndicators() }, [activeIndicators])

  // Compare/overlay: normalized (% change from first bar in range) line on a
  // left price scale, so it doesn't distort the primary candlestick axis.
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    if (compareSeriesRef.current) {
      try { chart.removeSeries(compareSeriesRef.current) } catch { /* already gone */ }
      compareSeriesRef.current = null
    }
    if (!compareSymbol || !compareBars?.length) {
      chart.applyOptions({ leftPriceScale: { visible: false } })
      return
    }
    chart.applyOptions({ leftPriceScale: { visible: true, borderColor: '#244873' } })
    const closes = compareBars.map(b => b.c)
    const times  = compareBars.map(b => b.t / 1000)
    const s = chart.addSeries(LineSeries, {
      color: '#5BB8C4', lineWidth: 2, priceScaleId: 'left', // var(--cyan)
      priceLineVisible: false,
    })
    s.setData(zip(times, pctChange(closes)))
    compareSeriesRef.current = s
  }, [compareSymbol, compareBars])

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: 6 }}>
        <span className="title">{symbol} — Chart</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
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
          <div style={{ display: 'flex', gap: 4, marginLeft: 6 }}>
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
          ref={drawCanvasRef}
          onClick={onCanvasClick}
          style={{
            position: 'absolute', inset: 0, width: '100%', height: '100%', zIndex: 5,
            // lightweight-charts appends its own canvases to this container in a
            // later effect, so without an explicit z-index they paint on top of
            // (and eat clicks meant for) this drawing overlay.
            pointerEvents: activeTool ? 'auto' : 'none',
            cursor: activeTool ? 'crosshair' : 'default',
          }}
        />
        {loading && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--text-dim)', fontSize: 11,
          }}>
            Loading...
          </div>
        )}
      </div>
    </div>
  )
}
