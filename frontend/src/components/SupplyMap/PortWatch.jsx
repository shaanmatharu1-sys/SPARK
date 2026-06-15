import React from 'react'
import { usePortWatch } from '../../hooks/useMarketData'

const chgColor = (p) => p == null ? 'var(--text-dim)' : p > 1 ? 'var(--green)' : p < -1 ? 'var(--red)' : 'var(--text)'

function Spark({ data, w = 70, h = 20, color = '#6BA3D4' }) {
  if (!data || data.length < 2) return null
  const min = Math.min(...data), max = Math.max(...data), rng = max - min || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / rng) * h}`).join(' ')
  return <svg width={w} height={h} style={{ display: 'block' }}><polyline points={pts} fill="none" stroke={color} strokeWidth="1.2" /></svg>
}

function ChokeRow({ c }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12, color: 'var(--text)' }}>{c.name}</div>
        <div className="dim" style={{ fontSize: 9 }}>{c.avg_7d} transits/day (7d avg)</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Spark data={c.spark} color={c.change_7d_pct >= 0 ? '#3FB68B' : '#E0556B'} />
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: chgColor(c.change_7d_pct),
                      minWidth: 52, textAlign: 'right' }}>
          {c.change_7d_pct == null ? '—' : `${c.change_7d_pct >= 0 ? '+' : ''}${c.change_7d_pct}%`}
        </div>
      </div>
    </div>
  )
}

function PortRow({ p }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ minWidth: 0 }}>
        <span style={{ fontSize: 12, color: 'var(--text)' }}>{p.name}</span>
        <span className="dim" style={{ fontSize: 9, marginLeft: 6 }}>{p.country}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="dim" style={{ fontSize: 11 }}>{p.avg_7d}/day</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: chgColor(p.change_7d_pct),
                       minWidth: 48, textAlign: 'right' }}>
          {p.change_7d_pct == null ? '—' : `${p.change_7d_pct >= 0 ? '+' : ''}${p.change_7d_pct}%`}
        </span>
      </div>
    </div>
  )
}

export default function PortWatch() {
  const { data, loading } = usePortWatch()
  const chokes = data?.chokepoints
  const ports = data?.ports

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%' }}>
      <div className="panel" style={{ flex: 1, minHeight: 0 }}>
        <div className="panel-header">
          <span className="title">Chokepoint Transit Trends</span>
          <span className="dim" style={{ fontSize: 9 }}>IMF PortWatch · weekly</span>
        </div>
        <div className="panel-body" style={{ padding: '4px 12px' }}>
          {loading && <div className="dim" style={{ fontSize: 11 }}>Loading PortWatch data…</div>}
          {chokes && chokes.available === false &&
            <div className="dim" style={{ fontSize: 11, padding: 8 }}>{chokes.reason}</div>}
          {chokes?.chokepoints?.map(c => <ChokeRow key={c.name} c={c} />)}
        </div>
      </div>

      <div className="panel" style={{ flex: 1, minHeight: 0 }}>
        <div className="panel-header">
          <span className="title">Port Activity</span>
          <span className="dim" style={{ fontSize: 9 }}>top ports by calls/day</span>
        </div>
        <div className="panel-body" style={{ padding: '4px 12px' }}>
          {ports && ports.available === false &&
            <div className="dim" style={{ fontSize: 11, padding: 8 }}>{ports.reason}</div>}
          {ports?.ports?.map(p => <PortRow key={p.name} p={p} />)}
          <div className="dim" style={{ fontSize: 9, marginTop: 8, lineHeight: 1.5 }}>
            Official IMF PortWatch data from satellite AIS (~90k ships, 2,065 ports,
            28 chokepoints). Updated weekly Tuesdays. % is 7-day vs prior 7-day change.
          </div>
        </div>
      </div>
    </div>
  )
}
