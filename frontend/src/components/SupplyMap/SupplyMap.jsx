import React, { useRef, useEffect, useState, useCallback } from 'react'
import { useVessels, usePortWatch } from '../../hooks/useMarketData'
import { WORLD_LAND } from './worldGeo'

// Base equirectangular projection (lon/lat -> base x/y), then a view transform
// (scale + pan) is applied on top so coastlines, vessels, and labels stay aligned.
function baseProject(lon, lat, W, H) {
  return [(lon + 180) / 360 * W, (90 - lat) / 180 * H]
}

const CHOKEPOINTS = [
  { name: 'Suez',      lon: 32.5,  lat: 30.0 },
  { name: 'Hormuz',    lon: 56.3,  lat: 26.6 },
  { name: 'Malacca',   lon: 100.3, lat: 2.5 },
  { name: 'Panama',    lon: -79.9, lat: 9.1 },
  { name: 'Gibraltar', lon: -5.6,  lat: 36.0 },
]

function VesselMap({ vessels, ports = [] }) {
  const canvasRef = useRef(null)
  const [hover, setHover] = useState(null)
  // View transform: scale + translate (in screen px)
  const view = useRef({ scale: 1, tx: 0, ty: 0 })
  const drag = useRef(null)
  const [, force] = useState(0)  // trigger redraw on view change

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width = canvas.offsetWidth
    const H = canvas.height = canvas.offsetHeight
    const { scale, tx, ty } = view.current

    // apply view transform: screen = base * scale + t
    const tf = (lon, lat) => {
      const [bx, by] = baseProject(lon, lat, W, H)
      return [bx * scale + tx, by * scale + ty]
    }

    ctx.fillStyle = '#0A1726'
    ctx.fillRect(0, 0, W, H)

    // ── Coastlines (land outlines) ──
    ctx.lineWidth = 0.7
    ctx.strokeStyle = 'rgba(74,123,166,0.45)'
    ctx.fillStyle = 'rgba(18,40,69,0.55)'
    for (const ring of WORLD_LAND) {
      ctx.beginPath()
      for (let i = 0; i < ring.length; i++) {
        const [x, y] = tf(ring[i][0], ring[i][1])
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.fill()
      ctx.stroke()
    }

    // ── Lat/lon grid (subtle, over land) ──
    ctx.strokeStyle = 'rgba(36,72,115,0.20)'
    ctx.lineWidth = 1
    for (let lon = -180; lon <= 180; lon += 30) {
      const [x0, y0] = tf(lon, 90), [x1, y1] = tf(lon, -90)
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke()
    }
    for (let lat = -60; lat <= 90; lat += 30) {
      const [x0, y0] = tf(-180, lat), [x1, y1] = tf(180, lat)
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke()
    }

    // ── Chokepoints ──
    for (const cp of CHOKEPOINTS) {
      const [x, y] = tf(cp.lon, cp.lat)
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2)
      ctx.fillStyle = '#C9A84C'; ctx.fill()
      ctx.fillStyle = '#C9A84C'; ctx.font = '10px IBM Plex Mono, monospace'
      ctx.textAlign = 'left'; ctx.fillText(cp.name, x + 5, y + 3)
    }

    // ── PortWatch major ports (sized by activity, colored by trend) ──
    const maxAct = Math.max(1, ...ports.map(p => p.avg_7d || 0))
    for (const p of ports) {
      if (p.lat == null || p.lon == null) continue
      const [x, y] = tf(p.lon, p.lat)
      if (x < -10 || x > W + 10 || y < -10 || y > H + 10) continue
      const r = 2 + Math.sqrt((p.avg_7d || 0) / maxAct) * 7
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI*2)
      const up = (p.change_7d_pct || 0) >= 0
      ctx.fillStyle = up ? 'rgba(63,182,139,0.55)' : 'rgba(224,85,107,0.55)'
      ctx.fill()
      ctx.strokeStyle = up ? '#3FB68B' : '#E0556B'
      ctx.lineWidth = 0.8; ctx.stroke()
    }

    // ── Vessels ──
    const positions = []
    for (const v of vessels) {
      if (v.lat == null || v.lon == null) continue
      const [x, y] = tf(v.lon, v.lat)
      if (x < -10 || x > W + 10 || y < -10 || y > H + 10) continue
      positions.push({ ...v, x, y })
      const moving = (v.sog || 0) > 0.5
      ctx.beginPath()
      ctx.arc(x, y, moving ? 2.4 : 1.7, 0, Math.PI*2)
      ctx.fillStyle = moving ? '#6BA3D4' : '#5E789A'
      ctx.fill()
    }
    canvasRef.current._positions = positions
  }, [vessels, ports])

  useEffect(() => { draw() }, [draw, vessels])

  // Redraw on container resize
  useEffect(() => {
    const ro = new ResizeObserver(() => draw())
    if (canvasRef.current) ro.observe(canvasRef.current)
    return () => ro.disconnect()
  }, [draw])

  // ── Zoom (scroll, centered on cursor) ──
  const onWheel = (ev) => {
    ev.preventDefault()
    const rect = canvasRef.current.getBoundingClientRect()
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top
    const v = view.current
    const factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15
    const newScale = Math.max(1, Math.min(40, v.scale * factor))
    // keep cursor point fixed: adjust translate
    v.tx = mx - (mx - v.tx) * (newScale / v.scale)
    v.ty = my - (my - v.ty) * (newScale / v.scale)
    v.scale = newScale
    // clamp pan so map can't drift fully off-screen
    clampView()
    draw()
  }

  const clampView = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const W = canvas.offsetWidth, H = canvas.offsetHeight
    const v = view.current
    const mapW = W * v.scale, mapH = H * v.scale
    v.tx = Math.min(0, Math.max(W - mapW, v.tx))
    v.ty = Math.min(0, Math.max(H - mapH, v.ty))
  }

  // ── Pan (drag) ──
  const onMouseDown = (ev) => {
    drag.current = { x: ev.clientX, y: ev.clientY, tx: view.current.tx, ty: view.current.ty }
  }
  const onMouseMove = (ev) => {
    if (drag.current) {
      view.current.tx = drag.current.tx + (ev.clientX - drag.current.x)
      view.current.ty = drag.current.ty + (ev.clientY - drag.current.y)
      clampView()
      draw()
      return
    }
    // hover detection
    const rect = canvasRef.current.getBoundingClientRect()
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top
    const positions = canvasRef.current._positions || []
    const hit = positions.find(p => Math.hypot(p.x - mx, p.y - my) < 5)
    setHover(hit ? { ...hit, mx, my } : null)
  }
  const onMouseUp = () => { drag.current = null }

  const resetView = () => { view.current = { scale: 1, tx: 0, ty: 0 }; draw(); force(n => n+1) }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas
        ref={canvasRef}
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={() => { drag.current = null; setHover(null) }}
        style={{ width: '100%', height: '100%', display: 'block', borderRadius: 4,
                 cursor: drag.current ? 'grabbing' : 'grab' }}
      />
      <button className="btn" onClick={resetView}
        style={{ position: 'absolute', top: 8, right: 8, zIndex: 10 }}>Reset view</button>
      <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 10, fontSize: 9,
                    color: 'var(--text-dim)', pointerEvents: 'none' }}>
        scroll to zoom · drag to pan
      </div>
      {hover && (
        <div style={{ position: 'absolute', left: hover.mx + 12, top: hover.my + 12,
                      background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                      borderRadius: 6, padding: '6px 10px', pointerEvents: 'none', zIndex: 10, fontSize: 10 }}>
          <div style={{ color: 'var(--gold)', fontWeight: 700 }}>{hover.name || `MMSI ${hover.mmsi}`}</div>
          <div className="dim">{hover.lat?.toFixed(2)}, {hover.lon?.toFixed(2)}</div>
          {hover.sog != null && <div className="dim">speed: {hover.sog} kn</div>}
          {hover.destination && <div className="dim">to {hover.destination}</div>}
        </div>
      )}
    </div>
  )
}

export default function SupplyMap() {
  const { data, loading } = useVessels()
  const { data: pw } = usePortWatch()
  const ports = pw?.ports?.ports || []

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
            <div style={{ flex: 1, minHeight: 0 }}>
              <VesselMap vessels={data.vessels || []} ports={ports} />
            </div>
            <div style={{ padding: '6px 8px', fontSize: 9, color: 'var(--text-dim)' }}>
              Blue = underway · gray = stationary · gold = chokepoints · circles = ports (size = activity, green/red = trend). Live AIS via aisstream.io, ports via IMF PortWatch.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
