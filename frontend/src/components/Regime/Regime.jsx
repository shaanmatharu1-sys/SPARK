import React from 'react'
import { useMarketRegime } from '../../hooks/useMarketData'

// Mirrors SectorHeatmap.jsx's heat-color-scale technique (theme --green/--red
// at varying alpha) so composite-score coloring looks consistent app-wide.
function scoreColor(score) {
  if (score == null) return 'var(--bg-raised)'
  if (score >  0.5)  return 'rgba(63,182,139,0.55)'
  if (score >  0.2)  return 'rgba(63,182,139,0.30)'
  if (score >  0)    return 'rgba(63,182,139,0.15)'
  if (score > -0.2)  return 'rgba(224,85,107,0.15)'
  if (score > -0.5)  return 'rgba(224,85,107,0.30)'
  return 'rgba(224,85,107,0.55)'
}

const REGIME_COLOR = {
  trending: 'var(--green)', 'mean-reverting': 'var(--gold)',
  'random-walk': 'var(--steel-bright)', unknown: 'var(--text-dim)',
}

function Metric({ label, value, color, sub }) {
  return (
    <div style={{ flex: 1, textAlign: 'center', padding: '10px 6px',
                  background: 'var(--bg-base)', borderRadius: 4 }}>
      <div className="dim" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 'bold', color: color || 'var(--text-primary)' }}>{value}</div>
      {sub && <div className="dim" style={{ fontSize: 9 }}>{sub}</div>}
    </div>
  )
}

export default function Regime() {
  const { data, loading } = useMarketRegime()
  const breadth = data?.market_breadth
  const regimePct = data?.regime_breadth_pct || {}
  const macro = data?.macro || {}
  const perSymbol = data?.per_symbol || []

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gridTemplateRows: '1fr 1fr', gap: 6, height: '100%', minHeight: 0 }}>
      {/* Regime breadth + macro context */}
      <div className="panel" style={{ minHeight: 0, gridRow: '1 / 3' }}>
        <div className="panel-header">
          <span className="title">Market Regime — SPY/QQQ/IWM + Sectors</span>
          <span className="dim" style={{ fontSize: 9 }}>hourly refresh</span>
        </div>
        <div className="panel-body" style={{ padding: 10, overflowY: 'auto' }}>
          {loading && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}

          <div className="dim" style={{ fontSize: 9, marginBottom: 6 }}>REGIME BREAKDOWN (% OF UNIVERSE)</div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
            <Metric label="TRENDING" value={`${regimePct.trending ?? 0}%`} color={REGIME_COLOR.trending} />
            <Metric label="MEAN-REVERTING" value={`${regimePct['mean-reverting'] ?? 0}%`} color={REGIME_COLOR['mean-reverting']} />
            <Metric label="RANDOM-WALK" value={`${regimePct['random-walk'] ?? 0}%`} color={REGIME_COLOR['random-walk']} />
          </div>

          <div className="dim" style={{ fontSize: 9, marginBottom: 6 }}>BREADTH (~{breadth?.universe_size || 0}-NAME UNIVERSE)</div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
            <Metric label="ADVANCERS" value={breadth?.advancers ?? '—'} color="var(--green)" />
            <Metric label="DECLINERS" value={breadth?.decliners ?? '—'} color="var(--red)" />
            <Metric label="A/D RATIO" value={breadth?.advance_decline_ratio ?? '—'} />
            <Metric label="% UP (20D)" value={breadth?.pct_positive_20d_return != null ? `${breadth.pct_positive_20d_return}%` : '—'} />
          </div>

          <div className="dim" style={{ fontSize: 9, marginBottom: 6 }}>MACRO CONTEXT</div>
          <div style={{ display: 'flex', gap: 6 }}>
            <Metric label="VIX" value={macro.vix != null ? macro.vix.toFixed(1) : '—'}
              color={macro.vix_regime === 'elevated' ? 'var(--red)' : macro.vix_regime === 'low' ? 'var(--green)' : 'var(--text)'}
              sub={macro.vix_regime} />
            <Metric label="2s10s SPREAD" value={macro.yield_curve_2s10s != null ? `${macro.yield_curve_2s10s > 0 ? '+' : ''}${macro.yield_curve_2s10s}%` : '—'}
              color={macro.yield_curve_shape === 'inverted' ? 'var(--red)' : 'var(--green)'}
              sub={macro.yield_curve_shape} />
          </div>

          {data?.computed_at && (
            <div className="dim" style={{ fontSize: 9, marginTop: 14 }}>
              Computed {new Date(data.computed_at + 'Z').toLocaleString()}. Regime = Hurst-exponent
              classification (analytics/signals/engine.py); breadth = advance/decline + 20-day
              cumulative-return sign across the curated universe.
            </div>
          )}
        </div>
      </div>

      {/* Per-symbol regime table */}
      <div className="panel" style={{ minHeight: 0, gridRow: '1 / 3' }}>
        <div className="panel-header"><span className="title">SPY / QQQ / IWM / Sector ETF Regimes</span></div>
        <div className="panel-body" style={{ padding: '4px 12px', overflowY: 'auto' }}>
          {perSymbol.length === 0 && !loading && <div className="dim" style={{ fontSize: 11, padding: 12 }}>No data yet.</div>}
          {perSymbol.length > 0 && (
            <table className="bbg-table">
              <thead>
                <tr><th>SYMBOL</th><th>REGIME</th><th>VOL REGIME</th><th>COMPOSITE</th><th>HURST</th></tr>
              </thead>
              <tbody>
                {perSymbol.map(s => (
                  <tr key={s.symbol}>
                    <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{s.symbol}</td>
                    <td style={{ color: REGIME_COLOR[s.regime] || 'var(--text)' }}>{s.regime}</td>
                    <td className="dim">{s.vol_regime}</td>
                    <td style={{ background: scoreColor(s.composite_score), textAlign: 'center' }}>
                      {s.composite_score != null ? (s.composite_score >= 0 ? '+' : '') + s.composite_score.toFixed(2) : '—'}
                    </td>
                    <td className="dim">{s.hurst != null ? s.hurst.toFixed(2) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
