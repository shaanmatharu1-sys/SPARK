import React from 'react'
import { useMacroDashboard } from '../../hooks/useMarketData'

function MacroRow({ item }) {
  const { name, value, change, date } = item
  const up = change > 0
  const chgColor = change == null ? 'var(--text-dim)'
                 : up ? 'var(--green)' : 'var(--red)'

  return (
    <tr>
      <td style={{ color: 'var(--yellow)' }}>{name}</td>
      <td style={{ color: 'var(--text-primary)', fontWeight: 'bold' }}>
        {value != null ? value.toFixed(2) : '—'}
      </td>
      <td style={{ color: chgColor }}>
        {change != null ? `${change >= 0 ? '+' : ''}${change.toFixed(3)}` : '—'}
      </td>
      <td className="dim" style={{ fontSize: 10 }}>{date || '—'}</td>
    </tr>
  )
}

export default function MacroDashboard() {
  const { data, loading } = useMacroDashboard()

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Macro Dashboard</span>
        <span className="dim" style={{ fontSize: 9 }}>FRED</span>
      </div>
      <div className="panel-body">
        {loading ? (
          <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading FRED data...</div>
        ) : (
          <table className="bbg-table">
            <thead>
              <tr>
                <th>INDICATOR</th>
                <th>VALUE</th>
                <th>CHANGE</th>
                <th>DATE</th>
              </tr>
            </thead>
            <tbody>
              {data && Object.values(data).map((item, i) => (
                <MacroRow key={i} item={item} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
