import React, { useState } from 'react'
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { usePairs, usePairDetail } from '../../hooks/useMarketData'

function SignalTag({ signal }) {
  const map = {
    LONG_SPREAD:  { c: 'var(--green)', t: 'LONG SPREAD' },
    SHORT_SPREAD: { c: 'var(--red)', t: 'SHORT SPREAD' },
    AT_MEAN:      { c: 'var(--text-dim)', t: 'AT MEAN' },
    NEUTRAL:      { c: 'var(--text-secondary)', t: 'NEUTRAL' },
  }
  const s = map[signal] || map.NEUTRAL
  return <span style={{ color: s.c, fontWeight: 600, fontSize: 10 }}>{s.t}</span>
}

// ADF stat strength: more negative = more confidently stationary (classic
// ADF critical values are roughly -2.9/-3.4/-3.9 at 10/5/1%).
function adfColor(adf) {
  if (adf == null) return 'var(--text-primary)'
  if (adf < -3.9) return 'var(--green)'
  if (adf < -3.4) return 'rgba(63,182,139,0.75)'
  if (adf < -2.9) return 'var(--gold)'
  return 'var(--red)'
}

// Half-life acceptability: too fast is noisy, too slow ties up capital —
// the "sweet spot" for a tradeable mean-reversion is roughly 5-30 sessions.
function halfLifeColor(hl) {
  if (hl == null) return 'var(--text-primary)'
  if (hl >= 5 && hl <= 30) return 'var(--green)'
  if (hl < 5 || hl <= 45) return 'var(--gold)'
  return 'var(--red)'
}

function fmtDate(t) {
  if (t == null) return ''
  const d = new Date(t < 1e12 ? t * 1000 : t)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
}

