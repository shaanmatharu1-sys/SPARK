import React, { useState, useEffect, useRef } from 'react'
import { useOptionsChainFull } from '../../hooks/useMarketData'
import { useSymbol } from '../../hooks/useSymbol'
import { heatBg } from '../../lib/colorScale'

function fmt(n, d = 2) { return n == null ? '—' : Number(n).toFixed(d) }
function fmtIV(n) { return n == null ? '—' : (n * 100).toFixed(1) + '%' }

function Side({ c, align }) {
  if (!c) return <td colSpan={5} className="dim" style={{ textAlign: 'center' }}>—</td>
  return (
    <>
      <td className="dim">{fmt(c.volume, 0)}</td>
      <td className="dim">{fmt(c.open_interest, 0)}</td>
      <td>{fmtIV(c.iv)}</td>
      <td className={c.delta >= 0 ? 'green' : 'red'} style={heatBg(c.delta, 1)}>{fmt(c.delta, 3)}</td>
      <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{fmt(c.last)}</td>
    </>
  )
}

export default function OptionsChain() {
  const { symbol, setSymbol } = useSymbol()
  const [input, setInput] = useState(symbol)
  useEffect(() => { setInput(symbol) }, [symbol])
  const [expiration, setExpiration] = useState(null)
  const [showAll, setShowAll] = useState(false)
  const bodyRef = useRef(null)
  const atmRowRef = useRef(null)

  const { data, loading } = useOptionsChainFull(symbol, expiration, showAll ? 0 : 20)

  // Reset the selected expiration when the symbol changes, so we don't hold
  // onto a stale date from the previous symbol's chain.
  useEffect(() => { setExpiration(null) }, [symbol])

  // Center the table on the at-the-money strike whenever a fresh chain loads,
  // instead of leaving the scroll position (and the reader) parked at the
  // lowest strike on the page.
  useEffect(() => {
    if (atmRowRef.current && bodyRef.current) {
      atmRowRef.current.scrollIntoView({ block: 'center' })
    }
  }, [data?.symbol, data?.expiration, data?.atm_strike])

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: 6 }}>
        <span className="title">Options Chain</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
          {data?.expirations?.map(exp => (
            <button key={exp} className={`btn ${(expiration || data.expiration) === exp ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px' }}
              onClick={() => setExpiration(exp)}>
              {exp}
            </button>
          ))}
          {data?.spot != null && (
            <span className="dim" style={{ fontSize: 9 }}>
              spot <span style={{ color: 'var(--gold-bright)' }}>{fmt(data.spot)}</span>
            </span>
          )}
          <button className={`btn ${showAll ? 'active' : ''}`} style={{ fontSize: 9, padding: '2px 7px' }}
            onClick={() => setShowAll(s => !s)}
            title={data?.total_strikes ? `${data.total_strikes} strikes available` : ''}>
            {showAll ? 'Near money only' : 'Show all strikes'}
          </button>
          <input className="input" style={{ width: 60 }} value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && setSymbol(input)} />
        </div>
      </div>
      <div className="panel-body" ref={bodyRef}>
        {loading && !data ? (
          <div style={{ padding: 16, color: 'var(--text-dim)' }}>Loading chain…</div>
        ) : !data?.rows?.length ? (
          <div style={{ padding: 16, color: 'var(--text-dim)' }}>No chain data available.</div>
        ) : (
          <table className="bbg-table">
            <thead>
              <tr>
                <th colSpan={5} style={{ textAlign: 'center', color: 'var(--green)' }}>CALLS</th>
                <th>STRIKE</th>
                <th colSpan={5} style={{ textAlign: 'center', color: 'var(--red)' }}>PUTS</th>
              </tr>
              <tr>
                <th>VOL</th><th>OI</th><th>IV</th><th>DELTA</th><th>LAST</th>
                <th style={{ color: 'var(--gold)' }}>—</th>
                <th>LAST</th><th>DELTA</th><th>IV</th><th>OI</th><th>VOL</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map(row => {
                const isAtm = row.strike === data.atm_strike
                return (
                  <tr key={row.strike} ref={isAtm ? atmRowRef : null}
                    className={isAtm ? 'atm-row' : ''}>
                    <Side c={row.call} align="left" />
                    <td style={{ color: 'var(--gold)', fontWeight: 700, textAlign: 'center' }}>{row.strike}</td>
                    <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{fmt(row.put?.last)}</td>
                    <td className={row.put?.delta >= 0 ? 'green' : 'red'} style={heatBg(row.put?.delta, 1)}>{fmt(row.put?.delta, 3)}</td>
                    <td>{fmtIV(row.put?.iv)}</td>
                    <td className="dim">{fmt(row.put?.open_interest, 0)}</td>
                    <td className="dim">{fmt(row.put?.volume, 0)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
