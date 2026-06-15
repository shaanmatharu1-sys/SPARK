import React, { useState } from 'react'
import { useFactorRankings } from '../../hooks/useMarketData'

const FACTOR_LABELS = {
  momentum:    'MOM',
  short_rev:   'REV',
  low_vol:     'LVOL',
  trend:       'TREND',
  vol_adj_mom: 'VAM',
}

// Heatmap color for a z-score value (-2..+2 -> red..green)
function zColor(z) {
  if (z == null) return 'transparent'
  const clamped = Math.max(-2, Math.min(2, z))
  if (clamped >= 0) {
    const a = clamped / 2
    return `rgba(0, 200, 83, ${0.12 + a * 0.45})`
  } else {
    const a = -clamped / 2
    return `rgba(255, 61, 87, ${0.12 + a * 0.45})`
  }
}

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
              padding: '2px 8px', fontSize: 9, cursor: 'pointer', fontFamily: 'Courier New',
            }}>{u.toUpperCase()}</button>
          ))}
        </div>
      </div>
      <div className="panel-body">
        {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Computing factor exposures across universe...</div>}
        {error && <div style={{ padding: 16, color: 'var(--red)' }}>Error: {error}</div>}
        {data?.error && <div style={{ padding: 16, color: 'var(--red)' }}>{data.error}</div>}

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
