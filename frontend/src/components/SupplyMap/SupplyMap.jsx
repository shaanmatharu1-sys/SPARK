import React, { useRef, useEffect, useState, useCallback } from 'react'
import { useVessels, usePortWatch, useFlights } from '../../hooks/useMarketData'
import { WORLD_LAND } from './worldGeo'

// An equirectangular projection needs a 2:1 width:height ratio (360deg lon /
// 180deg lat) to render undistorted — stretching lon across the full canvas
// width and lat across the full canvas height independently (the previous
// version) meant any panel that wasn't exactly 2:1 visibly squished or
// stretched every continent, which is what actually caused flights/vessels
// to look "off" relative to the coastlines even though their coordinates
// were mathematically exact (verified directly: computed pixel position
// from a flight's real lat/lon matched its rendered x/y to the sub-pixel).
// Fix: compute a letterboxed 2:1 map area inside the canvas and project
// into that, instead of the canvas's raw (and usually non-2:1) dimensions.
function mapDims(W, H) {
  const naturalAspect = 2 // 360 / 180
  const containerAspect = W / H
  if (containerAspect > naturalAspect) {
    const mapH = H, mapW = H * naturalAspect
    return { mapW, mapH, offsetX: (W - mapW) / 2, offsetY: 0 }
  }
  const mapW = W, mapH = W / naturalAspect
  return { mapW, mapH, offsetX: 0, offsetY: (H - mapH) / 2 }
}

function baseProject(lon, lat, W, H) {
  const { mapW, mapH, offsetX, offsetY } = mapDims(W, H)
  return [offsetX + (lon + 180) / 360 * mapW, offsetY + (90 - lat) / 180 * mapH]
}
// Inverse of baseProject, used for the cursor lat/lon readout.
function unproject(bx, by, W, H) {
  const { mapW, mapH, offsetX, offsetY } = mapDims(W, H)
  return [(bx - offsetX) / mapW * 360 - 180, 90 - (by - offsetY) / mapH * 180]
}

const CHOKEPOINTS = [
  { name: 'Suez',      lon: 32.5,  lat: 30.0 },
  { name: 'Hormuz',    lon: 56.3,  lat: 26.6 },
  { name: 'Malacca',   lon: 100.3, lat: 2.5 },
  { name: 'Panama',    lon: -79.9, lat: 9.1 },
  { name: 'Gibraltar', lon: -5.6,  lat: 36.0 },
]

// Canvas 2D context can't read CSS custom properties, so these hex values are
// hardcoded to exactly mirror the "Midnight & Brass" tokens in index.css.
// Each constant/line notes which var it mirrors — update both if the theme changes.
const GOLD          = '#C9A84C' // var(--gold) — chokepoints
const GREEN         = '#3FB68B' // var(--green) — ports trending up
const RED           = '#E0556B' // var(--red) — ports trending down
const STEEL_BRIGHT  = '#6BA3D4' // var(--steel-bright) — vessels underway / coastline stroke
const TEXT_DIM      = '#5E789A' // var(--text-dim) — vessels stationary
const GOLD_BRIGHT   = '#E0C168' // var(--gold-bright) — flights airborne
const GOLD_DIM      = '#8A7536' // var(--gold-dim) — flights on ground
const BG_BASE       = '#0B1929' // var(--bg-base) — map background
const BG_PANEL      = 'rgba(15,33,56,0.65)'   // var(--bg-panel) @ 65% — land fill
const COASTLINE     = 'rgba(107,163,212,0.45)' // var(--steel-bright) @ 45% — coastline stroke
const GRID          = 'rgba(36,72,115,0.20)'   // var(--border-bright) @ 20% — lat/lon grid
const PORT_UP_FILL  = 'rgba(63,182,139,0.55)'  // var(--green) @ 55%
const PORT_DOWN_FILL= 'rgba(224,85,107,0.55)'  // var(--red) @ 55%

function drawChevron(ctx, x, y, headingDeg, size, color) {
  // A small directional triangle (like an aircraft glyph) rotated to true_track.
  const rad = ((headingDeg || 0) * Math.PI) / 180
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(rad)
  ctx.beginPath()
  ctx.moveTo(0, -size)
  ctx.lineTo(size * 0.62, size * 0.75)
  ctx.lineTo(0, size * 0.35)
  ctx.lineTo(-size * 0.62, size * 0.75)
  ctx.closePath()
  ctx.fillStyle = color
  ctx.fill()
  ctx.restore()
}

