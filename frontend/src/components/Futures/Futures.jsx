import React, { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, Legend,
} from 'recharts'
import { useFuturesAll, useFuturesBars, useFuturesCOT } from '../../hooks/useMarketData'

const chgColor = (p) => p == null ? 'var(--text-dim)' : p > 0 ? 'var(--green)' : p < 0 ? 'var(--red)' : 'var(--text)'
const fmtPct = (p) => p == null ? '—' : `${p > 0 ? '+' : ''}${p.toFixed(2)}%`

const GROUP_ORDER = ['Equity Index', 'Rates', 'Energy', 'Metals', 'Agriculture', 'Currency']

function RankedBar({ quotes, onPick, selected }) {
  const ranked = useMemo(() => (
    quotes.filter(q => q.change_pct != null).slice().sort((a, b) => b.change_pct - a.change_pct)
  ), [quotes])
  if (!ranked.length) return null
  return (
    <div style={{ height: Math.min(420, ranked.length * 26), marginBottom: 8 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={ranked} layout="vertical" margin={{ top: 2, right: 24, left: 0, bottom: 2 }}
                  onClick={(s) => s?.activePayload?.[0] && onPick(s.activePayload[0].payload.symbol)}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
          <XAxis type="number" tick={{ fill: 'var(--text-dim)', fontSize: 8 }}
                 axisLine={{ stroke: 'var(--border-bright)' }} tickFormatter={v => `${v}%`} />
          <YAxis type="category" dataKey="name" width={110}
                 tick={{ fill: 'var(--text-dim)', fontSize: 9 }} axisLine={{ stroke: 'var(--border-bright)' }} />
          <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                   borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}
                   formatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(2)}%`}
                   labelFormatter={(_, p) => `${p?.[0]?.payload?.symbol} (${p?.[0]?.payload?.group})`} />
          <Bar dataKey="change_pct" cursor="pointer">
            {ranked.map(q => (
              <Cell key={q.symbol}
                    fill={q.symbol === selected ? 'var(--gold-bright)'
                         : q.change_pct >= 0 ? 'var(--green)' : 'var(--red)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function ContractDetail({ symbol, name }) {
  const { data: barsData, loading: barsLoading } = useFuturesBars(symbol, 90)
  const { data: cot, loading: cotLoading } = useFuturesCOT(symbol, 26)

  const chartData = useMemo(() => (barsData?.bars || []).map(b => ({
    t: new Date(b.t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    c: b.c,
  })), [barsData])

  const cotData = useMemo(() => (cot?.history || []).map(h => ({
    date: h.date?.slice(5),
    'Non-Commercial': h.noncomm_net,
    'Commercial': h.comm_net,
    'Non-Reportable': h.nonrept_net,
  })), [cot])

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)', marginBottom: 4 }}>
        {symbol} — {name} — 90D PRICE
      </div>
      <div style={{ height: 130 }}>
        {barsLoading ? <div className="dim" style={{ fontSize: 11 }}>Loading…</div> : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="t" tick={{ fill: 'var(--text-dim)', fontSize: 7 }}
                     axisLine={{ stroke: 'var(--border-bright)' }} interval={Math.ceil(chartData.length / 6)} />
              <YAxis domain={['auto', 'auto']} tick={{ fill: 'var(--text-dim)', fontSize: 8 }}
                     axisLine={{ stroke: 'var(--border-bright)' }} width={48} />
              <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                       borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }} />
              <Line type="monotone" dataKey="c" stroke="var(--steel-bright)" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)', margin: '10px 0 4px' }}>
        CFTC POSITIONING (NET, BY TRADER TYPE)
      </div>
      <div style={{ height: 140 }}>
        {cotLoading ? <div className="dim" style={{ fontSize: 11 }}>Loading…</div>
         : !cot?.available ? <div className="dim" style={{ fontSize: 11 }}>{cot?.reason || 'COT data unavailable for this contract.'}</div>
         : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={cotData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fill: 'var(--text-dim)', fontSize: 7 }}
                     axisLine={{ stroke: 'var(--border-bright)' }} interval={Math.ceil(cotData.length / 6)} />
              <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 8 }} axisLine={{ stroke: 'var(--border-bright)' }} width={44} />
              <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
                       borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }} />
              <Legend wrapperStyle={{ fontSize: 8 }} />
              <Line type="monotone" dataKey="Non-Commercial" stroke="var(--gold-bright)" strokeWidth={1.5} dot={false} />
              <Line type="monotone" dataKey="Commercial" stroke="var(--steel-bright)" strokeWidth={1.5} dot={false} />
              <Line type="monotone" dataKey="Non-Reportable" stroke="var(--text-dim)" strokeWidth={1} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      {cot?.available && (
        <div className="dim" style={{ fontSize: 9, marginTop: 4 }}>{cot.note}</div>
      )}
    </div>
  )
}

export default function Futures() {
  const { data, loading } = useFuturesAll()
  const [selected, setSelected] = useState(null) // { symbol, name }

  const quotes = data?.quotes || []
  const byGroup = useMemo(() => {
    const groups = {}
    for (const q of quotes) (groups[q.group] ||= []).push(q)
    return GROUP_ORDER.filter(g => groups[g]?.length).map(g => [g, groups[g]])
  }, [quotes])

  const pick = (symbol) => {
    const q = quotes.find(x => x.symbol === symbol)
    if (q) setSelected({ symbol: q.symbol, name: q.name })
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 6, height: '100%', minHeight: 0 }}>
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header">
          <span className="title">Futures — Ranked Performance</span>
          <span className="dim" style={{ fontSize: 9 }}>click to chart · delayed, free data</span>
        </div>
        <div className="panel-body" style={{ padding: '4px 12px', overflowY: 'auto' }}>
          {loading && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}
          {data && !data.available && (
            <div style={{ color: 'var(--red)', fontSize: 11, padding: 12 }}>
              {data.reason || 'Futures data unavailable'}
            </div>
          )}
          <RankedBar quotes={quotes} onPick={pick} selected={selected?.symbol} />
        </div>
      </div>

      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">Contract Detail</span></div>
        <div className="panel-body" style={{ padding: '8px 12px', overflowY: 'auto' }}>
          {selected ? (
            <ContractDetail symbol={selected.symbol} name={selected.name} />
          ) : (
            <div className="dim" style={{ fontSize: 11, padding: 12 }}>
              Click a contract on the left to see its price history and CFTC positioning trend.
            </div>
          )}

          {byGroup.map(([group, rows]) => (
            <div key={group} style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--gold-bright)', margin: '4px 0' }}>
                {group.toUpperCase()}
              </div>
              {rows.map(q => (
                <div key={q.symbol}
                  onClick={() => pick(q.symbol)}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '3px 6px', margin: '0 -6px', borderRadius: 3, cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    background: selected?.symbol === q.symbol ? 'var(--bg-raised)' : 'transparent',
                  }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11,
                                 color: selected?.symbol === q.symbol ? 'var(--gold-bright)' : 'var(--text)' }}>
                    {q.symbol} <span className="dim" style={{ fontSize: 9, marginLeft: 4 }}>{q.name}</span>
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: chgColor(q.change_pct) }}>
                    {q.price} &nbsp; {fmtPct(q.change_pct)}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
