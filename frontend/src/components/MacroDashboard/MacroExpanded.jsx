import React, { useState } from 'react'
import { useMacroExpanded } from '../../hooks/useMarketData'
import Explain from '../common/Explain'

const CATS = ['growth', 'inflation', 'labor', 'rates', 'money_credit', 'markets', 'housing', 'global']
const CAT_LABEL = {
  growth: 'Growth', inflation: 'Inflation', labor: 'Labor', rates: 'Rates',
  money_credit: 'Money & Credit', markets: 'Markets', housing: 'Housing', global: 'Global',
}

function Spark({ data, w = 64, h = 18, color = '#6BA3D4' }) {
  if (!data || data.length < 2) return null
  const min = Math.min(...data), max = Math.max(...data), rng = max - min || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / rng) * h}`).join(' ')
  return <svg width={w} height={h}><polyline points={pts} fill="none" stroke={color} strokeWidth="1.1" /></svg>
}

export default function MacroExpanded() {
  const [cat, setCat] = useState('growth')
  const { data, loading } = useMacroExpanded()
  const series = data?.[cat] || {}

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Macro Data</span>
        <Explain title="Macro indicators">
          ~66 economic series from the Federal Reserve (FRED) across 8 categories.
          Growth (GDP, industrial production), inflation (CPI, PCE, breakevens), labor
          (jobs, claims, JOLTS), rates (Treasuries, spreads), money &amp; credit, markets,
          housing, and global. Each shows the latest value, recent change, and a sparkline.
        </Explain>
      </div>
      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="tab-strip" style={{ display: 'flex', gap: 4, padding: 8, overflowX: 'auto', borderBottom: '1px solid var(--border)' }}>
          {CATS.map(c => (
            <button key={c} className={`btn ${cat === c ? 'active' : ''}`} style={{ fontSize: 10, whiteSpace: 'nowrap', flexShrink: 0 }}
              onClick={() => setCat(c)}>{CAT_LABEL[c]}</button>
          ))}
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '4px 12px' }}>
          {loading && <div className="dim" style={{ fontSize: 11, padding: 8 }}>Loading macro data…</div>}
          {Object.entries(series).map(([label, d]) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                       padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--text)' }}>{label}</div>
                <div className="dim" style={{ fontSize: 9 }}>{d.date}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Spark data={d.spark} color={(d.change || 0) >= 0 ? '#3FB68B' : '#E0556B'} />
                <div style={{ textAlign: 'right', minWidth: 70 }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>{d.value?.toLocaleString()}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10,
                                color: (d.change || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {(d.change || 0) >= 0 ? '+' : ''}{d.change}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
