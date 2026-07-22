import React, { useState } from 'react'
import { useCountryDirectory } from '../../hooks/useMarketData'

const chgColor = (p) => p == null ? 'var(--text-dim)' : p > 0 ? 'var(--green)' : p < 0 ? 'var(--red)' : 'var(--text)'
const fmtPct = (p) => p == null ? '—' : `${p > 0 ? '+' : ''}${p.toFixed(2)}%`

// CBQ — Country Directory: everything this app already knows about one
// country (index level, country ETF, ADRs, FX rate) in a single view,
// instead of spread across four asset-type panels.
export default function CountryDirectory() {
  const { data, loading } = useCountryDirectory()
  const countries = data?.countries || []
  const [selected, setSelected] = useState(null)
  const sel = countries.find(c => c.country === selected) || countries[0]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 6, height: '100%', minHeight: 0 }}>
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">Countries</span></div>
        <div className="panel-body">
          {loading && <div className="dim" style={{ padding: 12, fontSize: 11 }}>Loading…</div>}
          {countries.map(c => (
            <div key={c.country}
              onClick={() => setSelected(c.country)}
              style={{
                padding: '7px 12px', cursor: 'pointer', fontSize: 12,
                background: (sel?.country === c.country) ? 'var(--bg-raised)' : 'transparent',
                color: (sel?.country === c.country) ? 'var(--gold-bright)' : 'var(--text-secondary)',
                borderBottom: '1px solid var(--border)',
              }}>
              {c.country}
            </div>
          ))}
        </div>
      </div>

      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">{sel?.country || 'Select a country'}</span></div>
        <div className="panel-body" style={{ padding: 12 }}>
          {!sel && <div className="dim" style={{ fontSize: 11 }}>Pick a country from the list.</div>}
          {sel && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {sel.index && (
                <div>
                  <div className="label" style={{ marginBottom: 4 }}>Index</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--text-primary)' }}>{sel.index.name}</span>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>
                      {sel.index.level?.toLocaleString()}{' '}
                      <span style={{ color: chgColor(sel.index.change_pct) }}>{fmtPct(sel.index.change_pct)}</span>
                    </span>
                  </div>
                </div>
              )}
              {sel.etf && (
                <div>
                  <div className="label" style={{ marginBottom: 4 }}>Country ETF</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--gold)', fontWeight: 600 }}>{sel.etf.symbol}</span>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>
                      ${sel.etf.price?.toFixed(2)}{' '}
                      <span style={{ color: chgColor(sel.etf.change_pct) }}>{fmtPct(sel.etf.change_pct)}</span>
                    </span>
                  </div>
                </div>
              )}
              {sel.fx && (
                <div>
                  <div className="label" style={{ marginBottom: 4 }}>FX</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--text-primary)' }}>{sel.fx.pair}</span>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>
                      {sel.fx.rate}{' '}
                      <span style={{ color: chgColor(sel.fx.change_pct) }}>{fmtPct(sel.fx.change_pct)}</span>
                    </span>
                  </div>
                </div>
              )}
              {sel.adrs?.length > 0 && (
                <div>
                  <div className="label" style={{ marginBottom: 4 }}>ADRs</div>
                  <table className="bbg-table">
                    <thead><tr><th>SYMBOL</th><th>NAME</th><th>PRICE</th><th>CHG%</th></tr></thead>
                    <tbody>
                      {sel.adrs.map(a => (
                        <tr key={a.symbol}>
                          <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{a.symbol}</td>
                          <td className="dim">{a.name}</td>
                          <td>{a.price != null ? `$${a.price.toFixed(2)}` : '—'}</td>
                          <td style={{ color: chgColor(a.change_pct) }}>{fmtPct(a.change_pct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!sel.index && !sel.etf && !sel.fx && !sel.adrs?.length && (
                <div className="dim" style={{ fontSize: 11 }}>No data for this country yet.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
