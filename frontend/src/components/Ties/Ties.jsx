import React, { useState, useEffect } from 'react'
import { useCompanyTies } from '../../hooks/useMarketData'
import { useSymbol } from '../../hooks/useSymbol'

const SECTOR_COLOR = {
  'Information Technology': '#6BA3D4',
  'Consumer Discretionary': '#E0A55C',
  'Financials': '#3FB68B',
  'Health Care': '#C77DFF',
  'Energy': '#E0556B',
  'Industrials': '#C9A84C',
  'Communication Services': '#5FC9D4',
  'Consumer Staples': '#9BC47D',
  'Materials': '#D49B6B',
  'Real Estate': '#B98BD4',
  'Utilities': '#7D9BC4',
}
const color = (s) => SECTOR_COLOR[s] || '#5E789A'

function TieCard({ tie, side }) {
  return (
    <div style={{
      background: 'var(--bg-raised)',
      border: `1px solid var(--border)`,
      borderLeft: `3px solid ${color(tie.sector)}`,
      borderRadius: 4, padding: '5px 8px', marginBottom: 5,
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12, color: 'var(--text)' }}>
          {tie.symbol}
        </div>
        <div className="dim" style={{ fontSize: 9, whiteSpace: 'nowrap', overflow: 'hidden',
                                       textOverflow: 'ellipsis', maxWidth: 150 }}>
          {tie.name}
        </div>
        <div className="dim" style={{ fontSize: 8 }}>{tie.sub}</div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 8 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11,
                      color: tie.corr >= 0 ? 'var(--green)' : 'var(--red)' }}>
          {tie.corr >= 0 ? '+' : ''}{(tie.corr * 100).toFixed(0)}%
        </div>
        <div className="dim" style={{ fontSize: 8 }}>corr</div>
      </div>
    </div>
  )
}

export default function Ties() {
  const { symbol: globalSym, setSymbol: setGlobalSym } = useSymbol()
  const [input, setInput] = useState(globalSym)
  const [symbol, setSymbol] = useState(globalSym)
  useEffect(() => { setInput(globalSym); setSymbol(globalSym) }, [globalSym])
  const { data, loading } = useCompanyTies(symbol)

  const go = () => { setSymbol(input.trim().toUpperCase()); setGlobalSym(input.trim().toUpperCase()) }

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Company Relationships</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input className="input" style={{ width: 90, fontFamily: 'var(--font-mono)' }}
            value={input} onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && go()}
            placeholder="Ticker" />
          <button className="btn active" onClick={go}>Map ties</button>
        </div>
      </div>
      <div className="panel-body" style={{ overflow: 'auto' }}>
        {loading && <div style={{ padding: 16, color: 'var(--text-dim)' }}>Finding related companies…</div>}
        {data?.error && (
          <div style={{ padding: 16, color: 'var(--red)' }}>
            {data.error}
            {data.in_universe === false &&
              <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
                This map covers a {data.universe_size}-name universe (S&P 500 + major names).
              </div>}
          </div>
        )}
        {data && !data.error && (
          <div style={{ padding: 12 }}>
            {/* Center company */}
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <div style={{ display: 'inline-block', background: 'var(--bg-panel)',
                            border: `2px solid ${color(data.center_sector)}`,
                            borderRadius: 6, padding: '10px 20px' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 18,
                              color: 'var(--gold)' }}>{data.center}</div>
                <div style={{ fontSize: 12, color: 'var(--text)' }}>{data.center_name}</div>
                <div className="dim" style={{ fontSize: 10 }}>{data.center_sub}</div>
              </div>
            </div>

            {/* Two columns: industry peers | cross-industry correlates */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)',
                              marginBottom: 8, letterSpacing: '0.05em' }}>
                  INDUSTRY PEERS
                  <span className="dim" style={{ fontWeight: 400, marginLeft: 6 }}>
                    ({data.peers?.length || 0}) same sub-industry
                  </span>
                </div>
                {data.peers?.length
                  ? data.peers.map(t => <TieCard key={t.symbol} tie={t} side="peer" />)
                  : <div className="dim" style={{ fontSize: 11 }}>No same-industry names in universe.</div>}
              </div>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)',
                              marginBottom: 8, letterSpacing: '0.05em' }}>
                  CROSS-INDUSTRY TIES
                  <span className="dim" style={{ fontWeight: 400, marginLeft: 6 }}>
                    ({data.correlates?.length || 0}) statistically correlated
                  </span>
                </div>
                {data.correlates?.length
                  ? data.correlates.map(t => <TieCard key={t.symbol} tie={t} side="corr" />)
                  : <div className="dim" style={{ fontSize: 11 }}>No strong cross-industry ties.</div>}
              </div>
            </div>

            <div className="dim" style={{ fontSize: 9, marginTop: 14, lineHeight: 1.5 }}>
              Ties blend price correlation (60%) and GICS sub-industry/sector affinity (40%),
              ranked across a {data.universe_size}-name universe. These are statistical and
              classification ties — not disclosed supplier/customer relationships.
              {data.computed_at && ` Matrix computed ${new Date(data.computed_at + 'Z').toLocaleString()}.`}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
