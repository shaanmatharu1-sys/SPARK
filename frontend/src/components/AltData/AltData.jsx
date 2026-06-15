import React from 'react'
import { useAltData } from '../../hooks/useMarketData'

const chgColor = (p) => p == null ? 'var(--text-dim)' : p > 0 ? 'var(--green)' : p < 0 ? 'var(--red)' : 'var(--text)'

// Tiny inline sparkline
function Spark({ data, w = 80, h = 22, color = '#6BA3D4' }) {
  if (!data || data.length < 2) return null
  const min = Math.min(...data), max = Math.max(...data), rng = max - min || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / rng) * h}`).join(' ')
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.2" />
    </svg>
  )
}

function TrendCard({ s }) {
  const vals = s.points?.map(p => p.value) || []
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
      <div>
        <div style={{ fontSize: 12, color: 'var(--text)' }}>{s.keyword}</div>
        <div className="dim" style={{ fontSize: 9 }}>search interest (0-100)</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Spark data={vals} color={s.change_7 >= 0 ? '#3FB68B' : '#E0556B'} />
        <div style={{ textAlign: 'right', minWidth: 44 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text)' }}>{s.latest}</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: chgColor(s.change_7) }}>
            {s.change_7 >= 0 ? '+' : ''}{s.change_7} (7d)
          </div>
        </div>
      </div>
    </div>
  )
}

function CommodityRow({ c }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ minWidth: 0 }}>
        <span style={{ fontSize: 12, color: 'var(--text)' }}>{c.name}</span>
        <span className="dim" style={{ fontSize: 9, marginLeft: 6 }}>{c.group}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Spark data={c.spark} color={c.change_1mo_pct >= 0 ? '#3FB68B' : '#E0556B'} />
        <div style={{ textAlign: 'right', minWidth: 70 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{c.value} <span className="dim" style={{ fontSize: 9 }}>{c.unit}</span></div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: chgColor(c.change_1mo_pct) }}>
            {c.change_1mo_pct >= 0 ? '+' : ''}{c.change_1mo_pct}% 1mo
          </div>
        </div>
      </div>
    </div>
  )
}

function SocialRow({ s }) {
  const sentColor = s.sentiment == null ? 'var(--text-dim)'
    : s.sentiment > 0.1 ? 'var(--green)' : s.sentiment < -0.1 ? 'var(--red)' : 'var(--text)'
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text)' }}>{s.symbol}</span>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
        <span className="dim" style={{ fontSize: 11 }}>{s.volume} msgs</span>
        <span style={{ fontSize: 11, color: 'var(--green)' }}>{s.bullish} bull</span>
        <span style={{ fontSize: 11, color: 'var(--red)' }}>{s.bearish} bear</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: sentColor, minWidth: 40, textAlign: 'right' }}>
          {s.sentiment == null ? '—' : (s.sentiment > 0 ? '+' : '') + s.sentiment}
        </span>
      </div>
    </div>
  )
}

export default function AltData() {
  const { data, loading } = useAltData()
  const trends = data?.trends
  const commodities = data?.commodities
  const social = data?.social

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr',
                  gap: 6, height: '100%', minHeight: 0 }}>
      {/* Google Trends */}
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">Search Interest (Google Trends)</span></div>
        <div className="panel-body" style={{ padding: '4px 12px' }}>
          {loading && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}
          {trends && trends.available === false &&
            <div className="dim" style={{ fontSize: 11, padding: 8 }}>
              Trends unavailable (Google rate-limited). Refreshes periodically.
            </div>}
          {trends?.series?.map(s => <TrendCard key={s.keyword} s={s} />)}
        </div>
      </div>

      {/* Commodities */}
      <div className="panel" style={{ minHeight: 0, gridRow: '1 / 3' }}>
        <div className="panel-header"><span className="title">Commodities & Shipping</span></div>
        <div className="panel-body" style={{ padding: '4px 12px' }}>
          {loading && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}
          {commodities?.commodities?.map(c => <CommodityRow key={c.id} c={c} />)}
          {commodities?.shipping?.length > 0 && (
            <>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--gold-bright)', margin: '10px 0 4px' }}>
                SUPPLY-CHAIN STRESS
              </div>
              {commodities.shipping.map(c => <CommodityRow key={c.id} c={c} />)}
            </>
          )}
        </div>
      </div>

      {/* Social volume */}
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">Social Volume & Sentiment</span></div>
        <div className="panel-body" style={{ padding: '4px 12px' }}>
          {loading && <div className="dim" style={{ fontSize: 11 }}>Loading…</div>}
          {social && social.available === false &&
            <div className="dim" style={{ fontSize: 11, padding: 8 }}>Social feed unavailable.</div>}
          {social?.social?.map(s => <SocialRow key={s.symbol} s={s} />)}
          <div className="dim" style={{ fontSize: 9, marginTop: 8 }}>
            StockTwits message volume + bull/bear sentiment. Score = (bull − bear) / total.
          </div>
        </div>
      </div>
    </div>
  )
}
