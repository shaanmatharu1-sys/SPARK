import React, { useState } from 'react'
import { useUnusualActivity } from '../../hooks/useMarketData'

function Flag({ label }) {
  const colors = {
    CALL:          { bg: '#1a4a2e', color: '#00c853' },
    PUT:           { bg: '#4a1a1f', color: '#ff3d57' },
    HIGH_VOL_OI:   { bg: '#1a1a4a', color: '#7c4dff' },
    ITM:           { bg: '#1a3a1a', color: '#69f0ae' },
    OTM:           { bg: '#2a2010', color: '#ffd54f' },
  }
  const style = colors[label] || { bg: '#1c2333', color: '#c8d6e5' }
  return (
    <span style={{
      background: style.bg, color: style.color,
      padding: '1px 5px', borderRadius: 2, fontSize: 8,
      marginRight: 3, fontWeight: 'bold',
    }}>
      {label}
    </span>
  )
}

export default function UnusualActivity() {
  const [symbol, setSymbol] = useState('')
  const [filter, setFilter] = useState(null)
  const { data: activity, loading } = useUnusualActivity(filter)

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Unusual Activity</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <input
            value={symbol}
            onChange={e => setSymbol(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && setFilter(symbol || null)}
            placeholder="TICKER..."
            style={{
              background: '#0a0c10', border: '1px solid var(--border-accent)',
              color: 'var(--yellow)', padding: '2px 6px',
              fontSize: 9, borderRadius: 3, fontFamily: 'Courier New', width: 70,
            }}
          />
        </div>
      </div>
      <div className="panel-body">
        <table className="bbg-table">
          <thead>
            <tr>
              <th>CONTRACT</th>
              <th>TYPE</th>
              <th>STRIKE</th>
              <th>EXP</th>
              <th>VOL</th>
              <th>OI</th>
              <th>FLAGS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ color: 'var(--text-dim)', padding: 12 }}>
                Loading unusual activity...
              </td></tr>
            ) : (activity || []).slice(0, 30).map((c, i) => {
              const det = c.details || {}
              const day = c.day || {}
              return (
                <tr key={i}>
                  <td style={{ color: 'var(--yellow)', fontSize: 10 }}>
                    {det.underlying_ticker || '—'}
                  </td>
                  <td style={{
                    color: det.contract_type === 'call' ? 'var(--green)' : 'var(--red)',
                    fontWeight: 'bold',
                  }}>
                    {(det.contract_type || '').toUpperCase()}
                  </td>
                  <td>${det.strike_price || '—'}</td>
                  <td style={{ fontSize: 10 }}>{det.expiration_date || '—'}</td>
                  <td>{day.volume?.toLocaleString() || '—'}</td>
                  <td className="dim">{c.open_interest?.toLocaleString() || '—'}</td>
                  <td>
                    {(c.flags || []).map(f => <Flag key={f} label={f} />)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
