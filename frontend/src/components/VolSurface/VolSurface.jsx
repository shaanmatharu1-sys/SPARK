import React, { useState, useEffect } from 'react'
import { useSymbol } from '../../hooks/useSymbol'
import {
  LineChart, Line, ScatterChart, Scatter, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ZAxis, Legend
} from 'recharts'
import { useVolSurface } from '../../hooks/useMarketData'
import Surface3D from './Surface3D'

function Metric({ label, value, color }) {
  return (
    <div style={{ flex: 1, textAlign: 'center', padding: '6px 4px',
                  background: 'var(--bg-base)', borderRadius: 3 }}>
      <div className="dim" style={{ fontSize: 8 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 'bold', color: color || 'var(--text-primary)' }}>
        {value}
      </div>
    </div>
  )
}

// Distinct colors per expiration for the smile scatter
const EXP_COLORS = [
  'var(--steel-bright)', 'var(--green)', 'var(--gold)', 'var(--purple)',
  'var(--red)', 'var(--cyan)', 'var(--gold-bright)',
]

// Mirrors SectorHeatmap.jsx's heat-color-scale pattern: red = elevated/expensive
// IV, green = cheap IV, relative to the min/max IV currently on the surface.
function ivHeatColor(iv, min, max) {
  if (iv == null || min === max) return 'transparent'
  const t = (iv - min) / (max - min)
  if (t > 0.83) return 'rgba(224,85,107,0.55)'
  if (t > 0.66) return 'rgba(224,85,107,0.35)'
  if (t > 0.5)  return 'rgba(224,85,107,0.18)'
  if (t > 0.33) return 'rgba(63,182,139,0.18)'
  if (t > 0.16) return 'rgba(63,182,139,0.35)'
  return 'rgba(63,182,139,0.55)'
}

