import React, { useState } from 'react'
import { useInsider, useCongress, useFunds, use13F } from '../../hooks/useMarketData'

function InsiderView() {
  const [symbol, setSymbol] = useState('AAPL')
  const [input, setInput] = useState('AAPL')
  const { data, loading } = useInsider(symbol)
  return (
    <div>
      <div style={{ padding: '8px 12px', display: 'flex', gap: 6, alignItems: 'center' }}>
        <span className="dim" style={{ fontSize: 10 }}>TICKER:</span>
        <input className="input" style={{ width: 70 }} value={input}
          onChange={e => setInput(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && setSymbol(input)} />
      </div>
      {loading ? <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading insider filings…</div>
       : data?.trades?.length ? (
        <table className="bbg-table">
          <thead><tr><th>FORM</th><th>FILED</th><th>LINK</th></tr></thead>
          <tbody>
            {data.trades.map((t, i) => (
              <tr key={i}>
                <td style={{ color: 'var(--gold)' }}>Form {t.form}</td>
                <td>{t.filing_date}</td>
                <td><a href={t.url} target="_blank" rel="noreferrer"
                       style={{ color: 'var(--steel-bright)' }}>view</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>
            {data?.error ? `Error: ${data.error}` : 'No insider filings found.'}
          </div>}
      {data?.note && <div style={{ padding: '8px 12px', fontSize: 9, color: 'var(--text-dim)',
                                   fontStyle: 'italic' }}>{data.note}</div>}
    </div>
  )
}

function CongressView() {
  const [chamber, setChamber] = useState('house')
  const { data, loading } = useCongress(chamber)
  return (
    <div>
      <div style={{ padding: '8px 12px', display: 'flex', gap: 4 }}>
        {['house', 'senate'].map(c => (
          <button key={c} className={`btn ${chamber === c ? 'active' : ''}`}
            onClick={() => setChamber(c)}>{c.toUpperCase()}</button>
        ))}
      </div>
      {loading ? <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading congressional trades…</div>
       : data?.trades?.length ? (
        <table className="bbg-table">
          <thead><tr><th>MEMBER</th><th>TICKER</th><th>TYPE</th><th>AMOUNT</th><th>DATE</th></tr></thead>
          <tbody>
            {data.trades.slice(0, 40).map((t, i) => (
              <tr key={i}>
                <td style={{ fontSize: 10 }}>{t.representative}</td>
                <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{t.ticker || '—'}</td>
                <td style={{ color: /purchase|buy/i.test(t.type) ? 'var(--green)' : 'var(--red)' }}>
                  {t.type}
                </td>
                <td style={{ fontSize: 10 }}>{t.amount}</td>
                <td className="dim" style={{ fontSize: 10 }}>{t.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>
            {data?.note || 'No congressional trade data available.'}
          </div>}
    </div>
  )
}

function FundsView() {
  const { data: funds } = useFunds()
  const [fund, setFund] = useState('berkshire')
  const { data, loading } = use13F(fund)
  return (
    <div>
      <div style={{ padding: '8px 12px', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {funds && Object.entries(funds).map(([k, name]) => (
          <button key={k} className={`btn ${fund === k ? 'active' : ''}`}
            onClick={() => setFund(k)} style={{ fontSize: 9 }}>
            {name.split(' (')[0]}
          </button>
        ))}
      </div>
      {loading ? <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading 13F filings…</div>
       : data?.filings?.length ? (
        <>
          <div style={{ padding: '4px 12px', color: 'var(--gold)', fontWeight: 600 }}>{data.fund}</div>
          <table className="bbg-table">
            <thead><tr><th>FORM</th><th>FILED</th><th>HOLDINGS</th></tr></thead>
            <tbody>
              {data.filings.map((f, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--gold)' }}>{f.form}</td>
                  <td>{f.filing_date}</td>
                  <td><a href={f.url} target="_blank" rel="noreferrer"
                         style={{ color: 'var(--steel-bright)' }}>view</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>
            {data?.error ? `Error: ${data.error}` : 'No 13F filings found.'}
          </div>}
      {data?.note && <div style={{ padding: '8px 12px', fontSize: 9, color: 'var(--text-dim)',
                                   fontStyle: 'italic' }}>{data.note}</div>}
    </div>
  )
}

export default function Traders() {
  const [tab, setTab] = useState('insider')
  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Notable Traders</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button className={`btn ${tab === 'insider' ? 'active' : ''}`} onClick={() => setTab('insider')}>INSIDERS</button>
          <button className={`btn ${tab === 'congress' ? 'active' : ''}`} onClick={() => setTab('congress')}>CONGRESS</button>
          <button className={`btn ${tab === 'funds' ? 'active' : ''}`} onClick={() => setTab('funds')}>HEDGE FUNDS</button>
        </div>
      </div>
      <div className="panel-body">
        {tab === 'insider'  && <InsiderView />}
        {tab === 'congress' && <CongressView />}
        {tab === 'funds'    && <FundsView />}
      </div>
    </div>
  )
}
