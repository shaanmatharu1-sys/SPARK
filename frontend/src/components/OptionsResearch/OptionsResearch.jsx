import React, { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useIVRank, useOptionsFlow, useOptionsSkew, optionsApi } from '../../hooks/useMarketData'
import { useSymbol } from '../../hooks/useSymbol'

// ── Payoff modeler ──
function PayoffModeler({ symbol }) {
  const [strategy, setStrategy] = useState('long_straddle')
  const [spot, setSpot] = useState(100)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  // Default params per strategy (simple, user can adjust spot)
  const defaultParams = {
    long_call:        { strike: 100, premium: 4 },
    long_put:         { strike: 100, premium: 4 },
    bull_call_spread: { long_strike: 100, long_premium: 4, short_strike: 110, short_premium: 1.5 },
    bear_put_spread:  { long_strike: 100, long_premium: 4, short_strike: 90, short_premium: 1.5 },
    long_straddle:    { strike: 100, call_premium: 4, put_premium: 4 },
    long_strangle:    { call_strike: 105, call_premium: 2.5, put_strike: 95, put_premium: 2.5 },
    iron_condor:      { put_long: 85, put_long_prem: 0.5, put_short: 95, put_short_prem: 1.5,
                        call_short: 105, call_short_prem: 1.5, call_long: 115, call_long_prem: 0.5 },
  }

  const run = async () => {
    setLoading(true)
    const r = await optionsApi.payoff(strategy, spot, defaultParams[strategy] || {})
    setResult(r); setLoading(false)
  }
  useEffect(() => { run() }, [strategy, spot])

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <select className="input" value={strategy} onChange={e => setStrategy(e.target.value)}
          style={{ fontFamily: 'var(--font-ui)' }}>
          <option value="long_call">Long Call</option>
          <option value="long_put">Long Put</option>
          <option value="bull_call_spread">Bull Call Spread</option>
          <option value="bear_put_spread">Bear Put Spread</option>
          <option value="long_straddle">Long Straddle</option>
          <option value="long_strangle">Long Strangle</option>
          <option value="iron_condor">Iron Condor</option>
        </select>
        <span className="dim" style={{ fontSize: 10 }}>SPOT:</span>
        <input className="input" style={{ width: 60 }} type="number" value={spot}
          onChange={e => setSpot(parseFloat(e.target.value) || 100)} />
      </div>

      {loading ? <div className="dim">Computing…</div> : result?.curve && (
        <>
          <div style={{ display: 'flex', gap: 12, marginBottom: 10, fontSize: 11 }}>
            <div><span className="dim">Max profit </span>
              <span className="green">{result.max_profit != null ? '$'+result.max_profit : '∞'}</span></div>
            <div><span className="dim">Max loss </span>
              <span className="red">${result.max_loss}</span></div>
            <div><span className="dim">Break-even </span>
              <span className="gold">{result.breakevens?.join(', ') || '—'}</span></div>
          </div>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={result.curve} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="price" tick={{ fill: 'var(--text-dim)', fontSize: 9 }}
                       interval={Math.floor(result.curve.length / 6)} />
                <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 10 }} width={44}
                       tickFormatter={v => '$'+v} />
                <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                         borderRadius: 6, fontSize: 11 }}
                         formatter={v => ['$'+v, 'P&L']} labelFormatter={v => 'Price $'+v} />
                <ReferenceLine y={0} stroke="var(--text-dim)" strokeWidth={1} />
                <ReferenceLine x={result.spot} stroke="var(--gold-dim)" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="payoff" stroke="var(--gold)" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}

// ── IV / Flow / Skew metrics ──
function Metrics({ symbol }) {
  const { data: iv } = useIVRank(symbol)
  const { data: flow } = useOptionsFlow(symbol)
  const { data: skew } = useOptionsSkew(symbol)

  return (
    <div style={{ padding: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
      <div style={{ padding: 10, background: 'var(--bg-base)', borderRadius: 6 }}>
        <div className="label" style={{ marginBottom: 6 }}>IV Rank / Percentile</div>
        {iv?.iv_rank != null ? (
          <>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)',
                          color: iv.regime === 'high' ? 'var(--red)' : iv.regime === 'low' ? 'var(--green)' : 'var(--gold)' }}>
              {iv.iv_rank}
            </div>
            <div className="dim" style={{ fontSize: 10 }}>
              IV {iv.current_iv}% · pctile {iv.iv_percentile} · {iv.regime}
            </div>
          </>
        ) : <div className="dim" style={{ fontSize: 10 }}>{iv?.note || 'Building history…'}</div>}
      </div>

      <div style={{ padding: 10, background: 'var(--bg-base)', borderRadius: 6 }}>
        <div className="label" style={{ marginBottom: 6 }}>Put/Call Flow</div>
        {flow?.pcr_volume != null ? (
          <>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
              {flow.pcr_volume}
            </div>
            <div className="dim" style={{ fontSize: 10 }}>{flow.sentiment?.replace('_', ' ')}</div>
          </>
        ) : <div className="dim" style={{ fontSize: 10 }}>No flow data</div>}
      </div>

      <div style={{ padding: 10, background: 'var(--bg-base)', borderRadius: 6, gridColumn: '1 / 3' }}>
        <div className="label" style={{ marginBottom: 6 }}>Vol Skew (10% OTM)</div>
        {skew?.skew != null ? (
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)',
                          color: skew.skew > 0 ? 'var(--red)' : 'var(--green)' }}>
              {skew.skew > 0 ? '+' : ''}{skew.skew}
            </div>
            <div className="dim" style={{ fontSize: 10 }}>
              Put IV {skew.put_iv}% vs Call IV {skew.call_iv}% · {skew.read}
            </div>
          </div>
        ) : <div className="dim" style={{ fontSize: 10 }}>No skew data</div>}
      </div>
    </div>
  )
}

export default function OptionsResearch() {
  const { symbol, setSymbol } = useSymbol()
  const [input, setInput] = useState(symbol)
  useEffect(() => { setInput(symbol) }, [symbol])
  const [tab, setTab] = useState('payoff')

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Options Research</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <button className={`btn ${tab === 'payoff' ? 'active' : ''}`} onClick={() => setTab('payoff')}>PAYOFF</button>
          <button className={`btn ${tab === 'metrics' ? 'active' : ''}`} onClick={() => setTab('metrics')}>IV / FLOW</button>
          <input className="input" style={{ width: 60 }} value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && setSymbol(input)} />
        </div>
      </div>
      <div className="panel-body">
        {tab === 'payoff'  && <PayoffModeler symbol={symbol} />}
        {tab === 'metrics' && <Metrics symbol={symbol} />}
      </div>
    </div>
  )
}
