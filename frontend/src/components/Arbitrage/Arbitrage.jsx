import React from 'react'
import { useETFArb } from '../../hooks/useMarketData'
import Explain from '../common/Explain'

const sigColor = (s) => s === 'premium' ? 'var(--green)' : s === 'discount' ? 'var(--red)' : 'var(--text-dim)'

export default function Arbitrage() {
  const { data, loading } = useETFArb()
  const etfs = data?.etfs || []

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">ETF Arbitrage — Premium / Discount</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Explain title="ETF premium / discount">
            An ETF should trade close to the value of the stocks it holds (its basket).
            When it drifts above, it's at a <b>premium</b>; below, a <b>discount</b>.
            We compare the ETF's intraday return to its weighted basket's return — the
            gap is the spread.
            <br/><br/>
            In reality, big institutions ("authorized participants") arbitrage real gaps
            away within seconds, so persistent spreads here mostly reflect our using only
            the <i>top</i> holdings as an approximation. Treat it as a divergence monitor,
            not a free-money signal.
          </Explain>
          <span className="dim" style={{ fontSize: 9 }}>ETF return vs underlying basket</span>
        </div>
      </div>
      <div className="panel-body" style={{ padding: 12, overflow: 'auto' }}>
        {loading && <div className="dim" style={{ fontSize: 12 }}>Computing basket spreads…</div>}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {etfs.map(e => (
            <div key={e.etf} style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)',
                                       borderLeft: `3px solid ${sigColor(e.signal)}`, borderRadius: 5, padding: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>{e.etf}</span>
                  <span className="dim" style={{ fontSize: 9, marginLeft: 6 }}>{e.name}</span>
                </div>
                <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: sigColor(e.signal) }}>{e.signal}</span>
              </div>
              <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
                <div>
                  <div className="dim" style={{ fontSize: 9 }}>ETF</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{e.etf_change_pct >= 0 ? '+' : ''}{e.etf_change_pct}%</div>
                </div>
                <div>
                  <div className="dim" style={{ fontSize: 9 }}>BASKET</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{e.basket_change_pct >= 0 ? '+' : ''}{e.basket_change_pct}%</div>
                </div>
                <div>
                  <div className="dim" style={{ fontSize: 9 }}>SPREAD</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: sigColor(e.signal) }}>
                    {e.spread_pct >= 0 ? '+' : ''}{e.spread_pct}%
                  </div>
                </div>
              </div>
              <div className="dim" style={{ fontSize: 8, marginTop: 6 }}>
                basket = top {e.holdings?.length} holdings ({e.coverage_pct}% weight)
              </div>
            </div>
          ))}
        </div>
        <div className="dim" style={{ fontSize: 9, marginTop: 12, lineHeight: 1.6 }}>
          Spread = ETF intraday return minus its weighted-basket return. Positive (premium) means the ETF is
          outpacing its holdings; negative (discount) means it lags. Authorized participants arbitrage real
          creation-unit gaps away quickly — this uses TOP holdings as an approximate basket, so treat it as a
          divergence *monitor*, not a tradeable riskless arb. Not investment advice.
        </div>
      </div>
    </div>
  )
}
