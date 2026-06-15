import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { useCreditDashboard } from '../../hooks/useMarketData'

const signalColor = (s) => ({
  stress:   'var(--red)',
  elevated: 'var(--gold)',
  watch:    'var(--gold-bright)',
  calm:     'var(--green)',
}[s] || 'var(--text-secondary)')

function Stat({ label, value, change, suffix = '%' }) {
  return (
    <div style={{ flex: 1, padding: 12, background: 'var(--bg-base)', borderRadius: 6 }}>
      <div className="label" style={{ marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
        {value != null ? value.toFixed(2) + suffix : '—'}
      </div>
      {change != null && (
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)',
                      color: change > 0 ? 'var(--red)' : 'var(--green)' }}>
          {change > 0 ? '+' : ''}{change.toFixed(2)} (1mo)
        </div>
      )}
    </div>
  )
}

export default function Credit() {
  const { data, loading } = useCreditDashboard()

  const chartData = data?.hy_history?.map((h, i) => ({
    date: h.date,
    HY: h.value,
    IG: data.ig_history?.[i]?.value,
  })) || []

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Credit Markets</span>
        {data?.signal && (
          <span style={{ color: signalColor(data.signal), fontWeight: 700, fontSize: 12,
                         textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {data.signal}
          </span>
        )}
      </div>
      <div className="panel-body" style={{ padding: 12 }}>
        {loading ? <div style={{ color: 'var(--text-dim)' }}>Loading credit data…</div> : (
          <>
            <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
              <Stat label="HY OAS" value={data?.hy_oas} change={data?.hy_change} />
              <Stat label="IG OAS" value={data?.ig_oas} change={data?.ig_change} />
              <Stat label="HY / IG Ratio" value={data?.hy_ig_ratio} suffix="x" />
            </div>

            <div style={{ height: 220, marginBottom: 14 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--text-dim)', fontSize: 9 }}
                         interval={Math.floor(chartData.length / 6)} />
                  <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 10 }} width={40}
                         tickFormatter={v => v.toFixed(1)} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                           borderRadius: 6, fontSize: 11 }} />
                  <Line type="monotone" dataKey="HY" stroke="var(--red)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="IG" stroke="var(--steel-bright)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div style={{ padding: 12, background: 'var(--bg-base)', borderRadius: 6,
                          borderLeft: `3px solid ${signalColor(data?.signal)}` }}>
              <div className="label" style={{ marginBottom: 6 }}>Read</div>
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