function VesselMap({ vessels, flights, ports = [] }) {
  const canvasRef = useRef(null)
  const [hover, setHover] = useState(null)
  const [cursorLL, setCursorLL] = useState(null)
  const [layerMode, setLayerMode] = useState('both') // 'ships' | 'planes' | 'both'
  // View transform: scale + translate (in screen px)
  const view = useRef({ scale: 1, tx: 0, ty: 0 })
  const drag = useRef(null)
  const [, force] = useState(0)  // trigger redraw on view change

  const showShips  = layerMode !== 'planes'
  const showPlanes = layerMode !== 'ships'

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

    ctx.fillStyle = BG_BASE
    ctx.fillRect(0, 0, W, H)

    // ── Coastlines (land outlines) ──
    ctx.lineWidth = 0.7
    ctx.strokeStyle = COASTLINE
    ctx.fillStyle = BG_PANEL
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
    ctx.strokeStyle = GRID
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
      ctx.fillStyle = GOLD; ctx.fill()
      ctx.fillStyle = GOLD; ctx.font = '10px IBM Plex Mono, monospace'
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
      ctx.fillStyle = up ? PORT_UP_FILL : PORT_DOWN_FILL
      ctx.fill()
      ctx.strokeStyle = up ? GREEN : RED
      ctx.lineWidth = 0.8; ctx.stroke()
    }

    // ── Vessels ──
    const positions = []
    if (showShips) {
      for (const v of vessels) {
        if (v.lat == null || v.lon == null) continue
        const [x, y] = tf(v.lon, v.lat)
        if (x < -10 || x > W + 10 || y < -10 || y > H + 10) continue
        positions.push({ ...v, kind: 'vessel', x, y })
        const moving = (v.sog || 0) > 0.5
        ctx.beginPath()
        ctx.arc(x, y, moving ? 2.4 : 1.7, 0, Math.PI*2)
        ctx.fillStyle = moving ? STEEL_BRIGHT : TEXT_DIM
        ctx.fill()
      }
    }

    // ── Flights (chevrons rotated to heading) ──
    if (showPlanes) {
      for (const f of flights) {
        if (f.lat == null || f.lon == null) continue
        const [x, y] = tf(f.lon, f.lat)
        if (x < -10 || x > W + 10 || y < -10 || y > H + 10) continue
        positions.push({ ...f, kind: 'flight', x, y })
        const color = f.on_ground ? GOLD_DIM : GOLD_BRIGHT
        drawChevron(ctx, x, y, f.heading, f.on_ground ? 2.6 : 4, color)
      }
    }

    canvasRef.current._positions = positions
  }, [vessels, flights, ports, showShips, showPlanes])

  useEffect(() => { draw() }, [draw, vessels, flights])

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
    const rect = canvasRef.current.getBoundingClientRect()
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top

    if (drag.current) {
      view.current.tx = drag.current.tx + (ev.clientX - drag.current.x)
      view.current.ty = drag.current.ty + (ev.clientY - drag.current.y)
      clampView()
      draw()
    } else {
      // hover detection
      const positions = canvasRef.current._positions || []
      const hit = positions.find(p => Math.hypot(p.x - mx, p.y - my) < 5)
      setHover(hit ? { ...hit, mx, my } : null)
    }

    // lat/lon readout under cursor (independent of drag/hover state)
    const { scale, tx, ty } = view.current
    const [lon, lat] = unproject((mx - tx) / scale, (my - ty) / scale,
                                  canvasRef.current.offsetWidth, canvasRef.current.offsetHeight)
    setCursorLL({ lon, lat })
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
        onMouseLeave={() => { drag.current = null; setHover(null); setCursorLL(null) }}
        style={{ width: '100%', height: '100%', display: 'block', borderRadius: 4,
                 cursor: drag.current ? 'grabbing' : 'grab' }}
      />

      {/* Layer toggle */}
      <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 10, display: 'flex', gap: 4 }}>
        {[['ships', 'Ships'], ['planes', 'Planes'], ['both', 'Both']].map(([m, label]) => (
          <button key={m} onClick={() => setLayerMode(m)}
            className={`btn${layerMode === m ? ' active' : ''}`}
            style={{ padding: '2px 9px', fontSize: 9.5 }}>
            {label}
          </button>
        ))}
      </div>

      <button className="btn" onClick={resetView}
        style={{ position: 'absolute', top: 8, right: 8, zIndex: 10 }}>Reset view</button>

      <div style={{ position: 'absolute', top: 34, left: 8, zIndex: 10, fontSize: 9,
                    color: 'var(--text-dim)', pointerEvents: 'none' }}>
        scroll to zoom · drag to pan
      </div>

      {/* Lat/lon readout under cursor */}
      {cursorLL && (
        <div style={{ position: 'absolute', bottom: 8, left: 8, zIndex: 10, fontSize: 9.5,
                      fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                      background: 'var(--bg-panel)', border: '1px solid var(--border)',
                      borderRadius: 4, padding: '3px 7px', pointerEvents: 'none' }}>
          {cursorLL.lat.toFixed(2)}°{cursorLL.lat >= 0 ? 'N' : 'S'}, {cursorLL.lon.toFixed(2)}°{cursorLL.lon >= 0 ? 'E' : 'W'}
        </div>
      )}

      {hover && hover.kind === 'vessel' && (
        <div style={{ position: 'absolute', left: hover.mx + 12, top: hover.my + 12,
                      background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                      borderRadius: 6, padding: '6px 10px', pointerEvents: 'none', zIndex: 10, fontSize: 10 }}>
          <div style={{ color: 'var(--gold)', fontWeight: 700 }}>{hover.name || `MMSI ${hover.mmsi}`}</div>
          <div className="dim">{hover.lat?.toFixed(2)}, {hover.lon?.toFixed(2)}</div>
          {hover.sog != null && <div className="dim">speed: {hover.sog} kn</div>}
          {hover.destination && <div className="dim">to {hover.destination}</div>}
        </div>
      )}

      {hover && hover.kind === 'flight' && (
        <div style={{ position: 'absolute', left: hover.mx + 12, top: hover.my + 12,
                      background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                      borderRadius: 6, padding: '6px 10px', pointerEvents: 'none', zIndex: 10, fontSize: 10 }}>
          <div style={{ color: 'var(--gold-bright)', fontWeight: 700 }}>{hover.callsign || hover.icao24}</div>
          <div className="dim">{hover.lat?.toFixed(2)}, {hover.lon?.toFixed(2)}</div>
          {hover.altitude != null && <div className="dim">alt: {Math.round(hover.altitude * 3.28084).toLocaleString()} ft</div>}
          {hover.velocity != null && <div className="dim">speed: {Math.round(hover.velocity * 1.94384)} kn</div>}
          {hover.aircraft_type && <div className="dim">Type: {hover.aircraft_type}</div>}
          {hover.operator && <div className="dim">{hover.operator}</div>}
          {hover.on_ground && <div className="dim">on ground</div>}
        </div>
      )}
    </div>
  )
}

