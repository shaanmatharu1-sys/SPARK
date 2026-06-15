import React, { useState } from 'react'
import { useMovers } from '../../hooks/useMarketData'

export default function Movers() {
  const [dir, setDir] = useState('gainers')
  const { data, loading } = useMovers(dir)

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Movers</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button className={`btn ${dir === 'gainers' ? 'active' : ''}`}
            onClick={() => setDir('gainers')}>GAINERS</button>
          <button className={`btn ${dir === 'losers' ? 'active' : ''}`}
            onClick={() => setDir('losers')}>LOSERS</button>
        </div>
      </div>
      <div className="panel-body">
        {loading ? <div style={{ padding: 16, color: 'var(--text-dim)' }}>Loading…</div> : (
          <table className="bbg-table">
            <thead>
              <tr><th>SYMBOL</th><th>PRICE</th><th>CHG%</th><th>VOLUME</th></tr>
            </thead>
            <tbody>
              {(data || []).slice(0, 25).map((m, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{m.symbol}</td>
                  <td>{m.price?.toFixed(2)}</td>
                  <td style={{ color: m.change_pct >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {m.change_pct >= 0 ? '+' : ''}{m.change_pct?.toFixed(2)}%
                  </td>
                  <td className="dim">{m.volume ? (m.volume/1e6).toFixed(1)+'M' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
