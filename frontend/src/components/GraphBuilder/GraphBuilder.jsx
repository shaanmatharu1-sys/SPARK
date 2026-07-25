import React, { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useGraphFunctions, runGraphEval } from '../../hooks/useMarketData'
import Explain from '../common/Explain'

// Intraday ranges use minute/hour aggregates instead of daily bars — daily-only
// was the "graphs don't show quick aggs" gap: the backend already supported
// arbitrary timespans (fetch_agg_bars takes one), the frontend just never
// exposed anything but 'day'.
// Days-since-Jan-1 is computed once at module load (page-load time) rather
// than re-derived per render — fine for a formula plotter that isn't as
// precision-critical as the main price chart's own YTD button.
const daysSinceJan1 = Math.ceil((Date.now() - new Date(new Date().getFullYear(), 0, 1).getTime()) / 86400000)

const RANGE_OPTIONS = [
  { label: '1D',  days: 1,     timespan: 'minute' },
  { label: '5D',  days: 5,     timespan: 'minute' },
  { label: '1M',  days: 30,    timespan: 'hour' },
  { label: '3M',  days: 90,    timespan: 'day' },
  { label: '6M',  days: 180,   timespan: 'day' },
  { label: 'YTD', days: daysSinceJan1, timespan: 'day' },
  { label: '1Y',  days: 365,   timespan: 'day' },
  { label: '2Y',  days: 730,   timespan: 'day' },
  { label: '5Y',  days: 1825,  timespan: 'day' },
  // Monthly bars keep this well under the backend's 5000-bar cap even across decades.
  { label: 'All', days: 10950, timespan: 'month' },
]

const SAVE_KEY = 'terminal_saved_graphs'
function loadSaved() {
  try { return JSON.parse(localStorage.getItem(SAVE_KEY) || '[]') } catch { return [] }
}
function persistSaved(list) {
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(list)) } catch {}
}

function fmtDate(ts, timespan) {
  if (ts == null) return ''
  const d = new Date(typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts)
  if (timespan === 'minute' || timespan === 'hour') {
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
      + ' ' + d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }
  return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}

export default function GraphBuilder() {
  const { data: meta } = useGraphFunctions()
  const [expr, setExpr] = useState('SMA(AAPL,20) - SMA(AAPL,50)')
  const [range, setRange] = useState(() => RANGE_OPTIONS.find(o => o.label === '1Y'))
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(loadSaved)

  const run = async (overrideExpr, overrideRange) => {
    const e = overrideExpr ?? expr
    const r = overrideRange ?? range
    if (!e.trim()) return
    setLoading(true)
    try { setResult(await runGraphEval(e.trim(), r.days, r.timespan)) }
    finally { setLoading(false) }
  }

  const saveGraph = () => {
    if (!expr.trim()) return
    const next = [{ expr: expr.trim(), range, ts: Date.now() }, ...saved.filter(s => s.expr !== expr.trim())].slice(0, 20)
    setSaved(next)
    persistSaved(next)
  }
  const removeSaved = (e, ev) => {
    ev.stopPropagation()
    const next = saved.filter(s => s.expr !== e)
    setSaved(next)
    persistSaved(next)
  }
  const loadGraph = (s) => {
    setExpr(s.expr)
    setRange(s.range)
    run(s.expr, s.range)
  }

  const chartData = result?.points?.map(p => ({ t: p.t, v: p.v })) || []
  const values = chartData.map(p => p.v).filter(v => v != null)
  const last = values.length ? values[values.length - 1] : null
  const crossesZero = values.length > 0 && Math.min(...values) < 0 && Math.max(...values) > 0
  const isSaved = saved.some(s => s.expr === expr.trim())

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
            1D/5D use minute bars, 1M uses hourly bars, everything else uses
            daily bars. Hit Save to keep a formula in the list on the left —
            it's stored in this browser only.
            <br/><br/>
            This is evaluated by a restricted parser, not a live code
            interpreter — only arithmetic and the functions listed above are
            ever allowed to run.
          </Explain>
          {RANGE_OPTIONS.map(o => (
            <button key={o.label} className={`btn ${range.label === o.label ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px' }}
              onClick={() => { setRange(o); if (result) run(expr, o) }}>
              {o.label}
            </button>
          ))}
        </div>
      </div>
      <div className="panel-body" style={{ padding: 0, display: 'flex' }}>
        {/* Saved formulas rail */}
        <div style={{ width: 160, flexShrink: 0, borderRight: '1px solid var(--border)', overflowY: 'auto' }}>
          <div className="label" style={{ padding: '10px 10px 6px' }}>Saved</div>
          {saved.length === 0 && (
            <div className="dim" style={{ fontSize: 10, padding: '0 10px 10px' }}>
              Nothing saved yet — hit Save after plotting a formula.
            </div>
          )}
          {saved.map(s => (
            <div key={s.expr} onClick={() => loadGraph(s)}
              style={{
                padding: '7px 10px', cursor: 'pointer', fontSize: 10.5,
                fontFamily: 'var(--font-mono)', borderBottom: '1px solid var(--border)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 4,
                background: s.expr === expr.trim() ? 'var(--bg-raised)' : 'transparent',
              }}>
              <span style={{ wordBreak: 'break-word', color: 'var(--text-primary)' }}>{s.expr}</span>
              <span onClick={(ev) => removeSaved(s.expr, ev)} className="dim"
                style={{ flexShrink: 0, cursor: 'pointer' }} title="Remove">×</span>
            </div>
          ))}
        </div>

        <div style={{ flex: 1, minWidth: 0, padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Formula bar */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span className="dim" style={{ fontSize: 11, fontFamily: 'var(--font-mono)', flexShrink: 0 }}>fx</span>
            <input className="input" style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 13 }}
              value={expr}
              onChange={e => setExpr(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && run()}
              placeholder="e.g. SMA(AAPL,20) - SMA(AAPL,50)" />
            <button className="btn active" onClick={() => run()} disabled={loading || !expr.trim()}>
              {loading ? 'Plotting…' : 'Plot'}
            </button>
            <button className="btn" onClick={saveGraph} disabled={!expr.trim() || isSaved}
              title={isSaved ? 'Already saved' : 'Save this formula'}>
              {isSaved ? 'Saved ✓' : 'Save'}
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
              <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {result.expr}
                </span>
                {last != null && (
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--gold-bright)', fontWeight: 600 }}>
                    {last.toFixed(4)}
                  </span>
                )}
                <span className="dim" style={{ fontSize: 10 }}>
                  {result.symbols?.join(' · ')} · {chartData.length} bars · {range.label} ({range.timespan})
                </span>
              </div>
              <div style={{ flex: 1, minHeight: 260 }}>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
                    <XAxis dataKey="t" tickFormatter={(t) => fmtDate(t, range.timespan)} stroke="var(--text-dim)" fontSize={10}
                      minTickGap={50} />
                    <YAxis stroke="var(--text-dim)" fontSize={10} domain={['auto', 'auto']} width={64}
                      label={{ value: result.expr, angle: -90, position: 'insideLeft', fill: 'var(--text-dim)', fontSize: 9 }} />
                    {crossesZero && <ReferenceLine y={0} stroke="var(--text-dim)" strokeDasharray="3 3" />}
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 11 }}
                      labelFormatter={(t) => fmtDate(t, range.timespan)}
                      formatter={(v) => [v?.toFixed(4), result.expr]} />
                    <Line type="monotone" dataKey="v" stroke="var(--gold)" dot={false} strokeWidth={1.5} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
