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
        <span className="title">📉 Yield Curve</span>
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
              <CartesianGrid strokeDasharray="3 3" stroke="#131820" />
              <XAxis
                dataKey="maturity"
                tick={{ fill: '#546e7a', fontSize: 9 }}
                axisLine={{ stroke: '#1c2333' }}
              />
              <YAxis
                domain={['auto', 'auto']}
                tick={{ fill: '#546e7a', fontSize: 9 }}
                axisLine={{ stroke: '#1c2333' }}
                tickFormatter={v => `${v.toFixed(2)}%`}
                width={45}
              />
              <Tooltip
                contentStyle={{
                  background: '#0e1118', border: '1px solid #1c2333',
                  borderRadius: 4, fontSize: 11, fontFamily: 'Courier New',
                }}
                labelStyle={{ color: '#f0a500' }}
                formatter={(v) => [`${v.toFixed(3)}%`, 'Yield']}
              />
              <ReferenceLine y={0} stroke="#ff3d5760" strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="yield"
                stroke="#1e88e5"
                strokeWidth={2}
                dot={{ fill: '#1e88e5', r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
