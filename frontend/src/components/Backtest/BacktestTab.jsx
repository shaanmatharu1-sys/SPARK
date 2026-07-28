import React, { useState, useMemo } from 'react'
import {
  LineChart, Line, AreaChart, Area, ComposedChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { useIndicators, useStrategies, runCustomBacktest, runPresetBacktest } from '../../hooks/useMarketData'
import { useSymbol } from '../../hooks/useSymbol'
import Explain from '../common/Explain'

const OPS = [
  { v: '<', label: 'is below' },
  { v: '>', label: 'is above' },
  { v: 'cross_above', label: 'crosses above' },
  { v: 'cross_below', label: 'crosses below' },
]

function StatBox({ label, value, good }) {
  const color = good === undefined ? 'var(--text)' : good ? 'var(--green)' : 'var(--red)'
  return (
    <div style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)',
                  borderRadius: 5, padding: '8px 10px', minWidth: 90 }}>
      <div className="dim" style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, color, fontWeight: 600 }}>{value}</div>
    </div>
  )
}

function fmtDate(t) {
  if (t == null) return ''
  const d = new Date(t < 1e12 ? t * 1000 : t)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
}

// Compounds daily strategy returns into calendar-month returns for the heatmap.
function monthlyReturns(dates, returns) {
  const byMonth = {}
  for (let i = 0; i < returns.length; i++) {
    if (dates[i] == null) continue
    const d = new Date(dates[i] * 1000)
    const key = `${d.getFullYear()}-${d.getMonth()}`
    byMonth[key] ||= { product: 1, year: d.getFullYear(), month: d.getMonth() }
    byMonth[key].product *= (1 + returns[i])
  }
  return Object.values(byMonth).map(v => ({ year: v.year, month: v.month, ret: v.product - 1 }))
}

function heatColor(ret) {
  if (ret == null) return 'var(--bg-base)'
  const clamped = Math.max(-0.1, Math.min(0.1, ret))
  const a = 0.15 + Math.abs(clamped) / 0.1 * 0.5
  return ret >= 0 ? `rgba(63,182,139,${a})` : `rgba(224,85,107,${a})`
}

const MONTH_LABELS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

