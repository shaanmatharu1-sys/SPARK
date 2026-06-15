import React, { useState } from 'react'
import { usePairs } from '../../hooks/useMarketData'

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

export default function Pairs() {
  const [universe, setUniverse] = useState('watchlist')
  const { data, loading, error } = usePairs(universe)

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Pairs / Stat-Arb</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {['watchlist', 'sectors'].map(u => (
            <button key={u} className={`btn ${universe === u ? 'active' : ''}`}
              onClick={() => setUniverse(u)}>{u.toUpperCase()}</button>
          ))}
        </div>
      </div>
      <div className="panel-body">
        {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Scanning for cointegrated pairs…</div>}
        {error && <div style={{ padding: 16, color: 'var(--red)' }}>Error: {error}</div>}
        {data?.error && <div style={{ padding: 16, color: 'var(--red)' }}>{data.error}</div>}
        {data?.pairs && (
          <>
            <div style={{ padding: '6px 12px', fontSize: 10, color: 'var(--text-dim)' }}>
              {data.n_cointegrated} cointegrated of {data.n_pairs_tested} tested
            </div>
            <table className="bbg-table">
              <thead>
                <tr><th>PAIR</th><th>HEDGE</th><th>CORR</th><th>ADF</th><th>HALF-LIFE</th><th>Z</th><th>SIGNAL</th></tr>
              </thead>
              <tbody>
                {data.pairs.map((p, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{p.pair}</td>
                    <td>{p.hedge_ratio}</td>
                    <td>{p.correlation}</td>
                    <td style={{ color: p.adf_stat < -3 ? 'var(--green)' : 'var(--text-primary)' }}>{p.adf_stat}</td>
                    <td>{p.half_life}d</td>
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
    </div>
  )
}
