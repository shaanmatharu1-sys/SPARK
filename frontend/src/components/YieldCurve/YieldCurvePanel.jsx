import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import { useYieldCurveExtended } from '../../hooks/useMarketData'

const MATS = ['1M','3M','6M','1Y','2Y','3Y','5Y','7Y','10Y','20Y','30Y']

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

  const chartData = data?.curve
    ? MATS.filter(m => data.curve[m] != null).map(m => ({ maturity: m, yield: data.curve[m] }))
    : []

  const shapeColor = data?.shape === 'inverted' ? 'var(--red)'
                   : data?.shape === 'flat' ? 'var(--gold)' : 'var(--green)'

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Treasury Yield Curve</span>
        {data?.shape && (
          <span style={{ color: shapeColor, fontWeight: 700, fontSize: 12,
                         textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {data.shape}
          </span>
        )}
      </div>
      <div className="panel-body" style={{ padding: 12 }}>
        {loading ? <div style={{ color: 'var(--text-dim)' }}>Loading curve…</div> : (
          <>
            {/* Spread cards */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
              <SpreadCard label="2s10s (10Y − 2Y)" value={data?.spreads?.['2s10s']} desc="NORMAL" />
              <SpreadCard label="3m10y (10Y − 3M)" value={data?.spreads?.['3m10y']} desc="NORMAL" />
              <SpreadCard label="5s30s (30Y − 5Y)" value={data?.spreads?.['5s30s']} desc="NORMAL" />
            </div>

            {/* The curve — large */}
            <div style={{ height: 280, marginBottom: 14 }}>
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
                          borderLeft: `3px solid ${shapeColor}` }}>
              <div className="label" style={{ marginBottom: 6 }}>What this means</div>
              <div style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                {data?.interpretation}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
