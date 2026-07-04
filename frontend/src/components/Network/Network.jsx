import React, { useState, useRef, useEffect, useMemo } from 'react'
import { useNetwork } from '../../hooks/useMarketData'

// Sector -> color
const SECTOR_COLORS = {
  Tech: '#6BA3D4', Energy: '#E0A55C', Financials: '#3FB68B',
  Healthcare: '#C77DFF', Consumer: '#E0556B', Industrials: '#C9A84C',
  Unknown: '#5E789A',
}

// Distinct outline colors per connected-component cluster (cycles if more
// clusters than colors — unlikely at the 40-symbol cap this tab enforces).
const CLUSTER_COLORS = [
  '#F2C14E', '#E85D75', '#5FD4C4', '#9B7EDE', '#F28C4E', '#6FCF97', '#4EA8DE',
]

function Legend() {
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', padding: '4px 12px 8px' }}>
      {Object.entries(SECTOR_COLORS).map(([sector, c]) => (
        <div key={sector} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: c, display: 'inline-block' }} />
          <span className="dim" style={{ fontSize: 9 }}>{sector}</span>
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ width: 9, height: 9, borderRadius: '50%', border: `2px solid ${CLUSTER_COLORS[0]}`, display: 'inline-block' }} />
        <span className="dim" style={{ fontSize: 9 }}>ring = cluster</span>
      </div>
    </div>
  )
}

