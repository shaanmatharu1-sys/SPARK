import React, { useState } from 'react'
import { useAlgoList, useAlgoTemplates, useIndicators, algoApi } from '../../hooks/useMarketData'
import { RuleEditor } from '../Backtest/BacktestTab'

function Pnl({ value, pct }) {
  if (value == null) return <span className="dim">—</span>
  const pos = value >= 0
  return (
    <span style={{ color: pos ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
      {pos ? '+' : ''}{pct ? `${value.toFixed(2)}%` : `$${Math.abs(value).toLocaleString(undefined, {maximumFractionDigits:0})}`}
    </span>
  )
}

function AlgoCard({ algo, onRun, onReset, onDelete, busy }) {
  const cfg = algo.config
  const pf  = algo.portfolio
  const [expanded, setExpanded] = useState(false)

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
      marginBottom: 8, background: 'var(--bg-panel-2)', overflow: 'hidden',
    }}>
      <div style={{ padding: '10px 12px', display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', cursor: 'pointer' }}
           onClick={() => setExpanded(!expanded)}>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, fontWeight: 600,
                        color: 'var(--text-primary)' }}>{cfg.name}</div>
          <div className="dim" style={{ fontSize: 10, marginTop: 2 }}>
            {cfg.strategy} · {cfg.universe.join(' ')}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15 }}>
            <Pnl value={pf.total_return} pct />
          </div>
          <div className="dim" style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>
            ${pf.equity?.toLocaleString(undefined, {maximumFractionDigits:0})}
          </div>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '0 12px 12px', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: 16, padding: '10px 0', fontSize: 11 }}>
            <div><span className="dim">Cash </span>
              <span className="mono">${pf.cash?.toLocaleString(undefined,{maximumFractionDigits:0})}</span></div>
            <div><span className="dim">Realized </span><Pnl value={pf.realized_pnl} /></div>
            <div><span className="dim">Unrealized </span><Pnl value={pf.unrealized_pnl} /></div>
            <div><span className="dim">Fills </span><span className="mono">{pf.n_fills}</span></div>
          </div>

          {pf.positions?.length > 0 && (
            <table className="bbg-table" style={{ marginBottom: 10 }}>
              <thead><tr><th>SYMBOL</th><th>QTY</th><th>AVG</th><th>LAST</th><th>MKT VAL</th><th>UNREAL</th></tr></thead>
              <tbody>
                {pf.positions.map(p => (
                  <tr key={p.symbol}>
                    <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{p.symbol}</td>
                    <td style={{ color: p.quantity >= 0 ? 'var(--text-primary)' : 'var(--red)' }}>
                      {p.quantity}
                    </td>
                    <td>{p.avg_price?.toFixed(2)}</td>
                    <td>{p.last_price?.toFixed(2)}</td>
                    <td>${p.market_value?.toLocaleString(undefined,{maximumFractionDigits:0})}</td>
                    <td><Pnl value={p.unrealized_pnl} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn active" disabled={busy}
              onClick={(e) => { e.stopPropagation(); onRun(cfg.algo_id) }}>
              {busy ? 'Running…' : 'Run Once'}
            </button>
            <button className="btn" onClick={(e) => { e.stopPropagation(); onReset(cfg.algo_id) }}>
              Reset
            </button>
            <button className="btn" style={{ marginLeft: 'auto', borderColor: 'var(--red-dim)' }}
              onClick={(e) => { e.stopPropagation(); onDelete(cfg.algo_id) }}>
              Delete
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Algo() {
  const { data: algos, loading, refresh } = useAlgoList()
  const { data: templates } = useAlgoTemplates()
  const { data: indicators } = useIndicators()
  const [busy, setBusy] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const [newMode, setNewMode] = useState('template') // template | custom
  const [capital, setCapital] = useState(100000)
  const [maxPos, setMaxPos] = useState(20)
  const [customUniverse, setCustomUniverse] = useState('')

  // Custom-model builder state — same rule shape as the backtest builder,
  // so a model you back-tested there can be pasted straight in here to
  // actually run it live (paper) instead of just historically.
  const [modelName, setModelName] = useState('My Custom Model')
  const [entry, setEntry] = useState([{ indicator: 'rsi', op: '<', value: 30, param: 14 }])
  const [exit, setExit]   = useState([{ indicator: 'rsi', op: '>', value: 70, param: 14 }])

  const createFromTemplate = async (t) => {
    const universe = customUniverse.trim()
      ? customUniverse.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
      : t.universe
    await algoApi.create({
      name: t.name, strategy: t.strategy, universe,
      capital: Number(capital), max_position_pct: Number(maxPos) / 100, params: t.params,
    })
    setShowNew(false); setCustomUniverse('')
    refresh()
  }

  const createCustom = async () => {
    const universe = customUniverse.trim()
      ? customUniverse.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
      : []
    if (!universe.length || !entry.length) return
    await algoApi.create({
      name: modelName || 'Custom Model', strategy: 'custom', universe,
      capital: Number(capital), max_position_pct: Number(maxPos) / 100,
      params: { entry, exit },
    })
    setShowNew(false); setCustomUniverse('')
    refresh()
  }

  const run = async (id) => { setBusy(id); await algoApi.run(id); setBusy(null); refresh() }
  const runAll = async () => {
    setBusy('all')
    for (const a of (algos || [])) { await algoApi.run(a.config.algo_id) }
    setBusy(null); refresh()
  }
  const reset = async (id) => { await algoApi.reset(id); refresh() }
  const remove = async (id) => { await algoApi.remove(id); refresh() }

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Algorithm Lab</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span className="dim" style={{ fontSize: 9 }}>PAPER · NO REAL EXECUTION</span>
          {algos?.length > 0 && (
            <button className="btn" onClick={runAll} disabled={busy === 'all'}>
              {busy === 'all' ? 'Running all…' : 'Run All'}
            </button>
          )}
          <button className="btn active" onClick={() => setShowNew(!showNew)}>+ New Algo</button>
        </div>
      </div>
      <div className="panel-body" style={{ padding: 12 }}>
        {showNew && templates && (
          <div style={{ marginBottom: 12, padding: 12, background: 'var(--bg-base)',
                        borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              <button className={`btn ${newMode === 'template' ? 'active' : ''}`} onClick={() => setNewMode('template')}>
                From Template
              </button>
              <button className={`btn ${newMode === 'custom' ? 'active' : ''}`} onClick={() => setNewMode('custom')}>
                Build Custom Model
              </button>
            </div>

            {/* Customization controls */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <div>
                <div className="label" style={{ marginBottom: 3 }}>Capital</div>
                <input className="input" style={{ width: 90 }} type="number" value={capital}
                  onChange={e => setCapital(e.target.value)} />
              </div>
              <div>
                <div className="label" style={{ marginBottom: 3 }}>Max Pos %</div>
                <input className="input" style={{ width: 60 }} type="number" value={maxPos}
                  onChange={e => setMaxPos(e.target.value)} />
              </div>
              <div style={{ flex: 1, minWidth: 160 }}>
                <div className="label" style={{ marginBottom: 3 }}>
                  {newMode === 'custom' ? 'Universe (required)' : 'Universe (optional override)'}
                </div>
                <input className="input" style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                  placeholder="e.g. AAPL, MSFT, NVDA" value={customUniverse}
                  onChange={e => setCustomUniverse(e.target.value.toUpperCase())} />
              </div>
            </div>

            {newMode === 'template' ? (
              <>
                <div className="label" style={{ marginBottom: 8 }}>Choose a strategy template</div>
                {templates.map((t, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between',
                                        alignItems: 'center', padding: '8px 0',
                                        borderBottom: i < templates.length-1 ? '1px solid var(--border)' : 'none' }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{t.name}</div>
                      <div className="dim" style={{ fontSize: 10 }}>{t.blurb}</div>
                    </div>
                    <button className="btn" onClick={() => createFromTemplate(t)}>Create</button>
                  </div>
                ))}
              </>
            ) : (
              <>
                <div style={{ marginBottom: 10 }}>
                  <div className="label" style={{ marginBottom: 3 }}>Model name</div>
                  <input className="input" style={{ width: '100%' }} value={modelName}
                    onChange={e => setModelName(e.target.value)} />
                </div>
                <div className="dim" style={{ fontSize: 10, marginBottom: 8, lineHeight: 1.5 }}>
                  Same rule builder as the Backtest tab — pick indicators and conditions.
                  Goes long when ALL entry rules hold, flat when ANY exit rule holds. This
                  version runs live against real data and paper-trades it, instead of just
                  backtesting history.
                </div>
                <RuleEditor rules={entry} setRules={setEntry} indicators={indicators} label="ENTRY (all must hold)" />
                <RuleEditor rules={exit} setRules={setExit} indicators={indicators} label="EXIT (any triggers)" />
                <button className="btn active" onClick={createCustom}
                  disabled={!customUniverse.trim() || !entry.length}>
                  Create Custom Model
                </button>
              </>
            )}
          </div>
        )}

        {loading && <div className="dim" style={{ padding: 8 }}>Loading algorithms…</div>}
        {algos?.length === 0 && !showNew && (
          <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-dim)' }}>
            <div style={{ fontSize: 15, marginBottom: 6, fontWeight: 600 }}>
              No algorithms yet
            </div>
            <div style={{ fontSize: 11 }}>Create one from a template to start paper trading.</div>
          </div>
        )}

        {algos?.map(a => (
          <AlgoCard key={a.config.algo_id} algo={a} onRun={run} onReset={reset}
                    onDelete={remove} busy={busy === a.config.algo_id} />
        ))}
      </div>
    </div>
  )
}
