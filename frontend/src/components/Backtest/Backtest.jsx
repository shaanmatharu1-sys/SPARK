import React, { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts'
import { useBacktestCompare } from '../../hooks/useMarketData'

const STRAT_COLORS = {
  zscore_reversion:    '#42a5f5',
  momentum:            '#00c853',
  ma_crossover:        '#f0a500',
  bollinger_reversion: '#7c4dff',
  buy_hold:            '#7a92ab',
}

function fmtPct(x)  { return x != null ? `${(x * 100).toFixed(1)}%` : '—' }
function fmtNum(x)  { return x != null ? x.toFixed(2) : '—' }

function StatCell({ value, type }) {
  let color = 'var(--text-primary)'
  if (type === 'signed') color = value >= 0 ? 'var(--green)' : 'var(--red)'
  if (type === 'sharpe') color = value >= 1 ? 'var(--green)' : value >= 0 ? 'var(--yellow)' : 'var(--red)'
  if (type === 'dd')     color = 'var(--red)'
  return <td style={{ color }}>{
    type === 'pct' || type === 'signed' ? fmtPct(value) : fmtNum(value)
  }</td>
}

export default function Backtest() {
  const [symbol, setSymbol] = useState('SPY')
  const [input, setInput]   = useState('SPY')
  const [days, setDays]     = useState(365)
  const [costBps, setCostBps] = useState(1.0)

  const { data, loading, error } = useBacktestCompare(symbol, days, costBps)

  // Build merged equity curve data for charting
  const chartData = React.useMemo(() => {
    if (!data?.results) return []
    const strategies = Object.keys(data.results)
    const maxLen = Math.max(...strategies.map(s => data.results[s].equity_curve.length))
    const merged = []
    for (let i = 0; i < maxLen; i++) {
      const row = { idx: i }
      for (const s of strategies) {
        const curve = data.results[s].equity_curve
        if (i < curve.length) row[s] = curve[i]
      }
      merged.push(row)
    }
    return merged
  }, [data])

  const strategies = data?.results ? Object.keys(data.results) : []

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Backtest Lab</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span className="dim" style={{ fontSize: 9 }}>DAYS:</span>
          {[365, 730, 1095].map(d => (
            <button key={d} onClick={() => setDays(d)} style={{
              background: days === d ? 'var(--blue)' : 'transparent',
              color: days === d ? '#fff' : 'var(--text-secondary)',
              border: '1px solid var(--border-accent)', borderRadius: 3,
              padding: '2px 6px', fontSize: 9, cursor: 'pointer', fontFamily: 'Courier New',
            }}>{d === 365 ? '1Y' : d === 730 ? '2Y' : '3Y'}</button>
          ))}
          <span className="dim" style={{ fontSize: 9, marginLeft: 4 }}>COST:</span>
          <input value={costBps} onChange={e => setCostBps(parseFloat(e.target.value) || 0)}
            style={{ background: '#0a0c10', border: '1px solid var(--border-accent)',
                     color: 'var(--text-primary)', padding: '2px 4px', fontSize: 9,
                     borderRadius: 3, width: 32, fontFamily: 'Courier New' }} />
          <span className="dim" style={{ fontSize: 9 }}>bps</span>
          <input value={input} onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && setSymbol(input)}
            style={{ background: '#0a0c10', border: '1px solid var(--border-accent)',
                     color: 'var(--yellow)', padding: '2px 6px', fontSize: 10,
                     borderRadius: 3, width: 64, fontFamily: 'Courier New', fontWeight: 'bold' }} />
        </div>
      </div>

      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column' }}>
        {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Running backtests on {symbol}...</div>}
        {error && <div style={{ padding: 16, color: 'var(--red)' }}>Error: {error}</div>}
        {data?.error && <div style={{ padding: 16, color: 'var(--red)' }}>{data.error}</div>}

        {data?.results && (
          <>
            {/* Equity curves */}
            <div style={{ height: 260, padding: '8px 8px 0 0' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#131820" />
                  <XAxis dataKey="idx" tick={{ fill: '#546e7a', fontSize: 9 }}
                         axisLine={{ stroke: '#1c2333' }} />
                  <YAxis tick={{ fill: '#546e7a', fontSize: 9 }} axisLine={{ stroke: '#1c2333' }}
                         tickFormatter={v => `${v.toFixed(2)}x`} width={42}
                         domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: '#0e1118', border: '1px solid #1c2333',
                           borderRadius: 4, fontSize: 10, fontFamily: 'Courier New' }}
                           formatter={(v) => `${v.toFixed(3)}x`} />
                  <Legend wrapperStyle={{ fontSize: 9 }} />
                  {strategies.map(s => (
                    <Line key={s} type="monotone" dataKey={s}
                          name={data.results[s].name}
                          stroke={STRAT_COLORS[s] || '#888'}
                          strokeWidth={s === 'buy_hold' ? 1.5 : 1.5}
                          strokeDasharray={s === 'buy_hold' ? '4 4' : '0'}
                          dot={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Stats table */}
            <table className="bbg-table" style={{ marginTop: 8 }}>
              <thead>
                <tr>
                  <th>STRATEGY</th>
                  <th>TOT RET</th>
                  <th>ANN RET</th>
                  <th>SHARPE</th>
                  <th>SORTINO</th>
                  <th>MAX DD</th>
                  <th>CALMAR</th>
                  <th>HIT%</th>
                  <th>PF</th>
                </tr>
              </thead>
              <tbody>
                {strategies.map(s => {
                  const st = data.results[s].stats
                  return (
                    <tr key={s}>
                      <td style={{ color: STRAT_COLORS[s] || 'var(--text-primary)', fontWeight: 'bold' }}>
                        {data.results[s].name}
                      </td>
                      <StatCell value={st.total_return} type="signed" />
                      <StatCell value={st.ann_return} type="signed" />
                      <StatCell value={st.sharpe} type="sharpe" />
                      <StatCell value={st.sortino} type="sharpe" />
                      <StatCell value={st.max_drawdown} type="dd" />
                      <StatCell value={st.calmar} type="num" />
                      <StatCell value={st.hit_rate} type="pct" />
                      <StatCell value={st.profit_factor} type="num" />
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}
