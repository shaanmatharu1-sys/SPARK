import React from 'react'
import { useCrypto } from '../../hooks/useMarketData'

export default function Crypto() {
  const { data, loading } = useCrypto()
  const coins = data ? Object.values(data) : []

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Crypto</span>
        <span className="dim" style={{ fontSize: 9 }}>24/7</span>
      </div>
      <div className="panel-body">
        {loading ? <div style={{ padding: 16, color: 'var(--text-dim)' }}>Loading…</div> : (
          <table className="bbg-table">
            <thead>
              <tr><th>PAIR</th><th>PRICE</th><th>CHG%</th><th>HIGH</th><th>LOW</th></tr>
            </thead>
            <tbody>
              {coins.map((c, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{c.symbol}</td>
                  <td>{c.price?.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                  <td style={{ color: c.change_pct >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {c.change_pct >= 0 ? '+' : ''}{c.change_pct?.toFixed(2)}%
                  </td>
                  <td className="dim">{c.high?.toLocaleString(undefined,{maximumFractionDigits:2})}</td>
                  <td className="dim">{c.low?.toLocaleString(undefined,{maximumFractionDigits:2})}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
