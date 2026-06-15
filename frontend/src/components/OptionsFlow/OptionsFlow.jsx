import React, { useState } from 'react'
import { useOptionsSnapshot } from '../../hooks/useMarketData'

function fmt(n, d = 4) {
  return n != null ? Number(n).toFixed(d) : '—'
}

export default function OptionsFlow() {
  const [symbol, setSymbol] = useState('SPY')
  const [input, setInput]   = useState('SPY')
  const [filter, setFilter] = useState('all') // all | call | put

  const { data: contracts, loading } = useOptionsSnapshot(symbol)

  const filtered = (contracts || []).filter(c => {
    const type = c.details?.contract_type || ''
    if (filter === 'call') return type === 'call'
    if (filter === 'put')  return type === 'put'
    return true
  })

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Options Flow — Greeks</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {['all','call','put'].map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{
              background: filter === f ? 'var(--blue)' : 'transparent',
              color:       filter === f ? '#fff' : 'var(--text-secondary)',
              border: '1px solid var(--border-accent)', borderRadius: 3,
              padding: '2px 6px', fontSize: 9, cursor: 'pointer', fontFamily: 'Courier New',
            }}>
              {f.toUpperCase()}
            </button>
          ))}
          <input
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && setSymbol(input)}
            style={{
              background: '#0a0c10', border: '1px solid var(--border-accent)',
              color: 'var(--yellow)', padding: '2px 6px', fontSize: 9,
              borderRadius: 3, fontFamily: 'Courier New', width: 60,
            }}
          />
        </div>
      </div>
      <div className="panel-body">
        <table className="bbg-table">
          <thead>
            <tr>
              <th>TYPE</th>
              <th>STRIKE</th>
              <th>EXP</th>
              <th>BID</th>
              <th>ASK</th>
              <th>IV</th>
              <th>DELTA</th>
              <th>GAMMA</th>
              <th>THETA</th>
              <th>VEGA</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} style={{ color: 'var(--text-dim)', padding: 12 }}>
                Loading options chain for {symbol}...
              </td></tr>
            ) : filtered.slice(0, 50).map((c, i) => {
              const det  = c.details || {}
              const day  = c.day || {}
              const g    = c.greeks || {}
              const isCall = det.contract_type === 'call'
              return (
                <tr key={i}>
                  <td style={{
                    color: isCall ? 'var(--green)' : 'var(--red)', fontWeight: 'bold',
                  }}>
                    {(det.contract_type || '').toUpperCase()}
                  </td>
                  <td>${det.strike_price || '—'}</td>
                  <td style={{ fontSize: 10 }}>{det.expiration_date || '—'}</td>
                  <td>{fmt(day.open, 2)}</td>
                  <td>{fmt(day.close, 2)}</td>
                  <td style={{ color: 'var(--purple)' }}>
                    {c.implied_volatility != null
                      ? `${(c.implied_volatility * 100).toFixed(1)}%`
                      : '—'}
                  </td>
                  <td style={{ color: isCall ? 'var(--green)' : 'var(--red)' }}>
                    {fmt(g.delta, 3)}
                  </td>
                  <td>{fmt(g.gamma, 4)}</td>
                  <td className="red">{fmt(g.theta, 4)}</td>
                  <td style={{ color: 'var(--blue-bright)' }}>{fmt(g.vega, 4)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
