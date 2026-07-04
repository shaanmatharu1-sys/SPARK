import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, ColorType } from 'lightweight-charts'
import { useBars } from '../../hooks/useMarketData'
import { useWebSocket } from '../../hooks/useWebSocket'

const TIMESPANS = [
  { label: '1D',  multiplier: 1,  timespan: 'minute', limit: 390 },
  { label: '1W',  multiplier: 5,  timespan: 'minute', limit: 390 },
  { label: '1M',  multiplier: 1,  timespan: 'day',    limit: 30 },
  { label: '3M',  multiplier: 1,  timespan: 'day',    limit: 65 },
  { label: '1Y',  multiplier: 1,  timespan: 'week',   limit: 52 },
]

export default function PriceChart({ symbol = 'SPY' }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const candleRef    = useRef(null)
  const volumeRef    = useRef(null)
  const lastBarTime  = useRef(null)

  const [ts, setTs] = useState(TIMESPANS[0])
  const { data: bars, loading } = useBars(symbol, ts.multiplier, ts.timespan, ts.limit)

  // Live tick updates only make sense for the 1-minute intraday view — the websocket's
  // "AM" events are always 1-minute bars, so applying them to a 5m/day/week series
  // would draw a spurious extra candle instead of updating the right bucket.
  const isIntraday = ts.timespan === 'minute' && ts.multiplier === 1

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
      timeScale: {
        borderColor:     '#244873', // var(--border-bright)
        timeVisible:     true,
        secondsVisible:  false,
      },
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor:          '#3FB68B', // var(--green)
      downColor:        '#E0556B', // var(--red)
      borderUpColor:    '#3FB68B', // var(--green)
      borderDownColor:  '#E0556B', // var(--red)
      wickUpColor:      '#3FB68B', // var(--green)
      wickDownColor:    '#E0556B', // var(--red)
    })

    const volumeSeries = chart.addHistogramSeries({
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
  }, [bars])

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">{symbol} — Chart</span>
        <div style={{ display: 'flex', gap: 4 }}>
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
      <div
        ref={containerRef}
        style={{ flex: 1, position: 'relative' }}
      >
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