function PairDetail({ y, x, onClose }) {
  const { data, loading, error } = usePairDetail(y, x)
  const chartData = (data?.spread || []).map((s, i) => ({
    t: data.dates?.[i],
    spread: s,
    z: data.zscore?.[i],
  }))

  return (
    <div className="panel" style={{ borderTop: '2px solid var(--gold)', flexShrink: 0 }}>
      <div className="panel-header">
        <span className="title">{y} / {x} — Spread &amp; Z-Score</span>
        <button className="btn" style={{ fontSize: 9 }} onClick={onClose}>Close ✕</button>
      </div>
      <div className="panel-body" style={{ padding: 10 }}>
        {loading && <div className="dim" style={{ fontSize: 11 }}>Loading spread history…</div>}
        {error && <div style={{ color: 'var(--red)', fontSize: 11 }}>Error: {error}</div>}
        {data?.error && <div style={{ color: 'var(--red)', fontSize: 11 }}>{data.error}</div>}
        {chartData.length > 1 && (
          <>
            <div style={{ display: 'flex', gap: 14, marginBottom: 8, fontSize: 10 }}>
              <span className="dim">HEDGE {data.hedge_ratio}</span>
              <span className="dim">CORR {data.correlation}</span>
              <span style={{ color: adfColor(data.adf_stat) }}>ADF {data.adf_stat}</span>
              <span style={{ color: halfLifeColor(data.half_life) }}>HALF-LIFE {data.half_life}d</span>
              <span style={{ color: Math.abs(data.spread_z) > 2 ? 'var(--gold-bright)' : 'var(--text-primary)' }}>
                Z {data.spread_z >= 0 ? '+' : ''}{data.spread_z}
              </span>
            </div>
            <div className="dim" style={{ fontSize: 9, marginBottom: 4 }}>SPREAD (raw, {y} − hedge×{x})</div>
            <div style={{ height: 130 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 2, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
                  <XAxis dataKey="t" tickFormatter={fmtDate} stroke="var(--text-dim)" fontSize={9} minTickGap={60} />
                  <YAxis stroke="var(--text-dim)" fontSize={9} width={50} domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 10 }}
                           labelFormatter={fmtDate} />
                  <Line type="monotone" dataKey="spread" stroke="var(--steel-bright)" dot={false} strokeWidth={1.3} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="dim" style={{ fontSize: 9, margin: '8px 0 4px' }}>ROLLING Z-SCORE (entry/exit reference)</div>
            <div style={{ height: 130 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 2, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
                  <XAxis dataKey="t" tickFormatter={fmtDate} stroke="var(--text-dim)" fontSize={9} minTickGap={60} />
                  <YAxis stroke="var(--text-dim)" fontSize={9} width={50} domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 10 }}
                           labelFormatter={fmtDate} />
                  <ReferenceLine y={0} stroke="var(--text-dim)" strokeDasharray="3 3" />
                  <ReferenceLine y={2} stroke="var(--red)" strokeDasharray="3 3" strokeOpacity={0.6} />
                  <ReferenceLine y={-2} stroke="var(--green)" strokeDasharray="3 3" strokeOpacity={0.6} />
                  <Line type="monotone" dataKey="z" stroke="var(--gold)" dot={false} strokeWidth={1.3} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="dim" style={{ fontSize: 9, marginTop: 6, lineHeight: 1.5 }}>
              Entries typically trigger near |z| &gt; 2 (red/green reference lines); the spread panel above shows
              whether the current extreme looks like prior reversions or an unprecedented drift.
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function Pairs() {
  const [universe, setUniverse] = useState('watchlist')
  const [selected, setSelected] = useState(null) // { y, x }
  const { data, loading, error } = usePairs(universe)

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <span className="title">Pairs / Stat-Arb</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {['watchlist', 'sectors'].map(u => (
            <button key={u} className={`btn ${universe === u ? 'active' : ''}`}
              onClick={() => setUniverse(u)}>{u.toUpperCase()}</button>
          ))}
        </div>
      </div>
      <div className="panel-body" style={{ flex: selected ? '0 1 auto' : 1, minHeight: 0, overflowY: 'auto' }}>
        {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Scanning for cointegrated pairs…</div>}
        {error && <div style={{ padding: 16, color: 'var(--red)' }}>Error: {error}</div>}
        {data?.error && <div style={{ padding: 16, color: 'var(--red)' }}>{data.error}</div>}
        {data?.pairs && (
          <>
            <div style={{ padding: '6px 12px', fontSize: 10, color: 'var(--text-dim)' }}>
              {data.n_cointegrated} cointegrated of {data.n_pairs_tested} tested — click a row for the spread chart
            </div>
            <table className="bbg-table">
              <thead>
                <tr><th>PAIR</th><th>HEDGE</th><th>CORR</th><th>ADF</th><th>HALF-LIFE</th><th>Z</th><th>SIGNAL</th></tr>
              </thead>
              <tbody>
                {data.pairs.map((p, i) => (
                  <tr key={i} onClick={() => setSelected({ y: p.y, x: p.x })}
                      style={{
                        cursor: 'pointer',
                        background: selected?.y === p.y && selected?.x === p.x ? 'var(--bg-raised)' : 'transparent',
                      }}>
                    <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{p.pair}</td>
                    <td>{p.hedge_ratio}</td>
                    <td>{p.correlation}</td>
                    <td style={{ color: adfColor(p.adf_stat), fontWeight: 600 }}>{p.adf_stat}</td>
                    <td style={{ color: halfLifeColor(p.half_life) }}>{p.half_life}d</td>
                    <td style={{ color: Math.abs(p.spread_z) > 2 ? 'var(--gold-bright)' : 'var(--text-primary)' }}>
                      {p.spread_z >= 0 ? '+' : ''}{p.spread_z}
                    </td>
                    <td><SignalTag signal={p.signal} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.pairs.length === 0 && (
              <div style={{ padding: 16, color: 'var(--text-dim)', fontSize: 11 }}>
                No tradeable cointegrated pairs found in this universe right now.
              </div>
            )}
          </>
        )}
      </div>
      {selected && (
        <PairDetail y={selected.y} x={selected.x} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
