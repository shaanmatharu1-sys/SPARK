import React, { useRef, useEffect } from 'react'
import { useInternational } from '../../hooks/useMarketData'
import { WORLD_LAND } from '../SupplyMap/worldGeo'

const chgColor = (p) => p == null ? 'var(--text-dim)' : p > 0 ? 'var(--green)' : p < 0 ? 'var(--red)' : 'var(--text)'
const fmtPct = (p) => p == null ? '—' : `${p > 0 ? '+' : ''}${p.toFixed(2)}%`

// Approx region centroids for the map (lon, lat)
const REGION_CENTROID = {
  'Americas': [-95, 40],
  'Europe':   [10, 50],
  'Asia':     [110, 30],
  'Broad':    null,
}

function perfColor(pct) {
  if (pct == null) return 'rgba(94,120,154,0.3)'
  const a = Math.min(1, Math.abs(pct) / 3)
  return pct >= 0
    ? `rgba(63,182,139,${0.25 + a * 0.6})`
    : `rgba(224,85,107,${0.25 + a * 0.6})`
}

// Map each land ring to a rough region by its average longitude/latitude
function ringRegion(ring) {
  let sx = 0, sy = 0
  for (const [x, y] of ring) { sx += x; sy += y }
  const lon = sx / ring.length, lat = sy / ring.length
  if (lon < -30) return 'Americas'
  if (lon < 45)  return 'Europe'  // includes Africa visually; fine for shading
  return 'Asia'
}

function WorldPerfMap({ etfs }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width = canvas.offsetWidth
    const H = canvas.height = canvas.offsetHeight
    const project = (lon, lat) => [(lon + 180) / 360 * W, (90 - lat) / 180 * H]

    // Region average performance from ETFs
    const byRegion = {}
    for (const e of (etfs || [])) {
      if (e.change_pct == null || !e.region || e.region === 'Broad') continue
      ;(byRegion[e.region] ||= []).push(e.change_pct)
    }
    const regionAvg = {}
    for (const r in byRegion) regionAvg[r] = byRegion[r].reduce((a, b) => a + b, 0) / byRegion[r].length

    ctx.fillStyle = '#0A1726'
    ctx.fillRect(0, 0, W, H)

    // Draw land, colored by region performance
    for (const ring of WORLD_LAND) {
      const region = ringRegion(ring)
      const pct = regionAvg[region]
      ctx.beginPath()
      for (let i = 0; i < ring.length; i++) {
        const [x, y] = project(ring[i][0], ring[i][1])
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.fillStyle = perfColor(pct)
      ctx.fill()
      ctx.strokeStyle = 'rgba(74,123,166,0.4)'; ctx.lineWidth = 0.6; ctx.stroke()
    }

    // Region labels with avg performance
    ctx.font = '11px IBM Plex Mono, monospace'
    ctx.textAlign = 'center'
    for (const r in regionAvg) {
      const c = REGION_CENTROID[r]
      if (!c) continue
      const [x, y] = project(c[0], c[1])
      const pct = regionAvg[r]
      ctx.fillStyle = '#E8EAED'
      ctx.fillText(r, x, y - 6)
      ctx.fillStyle = pct >= 0 ? '#3FB68B' : '#E0556B'
      ctx.fillText(`${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`, x, y + 8)
    }
  }, [etfs])

  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block', borderRadius: 4 }} />
}

function Row({ left, sub, right, rightColor }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ minWidth: 0 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text)' }}>{left}</span>
        {sub && <span className="dim" style={{ fontSize: 10, marginLeft: 6 }}>{sub}</span>}
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: rightColor }}>{right}</span>
    </div>
  )
}

export default function International() {
  const { data, loading } = useInternational()

  const indices = data?.indices?.indices || []
  const indicesAvail = data?.indices?.available !== false
  const etfs = data?.etfs?.etfs || []
  const adrs = data?.adrs?.adrs || []
  const fx = data?.fx?.fx || []

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr',
                  gap: 6, height: '100%', minHeight: 0 }}>
      {/* World map + indices */}
      <div className="panel" style={{ minHeight: 0, gridRow: '1 / 3' }}>
        <div className="panel-header"><span className="title">Global Markets Map</span></div>
        <div className="panel-body" style={{ padding: 8, display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, minHeight: 180 }}><WorldPerfMap etfs={etfs} /></div>
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)', marginBottom: 4 }}>
              WORLD INDICES {!indicesAvail && <span className="dim" style={{ fontWeight: 400 }}>(yfinance unavailable)</span>}
            </div>
            {indices.length === 0 && indicesAvail && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}
            {indices.map(ix => (
              <Row key={ix.symbol} left={ix.name} sub={ix.country}
                   right={`${ix.level?.toLocaleString()}  ${fmtPct(ix.change_pct)}`}
                   rightColor={chgColor(ix.change_pct)} />
            ))}
          </div>
        </div>
      </div>

      {/* Country ETFs */}
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">Country / Region ETFs</span></div>
        <div className="panel-body" style={{ padding: '4px 12px' }}>
          {loading && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}
          {etfs.map(e => (
            <Row key={e.symbol} left={e.symbol} sub={e.name}
                 right={fmtPct(e.change_pct)} rightColor={chgColor(e.change_pct)} />
          ))}
        </div>
      </div>

      {/* ADRs + FX side by side in bottom-right */}
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">ADRs & FX</span></div>
        <div className="panel-body" style={{ padding: '4px 12px' }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--gold-bright)', margin: '2px 0 4px' }}>FX</div>
          {fx.map(f => (
            <Row key={f.symbol} left={f.pair}
                 right={`${f.rate ?? '—'}  ${fmtPct(f.change_pct)}`} rightColor={chgColor(f.change_pct)} />
          ))}
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--gold-bright)', margin: '8px 0 4px' }}>ADRs</div>
          {adrs.map(a => (
            <Row key={a.symbol} left={a.symbol} sub={a.country}
                 right={fmtPct(a.change_pct)} rightColor={chgColor(a.change_pct)} />
          ))}
        </div>
      </div>
    </div>
  )
}
