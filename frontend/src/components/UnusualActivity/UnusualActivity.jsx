import React, { useState } from 'react'
import { useUnusualActivity } from '../../hooks/useMarketData'

function Flag({ label }) {
  const colors = {
    CALL:          { bg: 'var(--green-dim)', color: 'var(--green)' },
    PUT:           { bg: 'var(--red-dim)', color: 'var(--red)' },
    HIGH_VOL_OI:   { bg: 'rgba(155,139,212,0.18)', color: 'var(--purple)' },
    ITM:           { bg: 'var(--green-dim)', color: 'var(--green)' },
    OTM:           { bg: 'rgba(201,168,76,0.18)', color: 'var(--gold-bright)' },
  }
  const style = colors[label] || { bg: 'var(--bg-raised)', color: 'var(--text-secondary)' }
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
              background: 'var(--bg-base)', border: '1px solid var(--border-accent)',
              color: 'var(--yellow)', padding: '2px 6px',
              fontSize: 9, borderRadius: 3, fontFamily: 'var(--font-mono)', width: 70,
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
                <tr key={det.ticker || `${det.underlying_ticker}-${det.contract_type}-${det.strike_price}-${det.expiration_date}` || i}>
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
