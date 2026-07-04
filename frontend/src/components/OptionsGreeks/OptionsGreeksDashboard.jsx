import React, { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useOptionPositionsGreeks, optionPositionsApi } from '../../hooks/useMarketData'

const EMPTY = { symbol: '', strike: 100, expiration: '', contract_type: 'call', qty: 1, side: 'long', cost_basis: 0 }

function StatTile({ label, value, valueColor }) {
  return (
    <div style={{ flex: 1, minWidth: 100, textAlign: 'center', padding: 8, background: 'var(--bg-base)', borderRadius: 5 }}>
      <div className="dim" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: valueColor || 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}

export default function OptionsGreeksDashboard() {
  const { data, loading, refresh } = useOptionPositionsGreeks()
  const [form, setForm] = useState({ ...EMPTY })
  const [adding, setAdding] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!form.symbol || !form.expiration) return
    setAdding(true)
    await optionPositionsApi.add({
      ...form,
      symbol: form.symbol.toUpperCase(),
      strike: parseFloat(form.strike),
      qty: parseInt(form.qty, 10),
      cost_basis: parseFloat(form.cost_basis) || 0,
    })
    setForm({ ...EMPTY })
    setAdding(false)
    refresh()
  }

  const remove = async (id) => {
    await optionPositionsApi.remove(id)
    refresh()
  }

  const total = data?.total || { delta: 0, gamma: 0, theta: 0, vega: 0 }
  const chartData = (data?.positions || []).map(p => ({
    name: `${p.symbol} ${p.strike}${p.contract_type[0].toUpperCase()}`,
    delta: p.contribution?.delta ?? 0,
  }))

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Options Greeks Dashboard</span>
      </div>
      <div className="panel-body" style={{ padding: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
          <StatTile label="DELTA" value={total.delta.toFixed(2)}
            valueColor={total.delta >= 0 ? 'var(--green)' : 'var(--red)'} />
          <StatTile label="GAMMA" value={total.gamma.toFixed(4)} />
          <StatTile label="THETA" value={total.theta.toFixed(2)}
            valueColor={total.theta >= 0 ? 'var(--green)' : 'var(--red)'} />
          <StatTile label="VEGA" value={total.vega.toFixed(2)} />
        </div>

        <form onSubmit={submit} style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
          <input className="input" placeholder="SYM" style={{ width: 55, fontSize: 11 }}
            value={form.symbol} onChange={e => setForm(f => ({ ...f, symbol: e.target.value.toUpperCase() }))} />
          <select className="input" style={{ fontSize: 11 }} value={form.contract_type}
            onChange={e => setForm(f => ({ ...f, contract_type: e.target.value }))}>
            <option value="call">Call</option>
            <option value="put">Put</option>
          </select>
          <input className="input" type="number" placeholder="Strike" style={{ width: 65, fontSize: 11 }}
            value={form.strike} onChange={e => setForm(f => ({ ...f, strike: e.target.value }))} />
          <input className="input" type="date" style={{ fontSize: 11 }}
            value={form.expiration} onChange={e => setForm(f => ({ ...f, expiration: e.target.value }))} />
          <select className="input" style={{ fontSize: 11 }} value={form.side}
            onChange={e => setForm(f => ({ ...f, side: e.target.value }))}>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
          <input className="input" type="number" placeholder="Qty" style={{ width: 55, fontSize: 11 }}
            value={form.qty} onChange={e => setForm(f => ({ ...f, qty: e.target.value }))} />
          <input className="input" type="number" placeholder="Cost" style={{ width: 55, fontSize: 11 }}
            value={form.cost_basis} onChange={e => setForm(f => ({ ...f, cost_basis: e.target.value }))} />
          <button className="btn active" type="submit" disabled={adding} style={{ fontSize: 11 }}>+ Add</button>
        </form>

        {loading && !data ? (
          <div className="dim">Loading positions…</div>
        ) : !data?.positions?.length ? (
          <div className="dim" style={{ fontSize: 11 }}>No option positions tracked yet — add one above.</div>
        ) : (
          <>
            <table className="bbg-table" style={{ marginBottom: 12 }}>
              <thead>
                <tr>
                  <th>SYMBOL</th><th>STRIKE</th><th>TYPE</th><th>EXP</th><th>QTY</th>
                  <th>DELTA</th><th>GAMMA</th><th>THETA</th><th>VEGA</th><th></th>
                </tr>
              </thead>
              <tbody>
                {data.positions.map(p => (
                  <tr key={p.id}>
                    <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{p.symbol}</td>
                    <td>{p.strike}</td>
                    <td className="dim">{p.contract_type}</td>
                    <td className="dim">{p.expiration}</td>
                    <td>{p.qty}</td>
                    {p.contribution ? (
                      <>
                        <td className={p.contribution.delta >= 0 ? 'green' : 'red'}>{p.contribution.delta}</td>
                        <td>{p.contribution.gamma}</td>
                        <td className={p.contribution.theta >= 0 ? 'green' : 'red'}>{p.contribution.theta}</td>
                        <td>{p.contribution.vega}</td>
                      </>
                    ) : (
                      <td colSpan={4} className="dim" style={{ textAlign: 'center' }}>contract not found in snapshot</td>
                    )}
                    <td style={{ cursor: 'pointer', color: 'var(--text-dim)' }} onClick={() => remove(p.id)}>✕</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="label" style={{ marginBottom: 6 }}>Delta contribution by position</div>
            <div style={{ height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-dim)', fontSize: 9 }} />
                  <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 10 }} width={40} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                           borderRadius: 6, fontSize: 11 }} />
                  <Bar dataKey="delta">
                    {chartData.map((d, i) => (
                      <Cell key={i} fill={d.delta >= 0 ? '#3FB68B' : '#E0556B'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
