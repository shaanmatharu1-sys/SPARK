import React, { useEffect, useRef, useState } from 'react'
import { createChart, ColorType } from 'lightweight-charts'
import { useBars } from '../../hooks/useMarketData'

const TIMESPANS = [
  { label: '1D',  multiplier: 1,  timespan: 'minute' },
  { label: '1W',  multiplier: 5,  timespan: 'minute' },
  { label: '1M',  multiplier: 1,  timespan: 'day' },
  { label: '3M',  multiplier: 1,  timespan: 'day' },
  { label: '1Y',  multiplier: 1,  timespan: 'week' },
]

export default function PriceChart({ symbol = 'SPY' }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const candleRef    = useRef(null)
  const volumeRef    = useRef(null)

  const [ts, setTs] = useState(TIMESPANS[0])
  const { data: bars, loading } = useBars(symbol, ts.multiplier, ts.timespan)

  // Init chart
  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0e1118' },
        textColor:  '#7a92ab',
      },
      grid: {
        vertLines:  { color: '#131820' },
        horzLines:  { color: '#131820' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#1c2333' },
      timeScale: {
        borderColor:     '#1c2333',
        timeVisible:     true,
        secondsVisible:  false,
      },
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor:          '#00c853',
      downColor:        '#ff3d57',
      borderUpColor:    '#00c853',
      borderDownColor:  '#ff3d57',
      wickUpColor:      '#00c853',
      wickDownColor:    '#ff3d57',
    })

    const volumeSeries = chart.addHistogramSeries({
      color:     '#1e88e5',
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
      color: b.c >= b.o ? '#00c85330' : '#ff3d5730',
    }))
    candleRef.current.setData(candles)
    volumeRef.current.setData(volumes)
    chartRef.current?.timeScale().fitContent()
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
