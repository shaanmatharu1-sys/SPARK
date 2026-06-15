import React, { useState } from 'react'
import { useEarnings, useFilings, useSocial } from '../../hooks/useMarketData'

function Earnings({ symbol }) {
  const { data, loading } = useEarnings(symbol)
  if (loading) return <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading earnings…</div>
  if (data?.error || !data?.quarters?.length)
    return <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>No earnings data available.</div>
  return (
    <table className="bbg-table">
      <thead><tr><th>PERIOD</th><th>REVENUE</th><th>NET INC</th><th>EPS</th></tr></thead>
      <tbody>
        {data.quarters.map((q, i) => (
          <tr key={i}>
            <td style={{ color: 'var(--gold)' }}>{q.fiscal_period} {q.fiscal_year}</td>
            <td>{q.revenue ? '$'+(q.revenue/1e9).toFixed(2)+'B' : '—'}</td>
            <td>{q.net_income ? '$'+(q.net_income/1e9).toFixed(2)+'B' : '—'}</td>
            <td>{q.eps_diluted != null ? '$'+q.eps_diluted.toFixed(2) : '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Filings({ symbol }) {
  const { data, loading } = useFilings(symbol)
  if (loading) return <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading filings…</div>
  if (data?.error || !data?.filings?.length)
    return <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>No filings found.</div>
  return (
    <div>
      {data.filings.slice(0, 15).map((f, i) => (
        <div key={i} style={{ padding: '6px 12px', borderBottom: '1px solid var(--border)',
                              display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <a href={f.url} target="_blank" rel="noreferrer"
               style={{ color: 'var(--steel-bright)', textDecoration: 'none', fontSize: 11, fontWeight: 600 }}>
              {f.form}
            </a>
            <span className="dim" style={{ fontSize: 10, marginLeft: 8 }}>{f.description}</span>
          </div>
          <span className="dim" style={{ fontSize: 10 }}>{f.filing_date}</span>
        </div>
      ))}
    </div>
  )
}

function Social({ symbol }) {
  const { data, loading } = useSocial(symbol)
  if (loading) return <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading sentiment…</div>
  if (!data?.available)
    return <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>
      Social sentiment unavailable. {data?.note}
    </div>
  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1, textAlign: 'center', padding: 8, background: 'var(--bg-base)', borderRadius: 5 }}>
          <div className="dim" style={{ fontSize: 9 }}>NET</div>
          <div style={{ fontSize: 14, fontWeight: 700,
            color: data.net_sentiment === 'bullish' ? 'var(--green)' :
                   data.net_sentiment === 'bearish' ? 'var(--red)' : 'var(--text-secondary)' }}>
            {data.net_sentiment?.toUpperCase()}
          </div>
        </div>
        <div style={{ flex: 1, textAlign: 'center', padding: 8, background: 'var(--bg-base)', borderRadius: 5 }}>
          <div className="dim" style={{ fontSize: 9 }}>BULLISH</div>
          <div className="green" style={{ fontSize: 14, fontWeight: 700 }}>{data.bullish_pct ?? '—'}%</div>
        </div>
        <div style={{ flex: 1, textAlign: 'center', padding: 8, background: 'var(--bg-base)', borderRadius: 5 }}>
          <div className="dim" style={{ fontSize: 9 }}>MESSAGES</div>
          <div style={{ fontSize: 14, fontWeight: 700 }}>{data.message_count}</div>
        </div>
      </div>
      <div className="dim" style={{ fontSize: 9, marginBottom: 8, fontStyle: 'italic' }}>{data.note}</div>
      {data.recent?.slice(0, 8).map((m, i) => (
        <div key={i} style={{ padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 10 }}>
          <span style={{ color: m.sentiment === 'Bullish' ? 'var(--green)' :
                                m.sentiment === 'Bearish' ? 'var(--red)' : 'var(--text-dim)',
                         fontWeight: 600, marginRight: 6 }}>
            {m.sentiment || '·'}
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>{m.body}</span>
        </div>
      ))}
    </div>
  )
}

export default function CompanyDetail() {
  const [symbol, setSymbol] = useState('AAPL')
  const [input, setInput] = useState('AAPL')
  const [tab, setTab] = useState('filings')

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Company Detail</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {['filings', 'earnings', 'social'].map(t => (
            <button key={t} className={`btn ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}>{t.toUpperCase()}</button>
          ))}
          <input className="input" value={input} style={{ width: 64 }}
            onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && setSymbol(input)} />
        </div>
      </div>
      <div className="panel-body">
        {tab === 'filings'  && <Filings symbol={symbol} />}
        {tab === 'earnings' && <Earnings symbol={symbol} />}
        {tab === 'social'   && <Social symbol={symbol} />}
      </div>
    </div>
  )
}
