import React, { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { useGraphFunctions, runGraphEval } from '../../hooks/useMarketData'
import Explain from '../common/Explain'

const DAY_OPTIONS = [
  { label: '3M', days: 90 }, { label: '6M', days: 180 },
  { label: '1Y', days: 365 }, { label: '2Y', days: 730 }, { label: '5Y', days: 1825 },
]

function fmtDate(ts) {
  if (ts == null) return ''
  const d = new Date(typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts)
  return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}

export default function GraphBuilder() {
  const { data: meta } = useGraphFunctions()
  const [expr, setExpr] = useState('SMA(AAPL,20) - SMA(AAPL,50)')
  const [days, setDays] = useState(365)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    if (!expr.trim()) return
    setLoading(true)
    try { setResult(await runGraphEval(expr.trim(), days)) }
    finally { setLoading(false) }
  }

  const chartData = result?.points?.map(p => ({ t: p.t, v: p.v })) || []
  const last = chartData.length ? chartData[chartData.length - 1].v : null

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: 6 }}>
        <span className="title">Graph Builder</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Explain title="How the Graph Builder works">
            Type a formula referencing tickers as bare names (AAPL, MSFT, ...),
            combined with + - * / and parentheses, and optionally wrapped in
            an indicator function: SMA, EMA, RSI, ROC, ZSCORE, STD, CORR.
            <br/><br/>
            Examples: <code>AAPL / MSFT</code> (a price ratio), <code>SMA(AAPL,20)
            - SMA(AAPL,50)</code> (a moving-average spread), <code>CORR(SPY,QQQ,30)</code>
            (rolling correlation). Up to 6 distinct tickers per formula.
            <br/><br/>
            This is evaluated by a restricted parser, not a live code
            interpreter — only arithmetic and the functions listed above are
            ever allowed to run.
          </Explain>
          {DAY_OPTIONS.map(o => (
            <button key={o.label} className={`btn ${days === o.days ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px' }}
              onClick={() => setDays(o.days)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>
      <div className="panel-body" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Formula bar */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span className="dim" style={{ fontSize: 11, fontFamily: 'var(--font-mono)', flexShrink: 0 }}>fx</span>
          <input className="input" style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 13 }}
            value={expr}
            onChange={e => setExpr(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
            placeholder="e.g. SMA(AAPL,20) - SMA(AAPL,50)" />
          <button className="btn active" onClick={run} disabled={loading || !expr.trim()}>
            {loading ? 'Plotting…' : 'Plot'}
          </button>
        </div>

        {/* Example chips */}
        {meta?.examples && (
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {meta.examples.map(ex => (
              <button key={ex} className="btn" style={{ fontSize: 9.5, fontFamily: 'var(--font-mono)' }}
                onClick={() => setExpr(ex)}>
                {ex}
              </button>
            ))}
          </div>
        )}

        {result?.error && (
          <div style={{ color: 'var(--red)', fontSize: 11, padding: '8px 10px',
                        background: 'var(--red-dim)', borderRadius: 'var(--radius-sm)' }}>
            {result.error}
          </div>
        )}

        {!result && !loading && (
          <div className="dim" style={{ fontSize: 11, padding: '24px 0', textAlign: 'center' }}>
            Type a formula and hit Plot — or click an example above.
          </div>
        )}

        {chartData.length > 1 && (
          <>
            <div style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
              <span className="dim" style={{ fontSize: 10 }}>{result.symbols?.join(' · ')}</span>
              {last != null && (
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--gold-bright)' }}>
                  {last.toFixed(4)}
                </span>
              )}
            </div>
            <div style={{ flex: 1, minHeight: 260 }}>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
                  <XAxis dataKey="t" tickFormatter={fmtDate} stroke="var(--text-dim)" fontSize={10}
                    minTickGap={40} />
                  <YAxis stroke="var(--text-dim)" fontSize={10} domain={['auto', 'auto']} width={64} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 11 }}
                    labelFormatter={fmtDate}
                    formatter={(v) => [v?.toFixed(4), result.expr]} />
                  <Line type="monotone" dataKey="v" stroke="var(--gold)" dot={false} strokeWidth={1.5} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