function ForceGraph({ nodes: rawNodes, edges, clusterOf }) {
  const canvasRef = useRef(null)
  const [hover, setHover] = useState(null)
  const stateRef = useRef(null) // { nodes, edges, view: {scale,offsetX,offsetY}, drag, pan }

  useEffect(() => {
    if (!rawNodes?.length) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    let W = canvas.width = canvas.offsetWidth
    let H = canvas.height = canvas.offsetHeight

    const nodes = rawNodes.map((n, i) => {
      const angle = (i / rawNodes.length) * Math.PI * 2
      return { ...n, x: W/2 + Math.cos(angle)*150, y: H/2 + Math.sin(angle)*150,
               vx: 0, vy: 0, pinned: false }
    })
    const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]))
    const liveEdges = edges.map(e => ({ ...e, s: nodeById[e.source], t: nodeById[e.target] }))
      .filter(e => e.s && e.t)

    const view = { scale: 1, offsetX: 0, offsetY: 0 }
    const state = { nodes, edges: liveEdges, view, drag: null, panning: null }
    stateRef.current = state

    const toWorld = (clientX, clientY) => {
      const rect = canvas.getBoundingClientRect()
      const sx = clientX - rect.left, sy = clientY - rect.top
      return { x: (sx - view.offsetX) / view.scale, y: (sy - view.offsetY) / view.scale }
    }

    const draw = () => {
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.clearRect(0, 0, W, H)
      ctx.setTransform(view.scale, 0, 0, view.scale, view.offsetX, view.offsetY)

      for (const e of liveEdges) {
        ctx.beginPath()
        ctx.moveTo(e.s.x, e.s.y)
        ctx.lineTo(e.t.x, e.t.y)
        const pos = e.weight >= 0
        ctx.strokeStyle = pos
          ? `rgba(63,182,139,${0.15 + Math.abs(e.weight)*0.5})`
          : `rgba(224,85,107,${0.15 + Math.abs(e.weight)*0.5})`
        ctx.lineWidth = Math.abs(e.weight) * 3
        ctx.stroke()
      }

      // Nodes, sorted by degree so important nodes draw (and label) on top
      const byDegree = [...nodes].sort((a, b) => b.degree - a.degree)
      const drawnLabelBoxes = []
      ctx.font = '600 11px IBM Plex Mono, monospace'
      ctx.textAlign = 'center'
      for (const n of byDegree) {
        const r = 6 + n.degree * 2
        ctx.beginPath()
        ctx.arc(n.x, n.y, r, 0, Math.PI*2)
        ctx.fillStyle = SECTOR_COLORS[n.sector] || SECTOR_COLORS.Unknown
        ctx.fill()
        ctx.strokeStyle = '#0B1929'; ctx.lineWidth = 2; ctx.stroke()

        const cluster = clusterOf.get(n.id)
        if (cluster != null) {
          ctx.beginPath()
          ctx.arc(n.x, n.y, r + 3, 0, Math.PI*2)
          ctx.strokeStyle = CLUSTER_COLORS[cluster % CLUSTER_COLORS.length]
          ctx.lineWidth = 1.5
          ctx.stroke()
        }

        // Label collision avoidance: skip if it would overlap an
        // already-placed (higher-degree) label's bounding box.
        const textWidth = ctx.measureText(n.id).width
        const boxX = n.x - textWidth/2, boxY = n.y - r - 14
        const box = { x: boxX, y: boxY, w: textWidth, h: 12 }
        const overlaps = drawnLabelBoxes.some(b =>
          box.x < b.x + b.w && box.x + box.w > b.x && box.y < b.y + b.h && box.y + box.h > b.y)
        if (!overlaps) {
          ctx.fillStyle = '#E8EAED'
          ctx.fillText(n.id, n.x, n.y - r - 4)
          drawnLabelBoxes.push(box)
        }
      }
    }

    let raf
    let iterations = 0
    const SETTLE_ITERS = 300
    const step = () => {
      if (iterations < SETTLE_ITERS) {
        for (const n of nodes) { n.fx = 0; n.fy = 0 }
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i+1; j < nodes.length; j++) {
            const a = nodes[i], b = nodes[j]
            let dx = a.x - b.x, dy = a.y - b.y
            let dist = Math.sqrt(dx*dx + dy*dy) || 1
            const rep = 2200 / (dist*dist)
            a.fx += (dx/dist)*rep; a.fy += (dy/dist)*rep
            b.fx -= (dx/dist)*rep; b.fy -= (dy/dist)*rep
          }
        }
        for (const e of liveEdges) {
          let dx = e.t.x - e.s.x, dy = e.t.y - e.s.y
          let dist = Math.sqrt(dx*dx + dy*dy) || 1
          const att = dist * 0.0008 * Math.abs(e.weight)
          e.s.fx += (dx/dist)*att*dist; e.s.fy += (dy/dist)*att*dist
          e.t.fx -= (dx/dist)*att*dist; e.t.fy -= (dy/dist)*att*dist
        }
        for (const n of nodes) {
          if (n.pinned) { n.vx = 0; n.vy = 0; continue }
          n.fx += (W/2 - n.x) * 0.01
          n.fy += (H/2 - n.y) * 0.01
          n.vx = (n.vx + n.fx) * 0.85
          n.vy = (n.vy + n.fy) * 0.85
          n.x += n.vx; n.y += n.vy
          n.x = Math.max(20, Math.min(W-20, n.x))
          n.y = Math.max(20, Math.min(H-20, n.y))
        }
        iterations++
      }
      draw()
      raf = requestAnimationFrame(step)
    }
    step()

    const onMouseDown = (ev) => {
      const { x, y } = toWorld(ev.clientX, ev.clientY)
      const hit = nodes.find(n => Math.hypot(n.x-x, n.y-y) < 12)
      if (hit) {
        hit.pinned = true
        state.drag = { node: hit }
      } else {
        state.panning = { startX: ev.clientX, startY: ev.clientY,
                          origOffsetX: view.offsetX, origOffsetY: view.offsetY }
      }
    }
    const onMouseMove = (ev) => {
      if (state.drag) {
        const { x, y } = toWorld(ev.clientX, ev.clientY)
        state.drag.node.x = x; state.drag.node.y = y
        draw()
        return
      }
      if (state.panning) {
        view.offsetX = state.panning.origOffsetX + (ev.clientX - state.panning.startX)
        view.offsetY = state.panning.origOffsetY + (ev.clientY - state.panning.startY)
        draw()
        return
      }
      const { x, y } = toWorld(ev.clientX, ev.clientY)
      const hit = nodes.find(n => Math.hypot(n.x-x, n.y-y) < 12)
      const rect = canvas.getBoundingClientRect()
      setHover(hit ? { id: hit.id, sector: hit.sector, degree: hit.degree,
                       avg_corr: hit.avg_corr, x: ev.clientX - rect.left, y: ev.clientY - rect.top } : null)
    }
    const onMouseUp = () => {
      if (state.drag) state.drag.node.pinned = true
      state.drag = null
      state.panning = null
    }
    const onWheel = (ev) => {
      ev.preventDefault()
      const rect = canvas.getBoundingClientRect()
      const mx = ev.clientX - rect.left, my = ev.clientY - rect.top
      const worldX = (mx - view.offsetX) / view.scale
      const worldY = (my - view.offsetY) / view.scale
      const delta = ev.deltaY > 0 ? 0.9 : 1.1
      const newScale = Math.max(0.4, Math.min(3, view.scale * delta))
      view.offsetX = mx - worldX * newScale
      view.offsetY = my - worldY * newScale
      view.scale = newScale
      draw()
    }
    canvas.addEventListener('mousedown', onMouseDown)
    canvas.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })

    const ro = new ResizeObserver(() => {
      const newW = canvas.offsetWidth, newH = canvas.offsetHeight
      if (!newW || !newH || (newW === W && newH === H)) return
      // Rescale node positions proportionally — without this, nodes laid out
      // against the canvas's pre-layout size (often much smaller, since this
      // fires again once the real flex/grid size resolves) stay pinned at
      // their old coordinates and end up squished in a corner.
      const sx = newW / W, sy = newH / H
      for (const n of nodes) { n.x *= sx; n.y *= sy }
      W = newW; H = newH
      canvas.width = W; canvas.height = H
      draw()
    })
    ro.observe(canvas)

    return () => {
      cancelAnimationFrame(raf)
      canvas.removeEventListener('mousedown', onMouseDown)
      canvas.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('wheel', onWheel)
      ro.disconnect()
    }
  }, [rawNodes, edges, clusterOf])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block', cursor: 'grab' }} />
      <div className="dim" style={{ position: 'absolute', top: 6, right: 10, fontSize: 9, pointerEvents: 'none' }}>
        drag node to move · drag background to pan · scroll to zoom
      </div>
      {hover && (
        <div style={{ position: 'absolute', left: hover.x + 12, top: hover.y + 12,
                      background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                      borderRadius: 6, padding: '6px 10px', pointerEvents: 'none', zIndex: 10 }}>
          <div style={{ color: 'var(--gold)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{hover.id}</div>
          <div className="dim" style={{ fontSize: 10 }}>{hover.sector}</div>
          <div className="dim" style={{ fontSize: 10 }}>connections: {hover.degree} · avg corr: {hover.avg_corr}</div>
        </div>
      )}
    </div>
  )
}

