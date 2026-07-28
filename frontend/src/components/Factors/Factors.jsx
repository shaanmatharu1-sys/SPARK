import React, { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend,
} from 'recharts'
import { useFactorRankings } from '../../hooks/useMarketData'

const FACTOR_LABELS = {
  momentum:    'MOM',
  short_rev:   'REV',
  low_vol:     'LVOL',
  trend:       'TREND',
  vol_adj_mom: 'VAM',
}

const FACTOR_COLORS = {
  momentum:    'var(--green)',
  short_rev:   'var(--gold)',
  low_vol:     'var(--steel-bright)',
  trend:       'var(--purple)',
  vol_adj_mom: 'var(--cyan)',
}

// Heatmap color for a z-score value (-2..+2 -> red..green), built from the
// theme's --green (63,182,139) / --red (224,85,107) at varying alpha —
// same technique as SectorHeatmap's heat-cell scale.
function zColor(z) {
  if (z == null) return 'transparent'
  const clamped = Math.max(-2, Math.min(2, z))
  if (clamped >= 0) {
    const a = clamped / 2
    return `rgba(63, 182, 139, ${0.12 + a * 0.45})`
  } else {
    const a = -clamped / 2
    return `rgba(224, 85, 107, ${0.12 + a * 0.45})`
  }
}

function round4(v) { return Math.round(v * 10000) / 10000 }

function BookTag({ book }) {
  if (book === 'LONG')  return <span style={{ color: 'var(--green)', fontWeight: 'bold' }}>● LONG</span>
  if (book === 'SHORT') return <span style={{ color: 'var(--red)', fontWeight: 'bold' }}>● SHORT</span>
  return <span className="dim">—</span>
}

export default function Factors() {
  const [universe, setUniverse] = useState('watchlist')
  const [days, setDays] = useState(400)
  const { data, loading, error } = useFactorRankings(universe, days)

  const factorNames = data?.factor_names || []
  const chartData = useMemo(() => (
    (data?.rankings || []).slice().sort((a, b) => b.composite - a.composite)
  ), [data])

  // Additive decomposition: composite = sum(weight[f] * zscore[f]), so
  // stacking each factor's weighted contribution reconstructs the composite
  // bar exactly — showing whether a high score comes from broad consensus
  // across factors or is fragile (driven by just one).
  const contribData = useMemo(() => {
    if (!data?.weights) return []
    return chartData.map(r => {
      const row = { symbol: r.symbol }
      for (const f of factorNames) row[f] = round4((data.weights[f] || 0) * (r.factors[f] || 0))
      return row
    })
  }, [chartData, data, factorNames])

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Factor Rankings</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {['watchlist', 'sectors'].map(u => (
            <button key={u} onClick={() => setUniverse(u)} style={{
              background: universe === u ? 'var(--blue)' : 'transparent',
              color: universe === u ? '#fff' : 'var(--text-secondary)',
              border: '1px solid var(--border-accent)', borderRadius: 3,
              padding: '2px 8px', fontSize: 9, cursor: 'pointer', fontFamily: 'var(--font-mono)',
            }}>{u.toUpperCase()}</button>
          ))}
        </div>
      </div>
      <div className="panel-body">
        {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Computing factor exposures across universe...</div>}
        {error && <div style={{ padding: 16, color: 'var(--red)' }}>Error: {error}</div>}
        {data?.error && <div style={{ padding: 16, color: 'var(--red)' }}>{data.error}</div>}

        {chartData.length > 0 && (
          <div style={{ height: Math.min(280, Math.max(120, chartData.length * 16)), padding: '8px 10px 0' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ top: 2, right: 24, left: 0, bottom: 2 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fill: 'var(--text-dim)', fontSize: 8 }}
                       axisLine={{ stroke: 'var(--border-bright)' }} />
                <YAxis type="category" dataKey="symbol" width={44}
                       tick={{ fill: 'var(--text-dim)', fontSize: 9 }} axisLine={{ stroke: 'var(--border-bright)' }} />
                <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                         borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}
                         formatter={(v) => v.toFixed(3)} labelFormatter={(l) => `${l} composite`} />
                <Bar dataKey="composite">
                  {chartData.map(r => (
                    <Cell key={r.symbol} fill={r.composite >= 0 ? 'var(--green)' : 'var(--red)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {contribData.length > 0 && (
          <>
            <div className="dim" style={{ fontSize: 9, padding: '4px 10px 0' }}>
              PER-FACTOR BREAKDOWN — weighted contribution to composite (stacked bars sum back to the score above)
            </div>
            <div style={{ height: Math.min(280, Math.max(140, contribData.length * 16)), padding: '4px 10px 0' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={contribData} layout="vertical" margin={{ top: 2, right: 24, left: 0, bottom: 2 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: 'var(--text-dim)', fontSize: 8 }}
                         axisLine={{ stroke: 'var(--border-bright)' }} />
                  <YAxis type="category" dataKey="symbol" width={44}
                         tick={{ fill: 'var(--text-dim)', fontSize: 9 }} axisLine={{ stroke: 'var(--border-bright)' }} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                           borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}
                           formatter={(v, name) => [v.toFixed(3), FACTOR_LABELS[name] || name]} />
                  <Legend wrapperStyle={{ fontSize: 9 }} formatter={(name) => FACTOR_LABELS[name] || name} />
                  {factorNames.map(f => (
                    <Bar key={f} dataKey={f} stackId="contrib" fill={FACTOR_COLORS[f] || 'var(--text-dim)'} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}

        {data?.rankings && (
          <table className="bbg-table">
            <thead>
              <tr>
                <th>#</th>
                <th>SYMBOL</th>
                <th>COMPOSITE</th>
                {factorNames.map(f => <th key={f}>{FACTOR_LABELS[f] || f}</th>)}
                <th>PCTL</th>
                <th>BOOK</th>
              </tr>
            </thead>
            <tbody>
              {data.rankings.map(r => (
                <tr key={r.symbol}>
                  <td className="dim">{r.rank}</td>
                  <td style={{ color: 'var(--yellow)', fontWeight: 'bold' }}>{r.symbol}</td>
                  <td style={{
                    color: r.composite >= 0 ? 'var(--green)' : 'var(--red)',
                    fontWeight: 'bold',
                  }}>
                    {r.composite >= 0 ? '+' : ''}{r.composite.toFixed(3)}
                  </td>
                  {factorNames.map(f => (
                    <td key={f} style={{ background: zColor(r.factors[f]), textAlign: 'center' }}>
                      {r.factors[f] >= 0 ? '+' : ''}{r.factors[f]?.toFixed(2)}
                    </td>
                  ))}
                  <td className="dim">{r.percentile?.toFixed(0)}</td>
                  <td><BookTag book={r.book} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {data?.weights && (
          <div style={{ padding: '8px 10px', borderTop: '1px solid var(--border)', marginTop: 4 }}>
            <span className="dim" style={{ fontSize: 9 }}>
              WEIGHTS: {Object.entries(data.weights).map(([k, v]) =>
                `${FACTOR_LABELS[k] || k} ${(v * 100).toFixed(0)}%`).join('  ·  ')}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