export default function VolSurface() {
  const { symbol, setSymbol } = useSymbol()
  const [input, setInput]   = useState(symbol)
  useEffect(() => { setInput(symbol) }, [symbol])
  const { data, loading, error } = useVolSurface(symbol)

  const s = data?.summary || {}

  // Group surface points by expiration for the smile chart
  const smileByExp = React.useMemo(() => {
    if (!data?.surface_points) return []
    const groups = {}
    for (const p of data.surface_points) {
      (groups[p.expiration] ||= []).push({ moneyness: p.moneyness, iv: p.iv * 100 })
    }
    return Object.entries(groups)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([exp, pts], i) => ({
        exp,
        color: EXP_COLORS[i % EXP_COLORS.length],
        points: pts.sort((a, b) => a.moneyness - b.moneyness),
      }))
  }, [data])

  // Strike x expiration IV grid — bucket by moneyness (rounded to nearest 0.05)
  // since raw strikes differ per expiration, so cells align meaningfully across columns.
  const heatmap = React.useMemo(() => {
    if (!data?.surface_points?.length) return null
    const expirations = [...new Set(data.surface_points.map(p => p.expiration))].sort().slice(0, 8)
    const bucket = m => Math.round(m / 0.05) * 0.05
    const rows = {}
    for (const p of data.surface_points) {
      if (!expirations.includes(p.expiration)) continue
      const b = bucket(p.moneyness)
      rows[b] ||= {}
      const cell = rows[b][p.expiration]
      if (cell) { cell.sum += p.iv; cell.n += 1 } else { rows[b][p.expiration] = { sum: p.iv, n: 1 } }
    }
    const moneynessBuckets = Object.keys(rows).map(Number).sort((a, b) => b - a)
    let min = Infinity, max = -Infinity
    for (const b of moneynessBuckets) {
      for (const e of expirations) {
        const c = rows[b][e]
        if (c) { const v = c.sum / c.n; if (v < min) min = v; if (v > max) max = v }
      }
    }
    if (!isFinite(min)) return null
    return { expirations, moneynessBuckets, rows, min, max }
  }, [data])

  const termData = (data?.term_structure || [])
    .slice().sort((a, b) => a.T - b.T)
    .map(t => ({ exp: t.expiration?.slice(5), iv: (t.atm_iv * 100).toFixed(1), T: t.T }))

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Vol Surface</span>
        <input value={input} onChange={e => setInput(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && setSymbol(input)}
          style={{ background: 'var(--bg-base)', border: '1px solid var(--border-accent)',
                   color: 'var(--yellow)', padding: '2px 6px', fontSize: 10,
                   borderRadius: 3, width: 64, fontFamily: 'var(--font-mono)', fontWeight: 'bold' }} />
      </div>
      <div className="panel-body" style={{ padding: 8 }}>
        {loading && <div style={{ color: 'var(--text-dim)' }}>Solving IV surface for {symbol}...</div>}
        {error && <div style={{ color: 'var(--red)' }}>Error: {error}</div>}
        {data?.error && <div style={{ color: 'var(--red)', fontSize: 11 }}>{data.error}</div>}

        {data?.summary && (
          <>
            {/* Summary metrics */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
              <Metric label="ATM IV (FRONT)" value={s.atm_iv_front ? `${(s.atm_iv_front*100).toFixed(1)}%` : '—'} />
              <Metric label="ATM IV (BACK)" value={s.atm_iv_back ? `${(s.atm_iv_back*100).toFixed(1)}%` : '—'} />
              <Metric label="TERM"
                value={s.term_shape || '—'}
                color={s.term_shape === 'contango' ? 'var(--green)' : 'var(--red)'} />
              <Metric label="SKEW"
                value={s.skew_direction || '—'}
                color={s.skew_direction === 'put skew' ? 'var(--yellow)' : 'var(--blue-bright)'} />
            </div>

            {/* Term structure */}
            <div className="dim" style={{ fontSize: 9, margin: '4px 0' }}>ATM TERM STRUCTURE</div>
            <div style={{ height: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={termData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="exp" tick={{ fill: 'var(--text-dim)', fontSize: 8 }} axisLine={{ stroke: 'var(--border-bright)' }} />
                  <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 8 }} axisLine={{ stroke: 'var(--border-bright)' }}
                         tickFormatter={v => `${v}%`} width={38} domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                           borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}
                           formatter={v => `${v}%`} />
                  <Line type="monotone" dataKey="iv" stroke="var(--steel-bright)" strokeWidth={2}
                        dot={{ fill: 'var(--steel-bright)', r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Vol smile by expiration */}
            <div className="dim" style={{ fontSize: 9, margin: '8px 0 4px' }}>IV SMILE (by moneyness)</div>
            <div style={{ height: 140 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" dataKey="moneyness" name="moneyness"
                         domain={['auto', 'auto']} tick={{ fill: 'var(--text-dim)', fontSize: 8 }}
                         axisLine={{ stroke: 'var(--border-bright)' }}
                         tickFormatter={v => v.toFixed(2)} />
                  <YAxis type="number" dataKey="iv" name="IV"
                         tick={{ fill: 'var(--text-dim)', fontSize: 8 }} axisLine={{ stroke: 'var(--border-bright)' }}
                         tickFormatter={v => `${v.toFixed(0)}%`} width={38} domain={['auto', 'auto']} />
                  <ZAxis range={[20, 20]} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                           borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}
                           formatter={(v, n) => n === 'IV' ? `${v.toFixed(1)}%` : v.toFixed(3)} />
                  <Legend wrapperStyle={{ fontSize: 8 }} />
                  {smileByExp.slice(0, 5).map(g => (
                    <Scatter key={g.exp} name={g.exp.slice(5)} data={g.points}
                             fill={g.color} line={{ stroke: g.color, strokeWidth: 1 }} lineType="joint" />
                  ))}
                </ScatterChart>
              </ResponsiveContainer>
            </div>

            {/* True 3D IV surface: moneyness x time-to-expiry x IV, interpolated mesh */}
            {data.surface_points?.length > 3 && (
              <>
                <div className="dim" style={{ fontSize: 9, margin: '8px 0 4px' }}>
                  3D IV SURFACE — drag to rotate, scroll to zoom (blue = cheap, red = elevated)
                </div>
                <Surface3D points={data.surface_points} />
              </>
            )}

            {/* IV surface heatmap: strike (moneyness) x expiration grid */}
            {heatmap && (
              <>
                <div className="dim" style={{ fontSize: 9, margin: '8px 0 4px' }}>
                  IV SURFACE (TABLE) — strike vs expiration (red = elevated IV, green = cheap IV)
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 9 }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left', padding: '2px 4px', color: 'var(--text-dim)' }}>MNY</th>
                        {heatmap.expirations.map(e => (
                          <th key={e} style={{ padding: '2px 4px', color: 'var(--text-dim)', fontWeight: 500 }}>
                            {e.slice(5)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {heatmap.moneynessBuckets.map(b => (
                        <tr key={b}>
                          <td style={{ padding: '2px 4px', color: 'var(--text-dim)' }}>{b.toFixed(2)}</td>
                          {heatmap.expirations.map(e => {
                            const c = heatmap.rows[b][e]
                            const iv = c ? c.sum / c.n : null
                            return (
                              <td key={e} style={{
                                padding: '3px 4px', textAlign: 'center',
                                background: ivHeatColor(iv, heatmap.min, heatmap.max),
                              }}>
                                {iv != null ? (iv * 100).toFixed(0) : '—'}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {/* Skew table */}
            {data.skew?.length > 0 && (
              <table className="bbg-table" style={{ marginTop: 8 }}>
                <thead>
                  <tr><th>EXP</th><th>RISK REV</th><th>BFLY</th><th>PUT IV</th><th>CALL IV</th></tr>
                </thead>
                <tbody>
                  {data.skew.map(sk => (
                    <tr key={sk.expiration}>
                      <td style={{ fontSize: 10 }}>{sk.expiration?.slice(5)}</td>
                      <td style={{ color: sk.risk_reversal > 0 ? 'var(--yellow)' : 'var(--blue-bright)' }}>
                        {sk.risk_reversal >= 0 ? '+' : ''}{(sk.risk_reversal * 100).toFixed(2)}
                      </td>
                      <td>{(sk.butterfly * 100).toFixed(2)}</td>
                      <td>{(sk.put_iv * 100).toFixed(1)}%</td>
                      <td>{(sk.call_iv * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </div>
  )
}
