import React, { useState } from 'react'
import {
  useEarnings, useFilings, useSocial,
  useTickerDetails, useShortInterest, useDividends, useSplits, useAnalystRatings,
  useRelativeValuation,
} from '../../hooks/useMarketData'

function fmtNum(n) {
  if (n == null) return '—'
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B'
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toLocaleString()
}

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

function StatTile({ label, value, valueColor }) {
  return (
    <div style={{ flex: 1, minWidth: 100, textAlign: 'center', padding: 8, background: 'var(--bg-base)', borderRadius: 5 }}>
      <div className="dim" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: valueColor || 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}

function Profile({ symbol }) {
  const { data, loading } = useTickerDetails(symbol)
  const { data: short, loading: shortLoading } = useShortInterest(symbol)

  if (loading) return <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading profile…</div>
  if (!data || Object.keys(data).length === 0)
    return <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>No profile data available.</div>

  return (
    <div style={{ padding: 12 }}>
      <div style={{ marginBottom: 10 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--gold)' }}>{data.name}</span>
        <span className="dim" style={{ fontSize: 10, marginLeft: 8 }}>
          {data.primary_exchange} · {data.sic_description}
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <StatTile label="MARKET CAP" value={data.market_cap ? '$' + fmtNum(data.market_cap) : '—'} />
        <StatTile label="EMPLOYEES" value={data.total_employees ? data.total_employees.toLocaleString() : '—'} />
        <StatTile label="SHARES OUT" value={fmtNum(data.share_class_shares_outstanding || data.weighted_shares_outstanding)} />
        {shortLoading ? (
          <StatTile label="SHORT INTEREST" value="…" />
        ) : short?.available ? (
          <StatTile
            label="SHORT INTEREST"
            value={fmtNum(short.short_interest)}
            valueColor={short.change_pct > 0 ? 'var(--red)' : short.change_pct < 0 ? 'var(--green)' : undefined}
          />
        ) : (
          <StatTile label="SHORT INTEREST" value="n/a" />
        )}
      </div>

      {short?.available && (
        <div className="dim" style={{ fontSize: 9, marginBottom: 12 }}>
          Short interest as of {short.settlement_date}: {fmtNum(short.short_interest)} shares
          ({short.change_pct > 0 ? '+' : ''}{short.change_pct}% vs prior settlement),
          {' '}{short.days_to_cover != null ? `${short.days_to_cover} days to cover` : ''}.
          Source: {short.source}.
        </div>
      )}
      {!shortLoading && short && !short.available && (
        <div className="dim" style={{ fontSize: 9, marginBottom: 12, fontStyle: 'italic' }}>
          Short interest unavailable: {short.reason}
        </div>
      )}

      {data.description && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {data.description}
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 10 }} className="dim">
        {data.address?.address1 && <div>{data.address.address1}, {data.address.city} {data.address.state}</div>}
        {data.homepage_url && (
          <a href={data.homepage_url} target="_blank" rel="noreferrer" style={{ color: 'var(--steel-bright)' }}>
            {data.homepage_url}
          </a>
        )}
        {data.list_date && <div>Listed: {data.list_date}</div>}
      </div>
    </div>
  )
}

function Dividends({ symbol }) {
  const { data: divs, loading: divLoading } = useDividends(symbol)
  const { data: splits, loading: splitLoading } = useSplits(symbol)

  if (divLoading) return <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading dividends…</div>

  return (
    <div>
      {!divs?.length ? (
        <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>No dividend history found.</div>
      ) : (
        <table className="bbg-table">
          <thead><tr><th>EX-DATE</th><th>PAY DATE</th><th>RECORD DATE</th><th>AMOUNT</th><th>FREQ</th><th>TYPE</th></tr></thead>
          <tbody>
            {divs.map((d, i) => (
              <tr key={i}>
                <td style={{ color: 'var(--gold)' }}>{d.ex_dividend_date}</td>
                <td>{d.pay_date || '—'}</td>
                <td>{d.record_date || '—'}</td>
                <td className="green">${d.cash_amount?.toFixed(4)}</td>
                <td>{d.frequency === 4 ? 'Quarterly' : d.frequency === 1 ? 'Annual' :
                     d.frequency === 12 ? 'Monthly' : d.frequency === 2 ? 'Semi-annual' : (d.frequency ?? '—')}</td>
                <td className="dim">{d.dividend_type || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ padding: '10px 12px 4px', borderTop: '1px solid var(--border)', marginTop: 8 }}>
        <span className="dim" style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.5 }}>STOCK SPLITS</span>
      </div>
      {splitLoading ? (
        <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>Loading splits…</div>
      ) : !splits?.length ? (
        <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>No split history found.</div>
      ) : (
        <table className="bbg-table">
          <thead><tr><th>EXECUTION DATE</th><th>RATIO</th></tr></thead>
          <tbody>
            {splits.map((s, i) => (
              <tr key={i}>
                <td style={{ color: 'var(--gold)' }}>{s.execution_date}</td>
                <td>{s.split_to}:{s.split_from}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function Ratings({ symbol }) {
  const { data, loading } = useAnalystRatings(symbol)
  if (loading) return <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading ratings…</div>
  if (!data?.available)
    return <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 11 }}>
      Analyst ratings unavailable. {data?.note || data?.reason}
    </div>

  const c = data.consensus || {}
  const pt = data.price_target || {}

  return (
    <div style={{ padding: 12 }}>
      <div className="dim" style={{ fontSize: 9, marginBottom: 6 }}>
        CONSENSUS {c.period ? `(${c.period})` : ''}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
        <StatTile label="STRONG BUY" value={c.strong_buy ?? 0} valueColor="var(--green)" />
        <StatTile label="BUY" value={c.buy ?? 0} valueColor="var(--green)" />
        <StatTile label="HOLD" value={c.hold ?? 0} valueColor="var(--gold)" />
        <StatTile label="SELL" value={c.sell ?? 0} valueColor="var(--red)" />
        <StatTile label="STRONG SELL" value={c.strong_sell ?? 0} valueColor="var(--red)" />
      </div>

      <div className="dim" style={{ fontSize: 9, marginBottom: 6 }}>PRICE TARGET</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
        <StatTile label="LOW" value={pt.low != null ? '$' + pt.low.toFixed(2) : '—'} />
        <StatTile label="MEAN" value={pt.mean != null ? '$' + pt.mean.toFixed(2) : '—'} valueColor="var(--gold)" />
        <StatTile label="MEDIAN" value={pt.median != null ? '$' + pt.median.toFixed(2) : '—'} />
        <StatTile label="HIGH" value={pt.high != null ? '$' + pt.high.toFixed(2) : '—'} />
      </div>

      {!!data.history?.length && (
        <table className="bbg-table">
          <thead><tr><th>PERIOD</th><th>S.BUY</th><th>BUY</th><th>HOLD</th><th>SELL</th><th>S.SELL</th></tr></thead>
          <tbody>
            {data.history.map((h, i) => (
              <tr key={i}>
                <td style={{ color: 'var(--gold)' }}>{h.period}</td>
                <td className="green">{h.strong_buy}</td>
                <td className="green">{h.buy}</td>
                <td>{h.hold}</td>
                <td className="red">{h.sell}</td>
                <td className="red">{h.strong_sell}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="dim" style={{ fontSize: 9, marginTop: 8, fontStyle: 'italic' }}>Source: {data.source}</div>
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

function RelativeValuation({ symbol }) {
  const [peers, setPeers] = useState('')
  const symbols = [symbol, ...peers.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)].slice(0, 4)
  const { data, loading } = useRelativeValuation(symbols)

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 12 }}>
        <span className="dim" style={{ fontSize: 10 }}>COMPARE {symbol} VS</span>
        <input className="input" style={{ width: 160, fontFamily: 'var(--font-mono)' }}
          placeholder="e.g. MSFT, GOOGL, AMZN" value={peers}
          onChange={e => setPeers(e.target.value.toUpperCase())} />
      </div>
      {loading && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}
      {data?.rows?.length > 0 && (
        <table className="bbg-table">
          <thead><tr><th>SYMBOL</th><th>NAME</th><th>PRICE</th><th>TTM EPS</th><th>P/E</th><th>MKT CAP</th><th>SECTOR</th></tr></thead>
          <tbody>
            {data.rows.map(r => (
              <tr key={r.symbol}>
                <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{r.symbol}</td>
                <td className="dim">{r.name}</td>
                <td>{r.price != null ? `$${r.price.toFixed(2)}` : '—'}</td>
                <td>{r.ttm_eps != null ? `$${r.ttm_eps.toFixed(2)}` : '—'}</td>
                <td style={{ color: 'var(--gold-bright)', fontWeight: 600 }}>{r.pe_ratio ?? '—'}</td>
                <td>{fmtNum(r.market_cap)}</td>
                <td className="dim" style={{ fontSize: 10 }}>{r.sector}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function CompanyDetail() {
  const [symbol, setSymbol] = useState('AAPL')
  const [input, setInput] = useState('AAPL')
  const [tab, setTab] = useState('profile')

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Company Detail</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {['profile', 'filings', 'earnings', 'dividends', 'ratings', 'social', 'rv'].map(t => (
            <button key={t} className={`btn ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}>{t.toUpperCase()}</button>
          ))}
          <input className="input" value={input} style={{ width: 64 }}
            onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && setSymbol(input)} />
        </div>
      </div>
      <div className="panel-body">
        {tab === 'profile'   && <Profile symbol={symbol} />}
        {tab === 'filings'   && <Filings symbol={symbol} />}
        {tab === 'earnings'  && <Earnings symbol={symbol} />}
        {tab === 'dividends' && <Dividends symbol={symbol} />}
        {tab === 'ratings'   && <Ratings symbol={symbol} />}
        {tab === 'social'    && <Social symbol={symbol} />}
        {tab === 'rv'        && <RelativeValuation symbol={symbol} />}
      </div>
    </div>
  )
}