export default function Network() {
  const [input, setInput] = useState('AAPL,MSFT,NVDA,GOOGL,META,AMZN,XOM,CVX,JPM,BAC,WMT,TGT')
  const [symbols, setSymbols] = useState('AAPL,MSFT,NVDA,GOOGL,META,AMZN,XOM,CVX,JPM,BAC,WMT,TGT')
  const [fetchThreshold] = useState(0.2) // fetch the widest reasonable set once; slider below re-filters client-side
  const [threshold, setThreshold] = useState(0.4)
  const { data, loading } = useNetwork(symbols, fetchThreshold)

  // Re-filter edges from the unfiltered all_correlations client-side as the
  // slider moves, instead of refetching per drag (see backend/analytics/
  // network/engine.py — all_correlations carries every pair, edges/clusters
  // from the API response only reflect fetchThreshold).
  const edges = useMemo(() => {
    if (!data?.all_correlations) return data?.edges || []
    return data.all_correlations.filter(e => Math.abs(e.weight) >= threshold)
  }, [data, threshold])

  const clusters = useMemo(() => {
    if (!data?.nodes) return []
    const adj = {}
    for (const n of data.nodes) adj[n.id] = []
    for (const e of edges) { adj[e.source]?.push(e.target); adj[e.target]?.push(e.source) }
    const seen = new Set(), comps = []
    for (const n of data.nodes) {
      if (seen.has(n.id)) continue
      const comp = [], stack = [n.id]
      while (stack.length) {
        const s = stack.pop()
        if (seen.has(s)) continue
        seen.add(s); comp.push(s)
        stack.push(...adj[s].filter(x => !seen.has(x)))
      }
      comps.push(comp)
    }
    comps.sort((a, b) => b.length - a.length)
    return comps
  }, [data, edges])

  const clusterOf = useMemo(() => {
    const m = new Map()
    clusters.forEach((comp, i) => comp.forEach(id => m.set(id, i)))
    return m
  }, [clusters])

  // Node degree also needs to reflect the re-filtered edge set, not just the
  // server's original fetchThreshold-based degree.
  const nodes = useMemo(() => {
    if (!data?.nodes) return []
    const degree = {}
    for (const n of data.nodes) degree[n.id] = 0
    for (const e of edges) { degree[e.source]++; degree[e.target]++ }
    return data.nodes.map(n => ({ ...n, degree: degree[n.id] ?? n.degree }))
  }, [data, edges])

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Correlation Network</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span className="dim" style={{ fontSize: 9 }}>THRESHOLD</span>
          <input type="range" min="0.2" max="0.9" step="0.05" value={threshold}
            onChange={e => setThreshold(parseFloat(e.target.value))} style={{ width: 80 }} />
          <span className="mono" style={{ fontSize: 11, color: 'var(--gold)' }}>{threshold}</span>
        </div>
      </div>
      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: 10, display: 'flex', gap: 6, borderBottom: '1px solid var(--border)' }}>
          <input className="input" style={{ flex: 1, fontFamily: 'var(--font-mono)' }}
            value={input} onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && setSymbols(input)}
            placeholder="Enter symbols, comma-separated" />
          <button className="btn active" onClick={() => setSymbols(input)}>Map</button>
        </div>
        <Legend />
        <div style={{ flex: 1, position: 'relative' }}>
          {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Computing correlations…</div>}
          {data?.error && <div style={{ padding: 16, color: 'var(--red)' }}>{data.error}</div>}
          {data?.nodes && (
            <>
              <ForceGraph nodes={nodes} edges={edges} clusterOf={clusterOf} />
              <div style={{ position: 'absolute', bottom: 8, left: 12, fontSize: 10, color: 'var(--text-dim)' }}>
                {nodes.length} nodes · {edges.length} edges · {clusters.length} clusters
                <span style={{ marginLeft: 10 }}>node size = connections · green/red = +/- correlation</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