function LegendSwatch({ color, label, shape = 'circle' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 9.5, color: 'var(--text-dim)' }}>
      <span style={{
        display: 'inline-block', width: 8, height: 8, background: color,
        borderRadius: shape === 'circle' ? '50%' : 2,
        clipPath: shape === 'triangle' ? 'polygon(50% 0%, 100% 100%, 0% 100%)' : undefined,
        flexShrink: 0,
      }} />
      {label}
    </div>
  )
}

function StatTile({ label, value, sub, color }) {
  return (
    <div style={{ flex: '0 0 auto', minWidth: 76, textAlign: 'center', padding: 8,
                  background: 'var(--bg-base)', borderRadius: 5 }}>
      <div className="dim" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: color || 'var(--text-primary)' }}>{value}</div>
      {sub != null && <div className="dim" style={{ fontSize: 9 }}>{sub}</div>}
    </div>
  )
}

export default function SupplyMap() {
  const { data, loading } = useVessels()
  const { data: flightData, loading: flightsLoading } = useFlights()
  const { data: pw } = usePortWatch()
  const ports = pw?.ports?.ports || []
  const chokepoints = pw?.chokepoints?.chokepoints || []
  const topChokepoints = chokepoints.slice(0, 5)

  const vesselsAvailable = !!data?.available
  const flightsAvailable = !!flightData?.available
  const vessels = vesselsAvailable ? (data.vessels || []) : []
  const flights = flightsAvailable ? (flightData.flights || []) : []
  const anyAvailable = vesselsAvailable || flightsAvailable
  const stillLoading = loading && flightsLoading

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Supply Routes — Live Vessels &amp; Flights</span>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {vesselsAvailable && (
            <span className="dim" style={{ fontSize: 10 }}>
              {data.feed_live ? <span className="live-dot" /> : null}
              {data.count} vessels · {data.total_tracked} tracked
            </span>
          )}
          {flightsAvailable && (
            <span className="dim" style={{ fontSize: 10 }}>
              {flightData.feed_live ? <span className="live-dot" /> : null}
              {flightData.count} flights · {flightData.total_tracked} tracked
            </span>
          )}
        </div>
      </div>
      <div className="panel-body" style={{ padding: 8 }}>
        {stillLoading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Loading vessel &amp; flight positions…</div>}
        {!stillLoading && !anyAvailable && (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)' }}>
            <div style={{ fontSize: 14, marginBottom: 6 }}>Live tracking unavailable</div>
            <div style={{ fontSize: 11 }}>{data?.reason}</div>
            <div style={{ fontSize: 11 }}>{flightData?.reason}</div>
          </div>
        )}
        {!stillLoading && anyAvailable && (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {!vesselsAvailable && (
              <div style={{ padding: '0 4px', fontSize: 10, color: 'var(--text-dim)' }}>
                Vessel feed not configured — {data?.reason}. Showing live flights only.
              </div>
            )}
            {!flightsAvailable && flightData && (
              <div style={{ padding: '0 4px', fontSize: 10, color: 'var(--text-dim)' }}>
                Flight feed unavailable — {flightData.reason}. {flightData.note}
              </div>
            )}
            {(vesselsAvailable && data.note) || (flightsAvailable && flightData.note) ? (
              <div style={{ padding: '0 4px', fontSize: 10, color: 'var(--text-dim)' }}>
                {vesselsAvailable && data.note} {flightsAvailable && flightData.note}
              </div>
            ) : null}
            <div style={{ flex: 1, minHeight: 0 }}>
              <VesselMap vessels={vessels} flights={flights} ports={ports} />
            </div>

            {/* Bottom chrome: structured legend + live stats — Bloomberg-style data-dense footer */}
            <div style={{ display: 'flex', gap: 14, padding: '8px 4px 2px', borderTop: '1px solid var(--border)',
                          flexShrink: 0, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0, paddingRight: 10,
                            borderRight: '1px solid var(--border)' }}>
                <LegendSwatch color="var(--steel-bright)" label="Vessel underway" />
                <LegendSwatch color="var(--text-dim)" label="Vessel stationary" />
                <LegendSwatch color="var(--gold-bright)" label="Flight airborne" shape="triangle" />
                <LegendSwatch color="var(--gold-dim)" label="Flight on ground" shape="triangle" />
                <LegendSwatch color="var(--gold)" label="Chokepoint" />
                <div style={{ display: 'flex', gap: 8 }}>
                  <LegendSwatch color="var(--green)" label="Port ↑7d" />
                  <LegendSwatch color="var(--red)" label="Port ↓7d" />
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, flex: 1, overflowX: 'auto', alignItems: 'stretch' }}>
                <StatTile label="VESSELS"
                  value={vesselsAvailable ? (data.total_tracked ?? 0) : '—'}
                  sub={vesselsAvailable ? 'tracked' : 'unavailable'} />
                <StatTile label="FLIGHTS"
                  value={flightsAvailable ? (flightData.total_tracked ?? 0) : '—'}
                  sub={flightsAvailable ? 'tracked' : 'unavailable'} />
                {topChokepoints.map(cp => (
                  <StatTile key={cp.name}
                    label={cp.name.toUpperCase().slice(0, 12)}
                    value={cp.avg_7d != null ? Math.round(cp.avg_7d) : '—'}
                    sub={cp.change_7d_pct != null
                      ? `${cp.change_7d_pct >= 0 ? '+' : ''}${cp.change_7d_pct}% 7d` : null}
                    color={cp.change_7d_pct == null ? undefined
                      : cp.change_7d_pct >= 0 ? 'var(--green)' : 'var(--red)'} />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
