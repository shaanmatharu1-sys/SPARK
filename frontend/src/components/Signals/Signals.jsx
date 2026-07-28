import React, { useState } from 'react'
import { useSignals } from '../../hooks/useMarketData'

function SignalBadge({ signal }) {
  const map = {
    STRONG_LONG:  { bg: 'var(--green-dim)', color: 'var(--green)', label: 'STRONG LONG' },
    LONG:         { bg: 'var(--green-dim)', color: 'var(--green)', label: 'LONG' },
    NEUTRAL:      { bg: 'var(--bg-raised)', color: 'var(--text-dim)', label: 'NEUTRAL' },
    SHORT:        { bg: 'var(--red-dim)', color: 'var(--red)', label: 'SHORT' },
    STRONG_SHORT: { bg: 'var(--red-dim)', color: 'var(--red)', label: 'STRONG SHORT' },
  }
  const s = map[signal] || map.NEUTRAL
  return (
    <span style={{ background: s.bg, color: s.color, padding: '3px 10px',
                   borderRadius: 3, fontSize: 11, fontWeight: 'bold', letterSpacing: '0.05em' }}>
      {s.label}
    </span>
  )
}

function Row({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0',
                  borderBottom: '1px solid var(--border)' }}>
      <span className="dim" style={{ fontSize: 10 }}>{label}</span>
      <span style={{ fontSize: 11, color: color || 'var(--text-primary)', fontWeight: 'bold' }}>{value}</span>
    </div>
  )
}

function RegimeTag({ regime }) {
  const colors = {
    'trending':       'var(--green)',
    'mean-reverting': 'var(--blue-bright)',
    'random-walk':    'var(--text-dim)',
    'unknown':        'var(--text-dim)',
  }
  return <span style={{ color: colors[regime] || 'var(--text-dim)' }}>{regime || '—'}</span>
}

export default function Signals() {
  const [symbol, setSymbol] = useState('SPY')
  const [input, setInput]   = useState('SPY')
  const { data, loading } = useSignals(symbol)

  const scoreColor = (s) => s == null ? 'var(--text-dim)'
    : s > 0.2 ? 'var(--green)' : s < -0.2 ? 'var(--red)' : 'var(--yellow)'

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Signals</span>
        <input value={input} onChange={e => setInput(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && setSymbol(input)}
          style={{ background: 'var(--bg-base)', border: '1px solid var(--border-accent)',
                   color: 'var(--yellow)', padding: '2px 6px', fontSize: 10,
                   borderRadius: 3, width: 64, fontFamily: 'var(--font-mono)', fontWeight: 'bold' }} />
      </div>
      <div className="panel-body" style={{ padding: 10 }}>
        {loading && <div style={{ color: 'var(--text-dim)' }}>Computing signals...</div>}
        {data?.error && <div style={{ color: 'var(--red)', fontSize: 11 }}>{data.error}</div>}
        {data && !data.error && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          marginBottom: 10 }}>
              <span style={{ color: 'var(--yellow)', fontSize: 16, fontWeight: 'bold' }}>
                {data.symbol}
              </span>
              <SignalBadge signal={data.signal} />
            </div>

            <div style={{ textAlign: 'center', margin: '8px 0 14px' }}>
              <div className="dim" style={{ fontSize: 9 }}>COMPOSITE SCORE</div>
              <div style={{ fontSize: 28, fontWeight: 'bold', color: scoreColor(data.composite_score) }}>
                {data.composite_score >= 0 ? '+' : ''}{data.composite_score?.toFixed(3)}
              </div>
            </div>

            <Row label="Last Price" value={`$${data.last_price?.toFixed(2)}`} />
            <Row label="Z-Score (20d)" value={data.zscore_20?.toFixed(2) ?? '—'}
                 color={data.zscore_20 == null ? null : Math.abs(data.zscore_20) > 2 ? 'var(--yellow)' : 'var(--text-primary)'} />
            <Row label="Regime" value={<RegimeTag regime={data.regime} />} />
            <Row label="Hurst Exponent" value={data.hurst?.toFixed(3) ?? '—'} />
            <Row label="OU Half-Life" value={data.ou_half_life ? `${data.ou_half_life} bars` : '—'} />
            <Row label="Realized Vol (20d)" value={data.realized_vol_20 ? `${(data.realized_vol_20*100).toFixed(1)}%` : '—'} />
            <Row label="Vol Regime" value={data.vol_regime}
                 color={data.vol_regime === 'expanding' ? 'var(--red)' : data.vol_regime === 'contracting' ? 'var(--green)' : 'var(--text-primary)'} />
            <Row label="Bollinger %B" value={data.bollinger_pct_b?.toFixed(2) ?? '—'} />

            {data.momentum && (
              <div style={{ marginTop: 10 }}>
                <div className="dim" style={{ fontSize: 9, marginBottom: 4 }}>
                  MOMENTUM (RISK-ADJ) — all three lookbacks feed the composite
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  {Object.entries(data.momentum).map(([lb, m]) => (
                    <div key={lb} style={{ flex: 1, textAlign: 'center', background: 'var(--bg-base)',
                                           borderRadius: 3, padding: '4px 0' }}>
                      <div className="dim" style={{ fontSize: 8 }}>{lb}</div>
                      <div style={{ fontSize: 11, fontWeight: 'bold',
                                    color: (m.risk_adj || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                        {m.risk_adj?.toFixed(2) ?? '—'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <div className="dim" style={{ fontSize: 9, marginBottom: 4 }}>TREND / VOLUME / CONFIRMATION</div>
              <Row label="ADX (14) — trend strength" value={data.adx_14?.toFixed(1) ?? '—'}
                   color={data.adx_14 > 25 ? 'var(--green)' : null} />
              <Row label="Volume vs 20d avg" value={data.volume_ratio_20d != null ? `${data.volume_ratio_20d}×` : '—'}
                   color={data.volume_ratio_20d > 1.5 ? 'var(--gold)' : data.volume_ratio_20d < 0.5 ? 'var(--text-dim)' : null} />
              <Row label="Weekly trend aligned" value={
                data.weekly_momentum_aligned == null ? '—' : data.weekly_momentum_aligned ? 'YES' : 'NO — dampened'
              } color={data.weekly_momentum_aligned === false ? 'var(--red)' : data.weekly_momentum_aligned ? 'var(--green)' : null} />
              <Row label="RSI divergence" value={data.rsi_divergence || 'none'}
                   color={data.rsi_divergence === 'bullish' ? 'var(--green)' : data.rsi_divergence === 'bearish' ? 'var(--red)' : null} />
              <Row label="ATR (14)" value={data.atr_14 != null ? `$${data.atr_14.toFixed(2)}` : '—'} />
              <Row label="Dist. to support / resistance" value={
                data.dist_to_support_atr != null
                  ? `${data.dist_to_support_atr} / ${data.dist_to_resistance_atr} ATR`
                  : '—'
              } />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
