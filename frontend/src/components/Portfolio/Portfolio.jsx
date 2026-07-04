import React, { useState, useMemo } from 'react'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { usePortfolio, portfolioApi } from '../../hooks/useMarketData'

const PIE_COLORS = [
  'var(--gold)', 'var(--steel-bright)', 'var(--green)', 'var(--purple)',
  'var(--red)', 'var(--cyan)', 'var(--gold-bright)', 'var(--blue-bright)',
]

export default function Portfolio() {
  const { data, loading, refresh } = usePortfolio()
  const [sym, setSym] = useState('')
  const [shares, setShares] = useState('')
  const [cost, setCost] = useState('')

  const add = async () => {
    if (!sym || !shares || !cost) return
    await portfolioApi.add(sym.toUpperCase(), parseFloat(shares), parseFloat(cost))
    setSym(''); setShares(''); setCost('')
    // Small delay lets the backend warm the new symbol's snapshot before refetch,
    // avoiding a transient blank while the quote populates.
    setTimeout(refresh, 600)
  }
  const remove = async (s) => { await portfolioApi.remove(s); setTimeout(refresh, 200) }

  const pnlColor = (v) => v == null ? 'var(--text-dim)' : v >= 0 ? 'var(--green)' : 'var(--red)'

  const positions = data?.positions || []
  const pieData = useMemo(() => (
    positions.filter(p => p.market_value != null).map(p => ({ name: p.symbol, value: p.market_value }))
  ), [positions])
  const pnlBars = useMemo(() => (
    positions.filter(p => p.unrealized_pnl != null)
      .slice().sort((a, b) => b.unrealized_pnl - a.unrealized_pnl)
  ), [positions])

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
          <>
            <div style={{ display: 'flex', gap: 8, padding: '8px 10px 0', flexWrap: 'wrap' }}>
              {pieData.length > 0 && (
                <div style={{ flex: '1 1 220px', height: 160 }}>
                  <div className="dim" style={{ fontSize: 9, marginBottom: 2 }}>ALLOCATION BY MARKET VALUE</div>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                           innerRadius={30} outerRadius={55} paddingAngle={2}>
                        {pieData.map((p, i) => <Cell key={p.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                               borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}
                               formatter={(v) => `$${v.toLocaleString()}`} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
              {pnlBars.length > 0 && (
                <div style={{ flex: '1 1 260px', height: 160 }}>
                  <div className="dim" style={{ fontSize: 9, marginBottom: 2 }}>UNREALIZED P&L BY POSITION</div>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={pnlBars} layout="vertical" margin={{ top: 2, right: 16, left: 0, bottom: 2 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                      <XAxis type="number" tick={{ fill: 'var(--text-dim)', fontSize: 8 }}
                             axisLine={{ stroke: 'var(--border-bright)' }} />
                      <YAxis type="category" dataKey="symbol" width={44}
                             tick={{ fill: 'var(--text-dim)', fontSize: 9 }} axisLine={{ stroke: 'var(--border-bright)' }} />
                      <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                               borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}
                               formatter={(v) => `$${v.toLocaleString()}`} />
                      <Bar dataKey="unrealized_pnl">
                        {pnlBars.map(p => (
                          <Cell key={p.symbol} fill={p.unrealized_pnl >= 0 ? 'var(--green)' : 'var(--red)'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
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
          </>
        )}
      </div>
    </div>
  )
}
