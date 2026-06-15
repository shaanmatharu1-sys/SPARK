import React, { useState } from 'react'
import { useCorrelation, useMacroMatrix } from '../../hooks/useMarketData'

// Correlation -> color: +1 green, 0 dark, -1 red
function corrColor(c) {
  if (c == null) return 'var(--bg-panel)'
  if (c >= 0) return `rgba(63,182,139,${0.15 + c * 0.55})`
  return `rgba(224,85,107,${0.15 + (-c) * 0.55})`
}

function Matrix({ labels, rowLabels, matrix }) {
  const rl = rowLabels || labels
  return (
    <div style={{ overflow: 'auto', padding: 8 }}>
      <table style={{ borderCollapse: 'collapse', fontSize: 10 }}>
        <thead>
          <tr>
            <th style={{ padding: 4 }}></th>
            {labels.map(l => (
              <th key={l} style={{ padding: '4px 3px', color: 'var(--text-dim)',
                   fontSize: 9, writingMode: labels.length > 8 ? 'vertical-rl' : 'horizontal-tb',
                   fontFamily: 'var(--font-mono)' }}>{l}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td style={{ padding: '3px 6px', color: 'var(--gold)', fontWeight: 600,
                   fontFamily: 'var(--font-mono)', fontSize: 10 }}>{rl[i]}</td>
              {row.map((c, j) => (
                <td key={j} style={{
                  background: corrColor(c), textAlign: 'center', padding: '4px 5px',
                  fontFamily: 'var(--font-mono)', fontSize: 9,
                  color: c != null && Math.abs(c) > 0.5 ? '#fff' : 'var(--text-secondary)',
                  minWidth: 32,
                }}>
                  {c != null ? c.toFixed(2) : '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Correlation() {
  const [mode, setMode] = useState('assets')
  const { data: corr, loading: cl } = useCorrelation('watchlist')
  const { data: macro, loading: ml } = useMacroMatrix()

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Correlation Matrix</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button className={`btn ${mode === 'assets' ? 'active' : ''}`}
            onClick={() => setMode('assets')}>ASSETS</button>
          <button className={`btn ${mode === 'macro' ? 'active' : ''}`}
            onClick={() => setMode('macro')}>MACRO</button>
        </div>
      </div>
      <div className="panel-body">
        {mode === 'assets' && (
          cl ? <div style={{ padding: 16, color: 'var(--text-dim)' }}>Computing correlations…</div>
          : corr?.matrix ? <Matrix labels={corr.symbols} matrix={corr.matrix} />
          : <div style={{ padding: 16, color: 'var(--red)' }}>{corr?.error || 'No data'}</div>
        )}
        {mode === 'macro' && (
          ml ? <div style={{ padding: 16, color: 'var(--text-dim)' }}>Computing macro correlations…</div>
          : macro?.matrix ? <Matrix labels={macro.factors} rowLabels={macro.assets} matrix={macro.matrix} />
          : <div style={{ padding: 16, color: 'var(--red)' }}>{macro?.error || 'No data'}</div>
        )}
        {mode === 'assets' && corr?.most_correlated && (
          <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', fontSize: 10 }}>
            <span className="dim">Most correlated: </span>
            <span className="gold">{corr.most_correlated[0]?.pair} ({corr.most_correlated[0]?.corr})</span>
          </div>
        )}
      </div>
    </div>
  )
}