function MonthlyReturnsHeatmap({ dates, returns }) {
  const cells = useMemo(() => monthlyReturns(dates || [], returns || []), [dates, returns])
  const years = [...new Set(cells.map(c => c.year))].sort()
  if (!years.length) return null
  const byKey = Object.fromEntries(cells.map(c => [`${c.year}-${c.month}`, c.ret]))
  return (
    <div style={{ marginTop: 12 }}>
      <div className="label" style={{ marginBottom: 4 }}>Monthly Returns</div>
      <table style={{ borderCollapse: 'collapse', fontSize: 9 }}>
        <thead>
          <tr>
            <th style={{ padding: '2px 6px' }} />
            {MONTH_LABELS.map((m, i) => <th key={i} className="dim" style={{ padding: '2px 6px', fontWeight: 500 }}>{m}</th>)}
          </tr>
        </thead>
        <tbody>
          {years.map(y => (
            <tr key={y}>
              <td className="dim" style={{ padding: '2px 6px' }}>{y}</td>
              {MONTH_LABELS.map((_, m) => {
                const ret = byKey[`${y}-${m}`]
                return (
                  <td key={m} title={ret != null ? `${(ret * 100).toFixed(1)}%` : ''}
                      style={{ padding: '4px 6px', textAlign: 'center', background: heatColor(ret),
                               color: 'var(--text-primary)', minWidth: 30 }}>
                    {ret != null ? `${(ret * 100).toFixed(0)}` : ''}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function RuleEditor({ rules, setRules, indicators, label }) {
  const add = () => setRules([...rules, { indicator: 'rsi', op: '<', value: 30, param: 14 }])
  const update = (i, k, v) => setRules(rules.map((r, j) => j === i ? { ...r, [k]: v } : r))
  const remove = (i) => setRules(rules.filter((_, j) => j !== i))

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)', marginBottom: 5 }}>{label}</div>
      {rules.map((r, i) => (
        <div key={i} style={{ display: 'flex', gap: 4, alignItems: 'center', marginBottom: 4, flexWrap: 'wrap' }}>
          <select className="input" value={r.indicator} style={{ fontSize: 11 }}
            onChange={e => {
              const meta = indicators?.[e.target.value]
              update(i, 'indicator', e.target.value)
              if (meta) update(i, 'param', meta.default_param)
            }}>
            {indicators && Object.entries(indicators).map(([k, m]) =>
              <option key={k} value={k}>{m.name}</option>)}
          </select>
          <input className="input" type="number" value={r.param} style={{ width: 50, fontSize: 11 }}
            title="period/window" onChange={e => update(i, 'param', parseInt(e.target.value))} />
          <select className="input" value={r.op} style={{ fontSize: 11 }}
            onChange={e => update(i, 'op', e.target.value)}>
            {OPS.map(o => <option key={o.v} value={o.v}>{o.label}</option>)}
          </select>
          <input className="input" type="number" value={r.value} style={{ width: 60, fontSize: 11 }}
            onChange={e => update(i, 'value', parseFloat(e.target.value))} />
          <button className="btn" style={{ fontSize: 11 }} onClick={() => remove(i)}>x</button>
        </div>
      ))}
      <button className="btn" style={{ fontSize: 11 }} onClick={add}>+ add rule</button>
    </div>
  )
}

export default function Backtest() {
  const { symbol } = useSymbol()
  const { data: indicators } = useIndicators()
  const { data: strategies } = useStrategies()
  const [mode, setMode] = useState('custom')   // custom | preset
  const [entry, setEntry] = useState([{ indicator: 'rsi', op: '<', value: 30, param: 14 }])
  const [exit, setExit]   = useState([{ indicator: 'rsi', op: '>', value: 70, param: 14 }])
  const [preset, setPreset] = useState('zscore_reversion')
  const [days, setDays] = useState(730)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    setLoading(true)
    try {
      const r = mode === 'custom'
        ? await runCustomBacktest(symbol, entry, exit, days)
        : await runPresetBacktest(symbol, preset, days)
      setResult(r)
    } finally { setLoading(false) }
  }

  const s = result?.stats
  const hasDates = result?.dates?.length > 0
  const equityData = useMemo(() => {
    if (!result?.equity_curve) return []
    const positions = result.positions || []
    return result.equity_curve.map((e, i) => ({
      x: hasDates ? result.dates[i] : i,
      equity: e,
      drawdown: result.drawdown ? result.drawdown[i] * 100 : null,
      benchmark: result.benchmark?.equity_curve?.[i] ?? null,
      // Mark bars where the position actually changed — an entry/exit — so
      // trades can be pinned on the equity curve instead of being invisible.
      trade: i > 0 && positions[i - 1] != null && positions[i] !== positions[i - 1] ? e : null,
    }))
  }, [result, hasDates])
  const rollingSharpeData = useMemo(() => {
    if (!result?.rolling_sharpe) return []
    // strategy_returns/rolling_sharpe are one shorter than equity_curve/dates
    // (returns, not levels) — offset by 1 to line back up with real dates.
    return result.rolling_sharpe.map((v, i) => ({
      x: hasDates ? result.dates[i + 1] : i + 1,
      sharpe: v,
    }))
  }, [result, hasDates])
  const xTick = hasDates ? fmtDate : undefined

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Backtest — {symbol}</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Explain title="How backtesting works">
            A backtest replays a trading rule over historical prices to see how it
            would have performed. <b>Build your own</b>: pick indicators (RSI, momentum,
            etc.) and conditions for when to buy (entry) and sell (exit). The engine
            goes long when all entry rules hold and flat when any exit rule triggers.
            <br/><br/>
            <b>Reading results:</b> Sharpe &gt; 1 is decent risk-adjusted return; max
            drawdown is the worst peak-to-trough loss; hit rate is % of winning periods.
            Beware overfitting — tuning rules until the curve looks great usually fails
            on new data.
          </Explain>
          <button className={`btn ${mode === 'custom' ? 'active' : ''}`} onClick={() => setMode('custom')}>Build your own</button>
          <button className={`btn ${mode === 'preset' ? 'active' : ''}`} onClick={() => setMode('preset')}>Presets</button>
        </div>
      </div>
      <div className="panel-body" style={{ display: 'flex', gap: 12, padding: 12, overflow: 'auto' }}>
        {/* Left: strategy builder */}
        <div style={{ width: 340, flexShrink: 0 }}>
          {mode === 'custom' ? (
            <>
              <div className="dim" style={{ fontSize: 10, marginBottom: 8, lineHeight: 1.5 }}>
                Go long when ALL entry rules hold; go flat when ANY exit rule holds.
              </div>
              <RuleEditor rules={entry} setRules={setEntry} indicators={indicators} label="ENTRY (all must hold)" />
              <RuleEditor rules={exit} setRules={setExit} indicators={indicators} label="EXIT (any triggers)" />
            </>
          ) : (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)', marginBottom: 5 }}>STRATEGY</div>
              <select className="input" value={preset} onChange={e => setPreset(e.target.value)} style={{ width: '100%' }}>
                {strategies && Object.entries(strategies).map(([k, m]) =>
                  <option key={k} value={k}>{m.name}</option>)}
              </select>
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 8 }}>
            <span className="dim" style={{ fontSize: 10 }}>LOOKBACK</span>
            <select className="input" value={days} onChange={e => setDays(parseInt(e.target.value))} style={{ fontSize: 11 }}>
              <option value={365}>1 year</option>
              <option value={730}>2 years</option>
              <option value={1825}>5 years</option>
            </select>
            <button className="btn active" onClick={run} disabled={loading} style={{ marginLeft: 'auto' }}>
              {loading ? 'Running…' : 'Run backtest'}
            </button>
          </div>
        </div>

        {/* Right: results */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {!result && <div className="dim" style={{ fontSize: 12, padding: 20 }}>Build a strategy and run it to see the equity curve and performance stats.</div>}
          {result?.error && <div style={{ color: 'var(--red)', padding: 12 }}>{result.error}</div>}
          {s && (
            <>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                <StatBox label="Total Return" value={`${(s.total_return * 100).toFixed(1)}%`} good={s.total_return > 0} />
                <StatBox label="Ann. Return" value={`${(s.ann_return * 100).toFixed(1)}%`} good={s.ann_return > 0} />
                <StatBox label="Sharpe" value={s.sharpe?.toFixed(2)} good={s.sharpe > 1} />
                <StatBox label="Sortino" value={s.sortino?.toFixed(2)} good={s.sortino > 1} />
                <StatBox label="Max DD" value={`${(s.max_drawdown * 100).toFixed(1)}%`} good={s.max_drawdown > -0.2} />
                <StatBox label="Calmar" value={s.calmar?.toFixed(2)} good={s.calmar > 0.5} />
                <StatBox label="Hit Rate" value={`${(s.hit_rate * 100).toFixed(0)}%`} good={s.hit_rate > 0.5} />
                <StatBox label="Trades" value={s.n_trades} />
                {result.total_cost_bps_paid != null && (
                  <StatBox label="Costs Paid" value={`${result.total_cost_bps_paid.toFixed(0)}bps`} />
                )}
              </div>

              <div className="dim" style={{ fontSize: 9, marginBottom: 2 }}>
                EQUITY CURVE{result.benchmark ? ` — vs ${result.benchmark.symbol} buy &amp; hold` : ''}
              </div>
              <div style={{ height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={equityData}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
                    <XAxis dataKey="x" tickFormatter={xTick} stroke="var(--text-dim)" fontSize={10} minTickGap={50} />
                    <YAxis stroke="var(--text-dim)" fontSize={10} domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 11 }}
                             labelFormatter={xTick} />
                    {result.benchmark && (
                      <Line type="monotone" dataKey="benchmark" stroke="var(--steel-bright)" strokeDasharray="3 3"
                            dot={false} strokeWidth={1.2} isAnimationActive={false} name={result.benchmark.symbol} />
                    )}
                    <Line type="monotone" dataKey="equity" stroke="var(--gold)" dot={false} strokeWidth={1.5}
                          isAnimationActive={false} name="Strategy" />
                    <Scatter dataKey="trade" fill="var(--gold-bright)" shape="circle" legendType="none" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              <div className="dim" style={{ fontSize: 9, margin: '6px 0 2px' }}>DRAWDOWN</div>
              <div style={{ height: 60 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={equityData}>
                    <XAxis dataKey="x" hide />
                    <YAxis hide domain={['auto', 0]} />
                    <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 10 }}
                             formatter={(v) => [`${v?.toFixed(2)}%`, 'Drawdown']} labelFormatter={xTick} />
                    <Area type="monotone" dataKey="drawdown" stroke="var(--red)" fill="var(--red)"
                          fillOpacity={0.25} strokeWidth={1} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="dim" style={{ fontSize: 9, margin: '6px 0 2px' }}>ROLLING SHARPE (60-period)</div>
              <div style={{ height: 60 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={rollingSharpeData}>
                    <XAxis dataKey="x" hide />
                    <YAxis hide domain={['auto', 'auto']} />
                    <ReferenceLine y={0} stroke="var(--text-dim)" strokeDasharray="2 2" />
                    <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)', fontSize: 10 }}
                             formatter={(v) => [v?.toFixed(2), 'Rolling Sharpe']} labelFormatter={xTick} />
                    <Line type="monotone" dataKey="sharpe" stroke="var(--cyan)" dot={false} strokeWidth={1.2} isAnimationActive={false} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {hasDates && result.strategy_returns && (
                <MonthlyReturnsHeatmap dates={result.dates.slice(1)} returns={result.strategy_returns} />
              )}

              <div className="dim" style={{ fontSize: 9, marginTop: 8, lineHeight: 1.5 }}>
                Equity curve = growth of $1 following the strategy, net of a realistic cost model
                (commission + spread + slippage + size-scaled market impact —
                {result.cost_model ? ` ${result.cost_model.commission_bps}bps commission, ${result.cost_model.spread_bps}bps spread, ${result.cost_model.slippage_bps}bps slippage, ${result.cost_model.impact_coef}bps/unit impact` : ' see cost_model'}).
                Gold dots mark entries/exits. Long/flat only (no shorting/leverage).
                Past performance on historical data does not predict future results — and beware
                overfitting: a great backtest on one symbol often fails out-of-sample.
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
