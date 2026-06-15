import React, { useState, useRef, useEffect } from 'react'
import { useNetwork } from '../../hooks/useMarketData'

// Sector -> color
const SECTOR_COLORS = {
  Tech: '#6BA3D4', Energy: '#E0A55C', Financials: '#3FB68B',
  Healthcare: '#C77DFF', Consumer: '#E0556B', Industrials: '#C9A84C',
  Unknown: '#5E789A',
}

function ForceGraph({ data }) {
  const canvasRef = useRef(null)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    if (!data?.nodes?.length) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const W = canvas.width = canvas.offsetWidth
    const H = canvas.height = canvas.offsetHeight

    // Initialize node positions in a circle
    const nodes = data.nodes.map((n, i) => {
      const angle = (i / data.nodes.length) * Math.PI * 2
      return { ...n, x: W/2 + Math.cos(angle)*150, y: H/2 + Math.sin(angle)*150,
               vx: 0, vy: 0 }
    })
    const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]))
    const edges = data.edges.map(e => ({ ...e, s: nodeById[e.source], t: nodeById[e.target] }))

    let raf
    let iterations = 0
    const simulate = () => {
      // Force-directed layout: repulsion + edge attraction + centering
      for (const n of nodes) { n.fx = 0; n.fy = 0 }
      // Repulsion between all nodes
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
      // Attraction along edges (stronger for higher correlation)
      for (const e of edges) {
        let dx = e.t.x - e.s.x, dy = e.t.y - e.s.y
        let dist = Math.sqrt(dx*dx + dy*dy) || 1
        const att = dist * 0.0008 * Math.abs(e.weight)
        e.s.fx += (dx/dist)*att*dist; e.s.fy += (dy/dist)*att*dist
        e.t.fx -= (dx/dist)*att*dist; e.t.fy -= (dy/dist)*att*dist
      }
      // Centering + integrate
      for (const n of nodes) {
        n.fx += (W/2 - n.x) * 0.01
        n.fy += (H/2 - n.y) * 0.01
        n.vx = (n.vx + n.fx) * 0.85
        n.vy = (n.vy + n.fy) * 0.85
        n.x += n.vx; n.y += n.vy
        n.x = Math.max(20, Math.min(W-20, n.x))
        n.y = Math.max(20, Math.min(H-20, n.y))
      }

      // Draw
      ctx.clearRect(0, 0, W, H)
      // Edges
      for (const e of edges) {
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
      // Nodes
      for (const n of nodes) {
        const r = 6 + n.degree * 2
        ctx.beginPath()
        ctx.arc(n.x, n.y, r, 0, Math.PI*2)
        ctx.fillStyle = SECTOR_COLORS[n.sector] || SECTOR_COLORS.Unknown
        ctx.fill()
        ctx.strokeStyle = '#0B1929'; ctx.lineWidth = 2; ctx.stroke()
        // Label
        ctx.fillStyle = '#E8EAED'
        ctx.font = '600 11px IBM Plex Mono, monospace'
        ctx.textAlign = 'center'
        ctx.fillText(n.id, n.x, n.y - r - 4)
      }

      iterations++
      if (iterations < 300) raf = requestAnimationFrame(simulate)
    }
    simulate()

    // Hover detection
    const onMove = (ev) => {
      const rect = canvas.getBoundingClientRect()
      const mx = ev.clientX - rect.left, my = ev.clientY - rect.top
      const hit = nodes.find(n => Math.hypot(n.x-mx, n.y-my) < 12)
      setHover(hit ? { id: hit.id, sector: hit.sector, degree: hit.degree,
                       avg_corr: hit.avg_corr, x: mx, y: my } : null)
    }
    canvas.addEventListener('mousemove', onMove)
    return () => { cancelAnimationFrame(raf); canvas.removeEventListener('mousemove', onMove) }
  }, [data])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
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
  const [threshold, setThreshold] = useState(0.4)
  const { data, loading } = useNetwork(symbols, threshold)

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
        <div style={{ flex: 1, position: 'relative' }}>
          {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Computing correlations…</div>}
          {data?.error && <div style={{ padding: 16, color: 'var(--red)' }}>{data.error}</div>}
          {data?.nodes && (
            <>
              <ForceGraph data={data} />
              <div style={{ position: 'absolute', bottom: 8, left: 12, fontSize: 10, color: 'var(--text-dim)' }}>
                {data.n_nodes} nodes · {data.n_edges} edges · {data.clusters?.length} clusters
                <span style={{ marginLeft: 10 }}>node size = connections · green/red = +/- correlation</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
