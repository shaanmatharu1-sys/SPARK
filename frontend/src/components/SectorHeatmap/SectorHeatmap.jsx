import React from 'react'
import { useSectors } from '../../hooks/useMarketData'

// Heat-cell background is a green/red intensity scale derived from the theme's
// --green (#3FB68B -> 63,182,139) and --red (#E0556B -> 224,85,107) at varying
// alpha — kept separate from the plain --green/--red used for the text above.
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

export default function SectorHeatmap() {
  const { data: sectors, loading } = useSectors()

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Sector Heatmap</span>
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
                border:        '1px solid var(--border)',
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
