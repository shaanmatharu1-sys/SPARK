import React, { useState, useMemo } from 'react'
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { useMarketRegime, useMarketRegimeHistory } from '../../hooks/useMarketData'

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

function fmtTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function RegimeHistoryCharts({ history }) {
  const data = useMemo(() => (history || []).map(h => ({
    t: h.computed_at,
    trending: h.regime_breadth_pct?.trending ?? 0,
    reverting: h.regime_breadth_pct?.['mean-reverting'] ?? 0,
    random: h.regime_breadth_pct?.['random-walk'] ?? 0,
    ad: h.advance_decline_ratio,
    vix: h.vix,
  })), [history])

  if (data.length < 2) {
    return (
      <div className="dim" style={{ fontSize: 10, padding: '16px 4px', lineHeight: 1.6 }}>
        History accumulates one point per hourly regime recompute — check back after a few
        cycles to see regime breadth, the A/D ratio, and VIX evolve over time instead of only
        the latest snapshot.
      </div>
    )
  }

  return (
    <>
      <div className="dim" style={{ fontSize: 9, margin: '2px 0 4px' }}>REGIME BREADTH OVER TIME (% stacked)</div>
      <div style={{ height: 110 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 2, right: 4, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
            <XAxis dataKey="t" tickFormatter={fmtTime} stroke="var(--text-dim)" fontSize={8} minTickGap={60} />
            <YAxis stroke="var(--text-dim)" fontSize={8} domain={[0, 100]} />
            <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 10 }}
                     labelFormatter={fmtTime} />
            <Area type="monotone" dataKey="trending" stackId="1" stroke={REGIME_COLOR.trending} fill={REGIME_COLOR.trending} fillOpacity={0.5} isAnimationActive={false} />
            <Area type="monotone" dataKey="reverting" stackId="1" stroke={REGIME_COLOR['mean-reverting']} fill={REGIME_COLOR['mean-reverting']} fillOpacity={0.5} isAnimationActive={false} />
            <Area type="monotone" dataKey="random" stackId="1" stroke={REGIME_COLOR['random-walk']} fill={REGIME_COLOR['random-walk']} fillOpacity={0.4} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="dim" style={{ fontSize: 9, margin: '8px 0 4px' }}>ADVANCE/DECLINE RATIO</div>
      <div style={{ height: 70 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 2, right: 4, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
            <XAxis dataKey="t" tickFormatter={fmtTime} stroke="var(--text-dim)" fontSize={8} minTickGap={60} />
            <YAxis stroke="var(--text-dim)" fontSize={8} domain={['auto', 'auto']} />
            <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 10 }}
                     labelFormatter={fmtTime} />
            <Line type="monotone" dataKey="ad" stroke="var(--green)" dot={false} strokeWidth={1.3} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="dim" style={{ fontSize: 9, margin: '8px 0 4px' }}>VIX</div>
      <div style={{ height: 70 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 2, right: 4, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
            <XAxis dataKey="t" tickFormatter={fmtTime} stroke="var(--text-dim)" fontSize={8} minTickGap={60} />
            <YAxis stroke="var(--text-dim)" fontSize={8} domain={['auto', 'auto']} />
            <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 10 }}
                     labelFormatter={fmtTime} />
            <Line type="monotone" dataKey="vix" stroke="var(--red)" dot={false} strokeWidth={1.3} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  )
}

export default function Regime() {
  const { data, loading } = useMarketRegime()
  const { data: histData } = useMarketRegimeHistory()
  const breadth = data?.market_breadth
  const regimePct = data?.regime_breadth_pct || {}
  const macro = data?.macro || {}
  const perSymbol = data?.per_symbol || []

  const [regimeFilter, setRegimeFilter] = useState('all')
  const [sortKey, setSortKey] = useState('symbol')
  const [sortDir, setSortDir] = useState(1)

  const sortedSymbols = useMemo(() => {
    let rows = perSymbol
    if (regimeFilter !== 'all') rows = rows.filter(r => r.regime === regimeFilter)
    return [...rows].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      if (av == null) return 1
      if (bv == null) return -1
      if (typeof av === 'string') return sortDir * av.localeCompare(bv)
      return sortDir * (av - bv)
    })
  }, [perSymbol, regimeFilter, sortKey, sortDir])

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => -d)
    else { setSortKey(key); setSortDir(1) }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gridTemplateRows: '1fr 1fr', gap: 6, height: '100%', minHeight: 0 }}>
      {/* Regime breadth + macro context */}
      <div className="panel" style={{ minHeight: 0 }}>
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

      {/* Regime/breadth/VIX history */}
      <div className="panel" style={{ minHeight: 0, gridRow: '1 / 3' }}>
        <div className="panel-header"><span className="title">History</span></div>
        <div className="panel-body" style={{ padding: 10, overflowY: 'auto' }}>
          <RegimeHistoryCharts history={histData?.history} />
        </div>
      </div>

      {/* Per-symbol regime table */}
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header">
          <span className="title">SPY / QQQ / IWM / Sector ETF Regimes</span>
          <select className="input" style={{ fontSize: 9 }} value={regimeFilter} onChange={e => setRegimeFilter(e.target.value)}>
            <option value="all">All regimes</option>
            <option value="trending">Trending</option>
            <option value="mean-reverting">Mean-reverting</option>
            <option value="random-walk">Random-walk</option>
          </select>
        </div>
        <div className="panel-body" style={{ padding: '4px 12px', overflowY: 'auto' }}>
          {sortedSymbols.length === 0 && !loading && <div className="dim" style={{ fontSize: 11, padding: 12 }}>No data yet.</div>}
          {sortedSymbols.length > 0 && (
            <table className="bbg-table">
              <thead>
                <tr>
                  {[
                    ['symbol', 'SYMBOL'], ['regime', 'REGIME'], ['vol_regime', 'VOL REGIME'],
                    ['composite_score', 'COMPOSITE'], ['hurst', 'HURST'],
                  ].map(([key, label]) => (
                    <th key={key} onClick={() => toggleSort(key)} style={{ cursor: 'pointer', userSelect: 'none' }}>
                      {label}{sortKey === key ? (sortDir === 1 ? ' ▲' : ' ▼') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedSymbols.map(s => (
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
