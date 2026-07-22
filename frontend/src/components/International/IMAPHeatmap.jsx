import React from 'react'
import { useInternational } from '../../hooks/useMarketData'

// IMAP — global equity performance heatmap. Same heat-cell pattern as
// SectorHeatmap.jsx, applied to world indices instead of US sectors.
function heatColor(pct) {
  if (pct == null) return 'var(--bg-raised)'
  if (pct >  3)  return 'rgba(63,182,139,0.55)'
  if (pct >  1)  return 'rgba(63,182,139,0.35)'
  if (pct >  0)  return 'rgba(63,182,139,0.18)'
  if (pct > -1)  return 'rgba(224,85,107,0.18)'
  if (pct > -3)  return 'rgba(224,85,107,0.35)'
  return 'rgba(224,85,107,0.55)'
}
function textColor(pct) {
  if (pct == null) return 'var(--text-dim)'
  return pct >= 0 ? 'var(--green)' : 'var(--red)'
}

export default function IMAPHeatmap() {
  const { data, loading } = useInternational()
  const indices = data?.indices?.indices || []

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Global Equity Performance</span>
        <span className="dim" style={{ fontSize: 9 }}>world indices</span>
      </div>
      <div className="panel-body" style={{ padding: 8 }}>
        {loading ? (
          <div style={{ color: 'var(--text-dim)', padding: 8 }}>Loading…</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 4 }}>
            {indices.map(ix => (
              <div key={ix.symbol} style={{
                background: heatColor(ix.change_pct), border: '1px solid var(--border)',
                borderRadius: 4, padding: '10px 8px', textAlign: 'center',
              }}>
                <div style={{ color: 'var(--yellow)', fontSize: 11, fontWeight: 'bold' }}>{ix.name}</div>
                <div style={{ fontSize: 9, color: 'var(--text-secondary)', marginBottom: 2 }}>{ix.country}</div>
                <div style={{ fontSize: 13, fontWeight: 'bold', color: textColor(ix.change_pct) }}>
                  {ix.change_pct != null ? `${ix.change_pct >= 0 ? '+' : ''}${ix.change_pct.toFixed(2)}%` : '—'}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-dim)' }}>
                  {ix.level?.toLocaleString() || '—'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
