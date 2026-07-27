import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell,
} from 'recharts'
import { useYieldCurveExtended, useGlobalYields, useRealYields } from '../../hooks/useMarketData'

const MATS = ['1M','3M','6M','1Y','2Y','3Y','5Y','7Y','10Y','20Y','30Y']

function RealYieldCard({ r }) {
  if (!r) return null
  const up = (r.change ?? 0) >= 0
  return (
    <div style={{ flex: 1, minWidth: 110, padding: 9, background: 'var(--bg-base)', borderRadius: 6 }}>
      <div className="dim" style={{ fontSize: 8.5 }}>{r.label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
        {r.value != null ? `${r.value.toFixed(2)}%` : '—'}
      </div>
      <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: up ? 'var(--green)' : 'var(--red)' }}>
        {r.change != null ? `${r.change >= 0 ? '+' : ''}${r.change.toFixed(2)}` : '—'}
      </div>
    </div>
  )
}

// Global sovereign 10Y yields — ranked bar, US highlighted for reference.
function GlobalYieldsPanel() {
  const { data, loading } = useGlobalYields()
  const rows = data?.yields || []
  return (
    <div className="panel" style={{ minHeight: 0 }}>
      <div className="panel-header">
        <span className="title">Global Sovereign 10Y Yields</span>
        <span className="dim" style={{ fontSize: 9 }}>FRED/OECD long-term rates · monthly (US: daily)</span>
      </div>
      <div className="panel-body" style={{ padding: '6px 12px', overflowY: 'auto' }}>
        {loading && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}
        {!loading && (
          <div style={{ height: Math.max(200, rows.length * 22) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} layout="vertical" margin={{ top: 2, right: 30, left: 0, bottom: 2 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fill: 'var(--text-dim)', fontSize: 8 }}
                       axisLine={{ stroke: 'var(--border-bright)' }} tickFormatter={v => `${v}%`} />
                <YAxis type="category" dataKey="country" width={30}
                       tick={{ fill: 'var(--text-dim)', fontSize: 9 }} axisLine={{ stroke: 'var(--border-bright)' }} />
                <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                         borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}
                         formatter={(v) => `${v.toFixed(2)}%`}
                         labelFormatter={(_, p) => p?.[0]?.payload?.name} />
                <Bar dataKey="yield_10y" cursor="default">
                  {rows.map(r => (
                    <Cell key={r.country} fill={r.country === 'US' ? 'var(--gold-bright)' : 'var(--steel-bright)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}

function SpreadCard({ label, value, desc }) {
  const inv = value != null && value < 0
  return (
    <div style={{ flex: 1, padding: 10, background: 'var(--bg-base)', borderRadius: 6,
                  border: `1px solid ${inv ? 'var(--red)' : 'var(--border)'}` }}>
      <div className="dim" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: inv ? 'var(--red)' : 'var(--green)' }}>
        {value != null ? `${value >= 0 ? '+' : ''}${value.toFixed(2)}%` : '—'}
      </div>
      <div className="dim" style={{ fontSize: 8 }}>{inv ? 'INVERTED' : desc}</div>
    </div>
  )
}

export default function YieldCurvePanel() {
  const { data, loading } = useYieldCurveExtended()
  const { data: realYields } = useRealYields()

  const chartData = data?.curve
    ? MATS.filter(m => data.curve[m] != null).map(m => ({ maturity: m, yield: data.curve[m] }))
    : []

  const shapeColor = data?.shape === 'inverted' ? 'var(--red)'
                   : data?.shape === 'flat' ? 'var(--gold)' : 'var(--green)'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.3fr) minmax(0, 1fr)', gap: 6, height: '100%', minHeight: 0 }}>
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header">
          <span className="title">Treasury Yield Curve</span>
          {data?.shape && (
            <span style={{ color: shapeColor, fontWeight: 700, fontSize: 12,
                           textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {data.shape}
            </span>
          )}
        </div>
        <div className="panel-body" style={{ padding: 12, overflowY: 'auto' }}>
          {loading ? <div style={{ color: 'var(--text-dim)' }}>Loading curve…</div> : (
            <>
              {/* Spread cards */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
                <SpreadCard label="2s10s (10Y − 2Y)" value={data?.spreads?.['2s10s']} desc="NORMAL" />
                <SpreadCard label="3m10y (10Y − 3M)" value={data?.spreads?.['3m10y']} desc="NORMAL" />
                <SpreadCard label="5s30s (30Y − 5Y)" value={data?.spreads?.['5s30s']} desc="NORMAL" />
              </div>

              {/* The curve — large */}
              <div style={{ height: 260, marginBottom: 14 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="maturity" tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
                           axisLine={{ stroke: 'var(--border)' }} />
                    <YAxis domain={['auto', 'auto']} tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
                           axisLine={{ stroke: 'var(--border)' }}
                           tickFormatter={v => `${v.toFixed(1)}%`} width={48} />
                    <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                             borderRadius: 6, fontSize: 12, fontFamily: 'var(--font-mono)' }}
                             formatter={v => [`${v.toFixed(3)}%`, 'Yield']} />
                    <Line type="monotone" dataKey="yield" stroke="var(--gold)" strokeWidth={2.5}
                          dot={{ fill: 'var(--gold)', r: 4 }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Interpretation */}
              <div style={{ padding: 12, background: 'var(--bg-base)', borderRadius: 6,
                            borderLeft: `3px solid ${shapeColor}`, marginBottom: 14 }}>
                <div className="label" style={{ marginBottom: 6 }}>What this means</div>
                <div style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                  {data?.interpretation}
                </div>
              </div>

              {/* Real yields / breakeven inflation — TIPS market depth */}
              <div className="label" style={{ marginBottom: 6 }}>Real Yields &amp; Breakeven Inflation (TIPS market)</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {['real_5y', 'real_10y', 'real_30y', 'breakeven_5y', 'breakeven_10y', 'forward_5y5y']
                  .map(k => <RealYieldCard key={k} r={realYields?.[k]} />)}
              </div>
            </>
          )}
        </div>
      </div>

      <GlobalYieldsPanel />
    </div>
  )
}
