import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'
import { useYieldCurve } from '../../hooks/useMarketData'

const MATURITIES = ['1M','3M','6M','1Y','2Y','3Y','5Y','7Y','10Y','20Y','30Y']

export default function YieldCurve() {
  const { data: curve, loading } = useYieldCurve()

  const chartData = MATURITIES
    .filter(m => curve?.[m] != null)
    .map(m => ({ maturity: m, yield: curve[m] }))

  const spread = curve?.['2s10s']
  const spreadColor = spread == null ? 'var(--text-dim)'
                    : spread >= 0 ? 'var(--green)' : 'var(--red)'

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Yield Curve</span>
        {spread != null && (
          <span style={{ fontSize: 10, color: spreadColor }}>
            2s10s: {spread >= 0 ? '+' : ''}{spread.toFixed(3)}%
          </span>
        )}
      </div>
      <div className="panel-body" style={{ padding: '8px 4px 4px 0' }}>
        {loading ? (
          <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading...</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 12, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="maturity"
                tick={{ fill: 'var(--text-dim)', fontSize: 9 }}
                axisLine={{ stroke: 'var(--border-bright)' }}
              />
              <YAxis
                domain={['auto', 'auto']}
                tick={{ fill: 'var(--text-dim)', fontSize: 9 }}
                axisLine={{ stroke: 'var(--border-bright)' }}
                tickFormatter={v => `${v.toFixed(2)}%`}
                width={45}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                  borderRadius: 4, fontSize: 11, fontFamily: 'var(--font-mono)',
                }}
                labelStyle={{ color: 'var(--gold)' }}
                formatter={(v) => [`${v.toFixed(3)}%`, 'Yield']}
              />
              <ReferenceLine y={0} stroke="rgba(224,85,107,0.4)" strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="yield"
                stroke="var(--steel-bright)"
                strokeWidth={2}
                dot={{ fill: 'var(--steel-bright)', r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
