import React, { useState } from 'react'
import { useAlgoList, useAlgoTemplates, algoApi } from '../../hooks/useMarketData'

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
              {busy ? 'Running…' : '▶ Run Once'}
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
  const [busy, setBusy] = useState(null)
  const [showNew, setShowNew] = useState(false)

  const createFromTemplate = async (t) => {
    await algoApi.create({
      name: t.name, strategy: t.strategy, universe: t.universe,
      capital: 100000, max_position_pct: 0.2, params: t.params,
    })
    setShowNew(false)
    refresh()
  }

  const run = async (id) => { setBusy(id); await algoApi.run(id); setBusy(null); refresh() }
  const reset = async (id) => { await algoApi.reset(id); refresh() }
  const remove = async (id) => { await algoApi.remove(id); refresh() }

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Algorithm Lab</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span className="dim" style={{ fontSize: 9 }}>PAPER · NO REAL EXECUTION</span>
          <button className="btn active" onClick={() => setShowNew(!showNew)}>+ New Algo</button>
        </div>
      </div>
      <div className="panel-body" style={{ padding: 12 }}>
        {showNew && templates && (
          <div style={{ marginBottom: 12, padding: 12, background: 'var(--bg-base)',
                        borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            <div className="label" style={{ marginBottom: 8 }}>Choose a template</div>
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
          </div>
        )}

        {loading && <div className="dim" style={{ padding: 8 }}>Loading algorithms…</div>}
        {algos?.length === 0 && !showNew && (
          <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-dim)' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, marginBottom: 6 }}>
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
