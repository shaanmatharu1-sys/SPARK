import React, { useRef, useEffect, useState } from 'react'
import { useVessels } from '../../hooks/useMarketData'

// Equirectangular projection: lon/lat -> x/y on canvas
function project(lon, lat, W, H) {
  const x = (lon + 180) / 360 * W
  const y = (90 - lat) / 180 * H
  return [x, y]
}

// Key chokepoints to label (Bloomberg-style)
const CHOKEPOINTS = [
  { name: 'Suez',    lon: 32.5, lat: 30.0 },
  { name: 'Hormuz',  lon: 56.3, lat: 26.6 },
  { name: 'Malacca', lon: 100.3, lat: 2.5 },
  { name: 'Panama',  lon: -79.9, lat: 9.1 },
  { name: 'Gibraltar', lon: -5.6, lat: 36.0 },
]

function VesselMap({ vessels }) {
  const canvasRef = useRef(null)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width = canvas.offsetWidth
    const H = canvas.height = canvas.offsetHeight

    // Background
    ctx.fillStyle = '#0A1726'
    ctx.fillRect(0, 0, W, H)

    // Lat/lon grid
    ctx.strokeStyle = 'rgba(36,72,115,0.25)'
    ctx.lineWidth = 1
    for (let lon = -180; lon <= 180; lon += 30) {
      const [x] = project(lon, 0, W, H)
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    }
    for (let lat = -60; lat <= 90; lat += 30) {
      const [, y] = project(0, lat, W, H)
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
    }

    // Chokepoint markers
    for (const cp of CHOKEPOINTS) {
      const [x, y] = project(cp.lon, cp.lat, W, H)
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2)
      ctx.fillStyle = 'var(--gold)'; ctx.fillStyle = '#C9A84C'; ctx.fill()
      ctx.fillStyle = '#8A7536'; ctx.font = '9px IBM Plex Mono, monospace'
      ctx.textAlign = 'left'; ctx.fillText(cp.name, x + 5, y + 3)
    }

    // Vessels
    const positions = []
    for (const v of vessels) {
      if (v.lat == null || v.lon == null) continue
      const [x, y] = project(v.lon, v.lat, W, H)
      positions.push({ ...v, x, y })
      const moving = (v.sog || 0) > 0.5
      ctx.beginPath()
      ctx.arc(x, y, moving ? 2.2 : 1.6, 0, Math.PI*2)
      ctx.fillStyle = moving ? '#6BA3D4' : '#5E789A'
      ctx.fill()
    }

    const onMove = (ev) => {
      const rect = canvas.getBoundingClientRect()
      const mx = ev.clientX - rect.left, my = ev.clientY - rect.top
      const hit = positions.find(p => Math.hypot(p.x-mx, p.y-my) < 5)
      setHover(hit ? { ...hit, mx, my } : null)
    }
    canvas.addEventListener('mousemove', onMove)
    return () => canvas.removeEventListener('mousemove', onMove)
  }, [vessels])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block', borderRadius: 4 }} />
      {hover && (
        <div style={{ position: 'absolute', left: hover.mx + 12, top: hover.my + 12,
                      background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                      borderRadius: 6, padding: '6px 10px', pointerEvents: 'none', zIndex: 10, fontSize: 10 }}>
          <div style={{ color: 'var(--gold)', fontWeight: 700 }}>{hover.name || `MMSI ${hover.mmsi}`}</div>
          <div className="dim">{hover.lat?.toFixed(2)}, {hover.lon?.toFixed(2)}</div>
          {hover.sog != null && <div className="dim">speed: {hover.sog} kn</div>}
          {hover.destination && <div className="dim">-> {hover.destination}</div>}
        </div>
      )}
    </div>
  )
}

export default function SupplyMap() {
  const { data, loading } = useVessels()

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Supply Routes — Live Vessels</span>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {data?.available && (
            <span className="dim" style={{ fontSize: 10 }}>
              {data.feed_live ? <span className="live-dot" /> : null}
              {data.count} vessels · {data.total_tracked} tracked
            </span>
          )}
        </div>
      </div>
      <div className="panel-body" style={{ padding: 8 }}>
        {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Loading vessel positions…</div>}
        {data && !data.available && (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)' }}>
            <div style={{ fontSize: 14, marginBottom: 6 }}>Vessel feed not configured</div>
            <div style={{ fontSize: 11 }}>{data.reason}</div>
            <div style={{ fontSize: 11, marginTop: 8 }}>{data.note}</div>
          </div>
        )}
        {data?.available && (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {data.note && (
              <div style={{ padding: '4px 8px', fontSize: 10, color: 'var(--text-dim)' }}>{data.note}</div>
            )}
            <div style={{ flex: 1 }}>
              <VesselMap vessels={data.vessels || []} />
            </div>
            <div style={{ padding: '6px 8px', fontSize: 9, color: 'var(--text-dim)' }}>
              Blue = underway · gray = stationary · gold = chokepoints. Live AIS via aisstream.io.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
