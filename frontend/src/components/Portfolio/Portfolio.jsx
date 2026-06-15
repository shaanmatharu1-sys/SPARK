import React, { useState } from 'react'
import { usePortfolio, portfolioApi } from '../../hooks/useMarketData'

export default function Portfolio() {
  const { data, loading, refresh } = usePortfolio()
  const [sym, setSym] = useState('')
  const [shares, setShares] = useState('')
  const [cost, setCost] = useState('')

  const add = async () => {
    if (!sym || !shares || !cost) return
    await portfolioApi.add(sym.toUpperCase(), parseFloat(shares), parseFloat(cost))
    setSym(''); setShares(''); setCost(''); refresh()
  }
  const remove = async (s) => { await portfolioApi.remove(s); refresh() }

  const pnlColor = (v) => v == null ? 'var(--text-dim)' : v >= 0 ? 'var(--green)' : 'var(--red)'

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Portfolio</span>
        {data && !data.empty && (
          <div style={{ display: 'flex', gap: 14, fontSize: 12, fontFamily: 'var(--font-mono)' }}>
            <span><span className="dim">VALUE </span>${data.total_value?.toLocaleString()}</span>
            <span style={{ color: pnlColor(data.total_pnl) }}>
              {data.total_pnl >= 0 ? '+' : ''}${data.total_pnl?.toLocaleString()} ({data.total_pnl_pct}%)
            </span>
          </div>
        )}
      </div>
      <div className="panel-body">
        {/* Add holding */}
        <div style={{ padding: 10, display: 'flex', gap: 6, alignItems: 'center',
                      borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
          <input className="input" placeholder="SYMBOL" style={{ width: 80 }} value={sym}
            onChange={e => setSym(e.target.value.toUpperCase())} />
          <input className="input" placeholder="SHARES" style={{ width: 70 }} type="number" value={shares}
            onChange={e => setShares(e.target.value)} />
          <input className="input" placeholder="COST/SH" style={{ width: 70 }} type="number" value={cost}
            onChange={e => setCost(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && add()} />
          <button className="btn active" onClick={add}>Add</button>
        </div>

        {loading ? <div style={{ padding: 16, color: 'var(--text-dim)' }}>Loading…</div>
         : data?.empty || !data?.positions?.length ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-dim)' }}>
            <div style={{ fontSize: 14, marginBottom: 6 }}>No holdings yet</div>
            <div style={{ fontSize: 11 }}>Add a position above to start tracking your portfolio.</div>
          </div>
        ) : (
          <table className="bbg-table">
            <thead>
              <tr><th>SYMBOL</th><th>SHARES</th><th>COST</th><th>LAST</th><th>MKT VAL</th><th>P&L</th><th>WT%</th><th></th></tr>
            </thead>
            <tbody>
              {data.positions.map((p, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{p.symbol}</td>
                  <td>{p.shares}</td>
                  <td>{p.cost_basis}</td>
                  <td>{p.last_price ?? '—'}</td>
                  <td>{p.market_value != null ? '$'+p.market_value.toLocaleString() : '—'}</td>
                  <td style={{ color: pnlColor(p.unrealized_pnl) }}>
                    {p.unrealized_pnl != null ?
                      `${p.unrealized_pnl >= 0 ? '+' : ''}$${p.unrealized_pnl.toLocaleString()} (${p.unrealized_pct}%)` : '—'}
                  </td>
                  <td className="dim">{p.weight ?? '—'}</td>
                  <td><span style={{ cursor: 'pointer', color: 'var(--text-dim)', fontSize: 10 }}
                            onClick={() => remove(p.symbol)}>remove</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
