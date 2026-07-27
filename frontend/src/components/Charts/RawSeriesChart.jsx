import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createChartEngine } from '../../lib/canvasChart'
import { sma, ema } from '../../lib/indicators'

// A full interactive canvas chart (zoom, pan, crosshair, real axes — the
// same engine PriceChart uses) for series that don't come from the
// Polygon-backed useBars() hook: futures continuous contracts (yfinance),
// FX pairs (Frankfurter), global indices, anything fetched as a plain
// { t, o, h, l, c, v? } bar array by the caller. This is what replaced the
// 130px recharts sparklines on the Futures and FX tabs — same drill-down
// depth as the main price chart instead of a decorative mini-graph.
//
// `bars`: array of { t: <unix seconds>, o?, h?, l?, c, v? } ascending by time.
// If any bar is missing o/h/l, the chart is forced into line mode (yfinance/
// Frankfurter daily closes don't carry true OHLC for these instruments).

const COLORS = {
  grid:             '#1A3354', // var(--border)
  border:           '#1A3354', // var(--border)
  text:             '#E8EAED', // var(--text-primary)
  dimText:          '#5E789A', // var(--text-dim)
  up:               '#3FB68B', // var(--green)
  down:             '#E0556B', // var(--red)
  volUp:            '#3FB68B4D',
  volDown:          '#E0556B4D',
  line:             '#6BA3D4', // var(--steel-bright)
  crosshair:        '#6BA3D480',
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

export default function RawSeriesChart({ bars, loading, title, height, showVolumeDefault = false }) {
  const containerRef = useRef(null)
  const canvasRef    = useRef(null)
  const engineRef    = useRef(null)

  const hasOHLC = bars && bars.length && bars.every(b => b.o != null && b.h != null && b.l != null)
  const [mode, setMode] = useState(hasOHLC ? 'candle' : 'line')
  const [showVolume, setShowVolume] = useState(showVolumeDefault)
  const [indicators, setIndicators] = useState({})

  useEffect(() => { setMode(hasOHLC ? 'candle' : 'line') }, [hasOHLC])

  useEffect(() => {
    if (!canvasRef.current || !containerRef.current) return
    const engine = createChartEngine(canvasRef.current, COLORS)
    engineRef.current = engine
    const ro = new ResizeObserver(() => engine.resize())
    ro.observe(containerRef.current)
    return () => { ro.disconnect(); engine.destroy() }
  }, [])

  useEffect(() => { engineRef.current?.setMode(mode) }, [mode])
  useEffect(() => { engineRef.current?.setShowVolume(showVolume) }, [showVolume])

  const rebuildOverlays = useCallback(() => {
    const engine = engineRef.current
    if (!engine || !bars?.length) return
    const closes = bars.map(b => b.c)
    const times  = bars.map(b => b.t)
    const overlays = []
    if (indicators.sma) overlays.push({ color: '#6BA3D4', points: zip(times, sma(closes, 20)) })
    if (indicators.ema) overlays.push({ color: '#E0C168', points: zip(times, ema(closes, 20)) })
    engine.setOverlays(overlays)
  }, [bars, indicators])

  useEffect(() => {
    if (!bars || !engineRef.current) return
    const engineBars = bars.map(b => ({
      t: b.t, o: b.o ?? b.c, h: b.h ?? b.c, l: b.l ?? b.c, c: b.c, v: b.v ?? 0,
    }))
    engineRef.current.setData(engineBars)
    rebuildOverlays()
  }, [bars])

  useEffect(() => { rebuildOverlays() }, [indicators])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: height ?? '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginBottom: 4, flexWrap: 'wrap', gap: 6 }}>
        {title && (
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)' }}>{title}</span>
        )}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {hasOHLC && ['candle', 'bar', 'line'].map(m => (
            <button key={m} className={`btn ${mode === m ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px', textTransform: 'capitalize' }}
              onClick={() => setMode(m)}>
              {m}
            </button>
          ))}
          {bars?.some(b => b.v) && (
            <button className={`btn ${showVolume ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px' }}
              onClick={() => setShowVolume(v => !v)}>
              Vol
            </button>
          )}
          {[['sma', 'SMA 20'], ['ema', 'EMA 20']].map(([k, label]) => (
            <button key={k} className={`btn ${indicators[k] ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px' }}
              onClick={() => setIndicators(a => ({ ...a, [k]: !a[k] }))}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div ref={containerRef} style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
        {loading && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', color: 'var(--text-dim)', fontSize: 11, pointerEvents: 'none' }}>
            Loading…
          </div>
        )}
        {!loading && !bars?.length && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', color: 'var(--text-dim)', fontSize: 11, pointerEvents: 'none' }}>
            No data
          </div>
        )}
      </div>
    </div>
  )
}
