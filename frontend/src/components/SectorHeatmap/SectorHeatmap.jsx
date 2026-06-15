import React from 'react'
import { useSectors } from '../../hooks/useMarketData'

function heatColor(pct) {
  if (pct == null) return '#1c2333'
  if (pct >  3)  return '#00695c'
  if (pct >  1)  return '#2e7d32'
  if (pct >  0)  return '#1b5e20'
  if (pct > -1)  return '#4a1500'
  if (pct > -3)  return '#7f1800'
  return '#b71c1c'
}

function textColor(pct) {
  if (pct == null) return 'var(--text-dim)'
  return pct >= 0 ? 'var(--green)' : 'var(--red)'
}

export default function SectorHeatmap() {
  const { data: sectors, loading } = useSectors()

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">🗺 Sector Heatmap</span>
        <span className="dim" style={{ fontSize: 9 }}>30s refresh</span>
      </div>
      <div className="panel-body" style={{ padding: 8 }}>
        {loading ? (
          <div style={{ color: 'var(--text-dim)', padding: 8 }}>Loading...</div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 4,
          }}>
            {(sectors || []).map(s => (
              <div key={s.symbol} style={{
                background:    heatColor(s.pct_change),
                border:        '1px solid #1c2333',
                borderRadius:  4,
                padding:       '8px 6px',
                textAlign:     'center',
              }}>
                <div style={{ color: 'var(--yellow)', fontSize: 11, fontWeight: 'bold' }}>
                  {s.symbol}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-secondary)', marginBottom: 2 }}>
                  {s.name}
                </div>
                <div style={{ fontSize: 12, fontWeight: 'bold', color: textColor(s.pct_change) }}>
                  {s.pct_change != null
                    ? `${s.pct_change >= 0 ? '+' : ''}${s.pct_change.toFixed(2)}%`
                    : '—'}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-dim)' }}>
                  ${s.price?.toFixed(2) || '—'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
