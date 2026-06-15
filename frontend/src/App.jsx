import React, { useState, useEffect } from 'react'
import MarketMonitor  from './components/MarketMonitor/MarketMonitor'
import PriceChart     from './components/Charts/PriceChart'
import MacroDashboard from './components/MacroDashboard/MacroDashboard'
import YieldCurve     from './components/YieldCurve/YieldCurve'
import FearGreed      from './components/FearGreed/FearGreed'
import SectorHeatmap  from './components/SectorHeatmap/SectorHeatmap'
import NewsFeed       from './components/NewsFeed/NewsFeed'
import UnusualActivity from './components/UnusualActivity/UnusualActivity'
import OptionsFlow    from './components/OptionsFlow/OptionsFlow'
import Backtest       from './components/Backtest/Backtest'
import Signals        from './components/Signals/Signals'
import Factors        from './components/Factors/Factors'
import VolSurface     from './components/VolSurface/VolSurface'
import Algo           from './components/Algo/Algo'

// ── Top bar clock ────────────────────────────────────────────────
function Clock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const isMarketOpen = () => {
    const h = time.getHours(), m = time.getMinutes()
    const mins = h * 60 + m
    const day  = time.getDay()
    return day >= 1 && day <= 5 && mins >= 570 && mins < 960
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <span style={{ color: isMarketOpen() ? 'var(--green)' : 'var(--red)', fontSize: 9 }}>
        ● {isMarketOpen() ? 'MARKET OPEN' : 'MARKET CLOSED'}
      </span>
      <span style={{ color: 'var(--text-secondary)', fontSize: 10 }}>
        {time.toLocaleTimeString('en-US', { hour12: false })}
      </span>
      <span className="dim" style={{ fontSize: 9 }}>
        {time.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
      </span>
    </div>
  )
}

// ── Tab definitions ──────────────────────────────────────────────
const TABS = [
  { id: 'overview',  label: 'OVERVIEW' },
  { id: 'options',   label: 'OPTIONS' },
  { id: 'quant',     label: 'QUANT' },
  { id: 'algo',      label: 'ALGO' },
  { id: 'macro',     label: 'MACRO' },
  { id: 'news',      label: 'NEWS' },
]

// ── Layout for each tab ──────────────────────────────────────────
function OverviewLayout({ chartSymbol }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 220px',
      gridTemplateRows:    '280px 1fr',
      gap: 4,
      height: '100%',
    }}>
      <div style={{ gridColumn: '1', gridRow: '1' }}>
        <PriceChart symbol={chartSymbol} />
      </div>
      <div style={{ gridColumn: '2', gridRow: '1' }}>
        <MarketMonitor />
      </div>
      <div style={{ gridColumn: '3', gridRow: '1 / 3' }}>
        <FearGreed />
      </div>
      <div style={{ gridColumn: '1', gridRow: '2' }}>
        <SectorHeatmap />
      </div>
      <div style={{ gridColumn: '2', gridRow: '2' }}>
        <YieldCurve />
      </div>
    </div>
  )
}

function OptionsLayout() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gridTemplateRows: '1fr 1fr',
      gap: 4,
      height: '100%',
    }}>
      <div style={{ gridColumn: '1', gridRow: '1 / 3' }}><OptionsFlow /></div>
      <div style={{ gridColumn: '2', gridRow: '1' }}><VolSurface /></div>
      <div style={{ gridColumn: '2', gridRow: '2' }}><UnusualActivity /></div>
    </div>
  )
}

function MacroLayout() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 4,
      height: '100%',
    }}>
      <MacroDashboard />
      <YieldCurve />
    </div>
  )
}

function NewsLayout() {
  return (
    <div style={{ height: '100%' }}>
      <NewsFeed />
    </div>
  )
}

function QuantLayout() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 280px',
      gridTemplateRows: '1fr 1fr',
      gap: 4,
      height: '100%',
    }}>
      <div style={{ gridColumn: '1', gridRow: '1' }}><Backtest /></div>
      <div style={{ gridColumn: '1', gridRow: '2' }}><Factors /></div>
      <div style={{ gridColumn: '2', gridRow: '1 / 3' }}><Signals /></div>
    </div>
  )
}

function AlgoLayout() {
  return (
    <div style={{ height: '100%', maxWidth: 900, margin: '0 auto' }}>
      <Algo />
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────
export default function App() {
  const [activeTab,    setActiveTab]    = useState('overview')
  const [chartSymbol,  setChartSymbol]  = useState('SPY')
  const [symbolInput,  setSymbolInput]  = useState('SPY')

  return (
    <div style={{
      display:       'flex',
      flexDirection: 'column',
      height:        '100vh',
      background:    'var(--bg-base)',
      overflow:      'hidden',
    }}>

      {/* ── Top Bar ─────────────────────────────────────────────── */}
      <div style={{
        background:    'var(--bg-header)',
        borderBottom:  '1px solid var(--border)',
        padding:       '6px 12px',
        display:       'flex',
        alignItems:    'center',
        justifyContent:'space-between',
        flexShrink:    0,
        height:        36,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          <span style={{
            fontFamily: 'var(--font-display)',
            color: 'var(--gold)', fontWeight: 600, fontSize: 18,
            letterSpacing: '0.02em', display: 'flex', alignItems: 'center', gap: 7,
          }}>
            <span style={{ fontSize: 14, opacity: 0.8 }}>◆</span>
            Meridian
          </span>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 3 }}>
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                style={{
                  background:   activeTab === t.id ? 'var(--bg-raised)' : 'transparent',
                  color:        activeTab === t.id ? 'var(--gold-bright)' : 'var(--text-secondary)',
                  border:       activeTab === t.id ? '1px solid var(--border-bright)' : '1px solid transparent',
                  borderRadius: 6,
                  padding:      '4px 13px',
                  fontSize:     11,
                  fontWeight:   activeTab === t.id ? 600 : 500,
                  cursor:       'pointer',
                  fontFamily:   'var(--font-ui)',
                  letterSpacing: '0.05em',
                  transition:   'all 0.15s ease',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Symbol lookup */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="dim" style={{ fontSize: 9 }}>CHART:</span>
          <input
            value={symbolInput}
            onChange={e => setSymbolInput(e.target.value.toUpperCase())}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                setChartSymbol(symbolInput)
                setActiveTab('overview')
              }
            }}
            style={{
              background:   '#0a0c10',
              border:       '1px solid var(--border-accent)',
              color:        'var(--yellow)',
              padding:      '3px 8px',
              fontSize:     11,
              borderRadius: 3,
              fontFamily:   'Courier New',
              width:        70,
              fontWeight:   'bold',
            }}
          />
        </div>

        <Clock />
      </div>

      {/* ── Main Content ─────────────────────────────────────────── */}
      <div style={{ flex: 1, padding: 4, overflow: 'hidden', minHeight: 0 }}>
        {activeTab === 'overview' && <OverviewLayout chartSymbol={chartSymbol} />}
        {activeTab === 'options'  && <OptionsLayout />}
        {activeTab === 'quant'    && <QuantLayout />}
        {activeTab === 'algo'     && <AlgoLayout />}
        {activeTab === 'macro'    && <MacroLayout />}
        {activeTab === 'news'     && <NewsLayout />}
      </div>

      {/* ── Status Bar ───────────────────────────────────────────── */}
      <div style={{
        background:   'var(--bg-header)',
        borderTop:    '1px solid var(--border)',
        padding:      '3px 12px',
        display:      'flex',
        alignItems:   'center',
        gap:          16,
        flexShrink:   0,
        height:       20,
      }}>
        <span className="dim" style={{ fontSize: 8 }}>
          DATA: Polygon.io · FRED · CNN F&G · NewsAPI
        </span>
        <span className="dim" style={{ fontSize: 8 }}>
          BACKEND: {import.meta.env.VITE_API_BASE ? 'cloud' : 'localhost:8000'}
        </span>
        <span style={{ color: 'var(--text-dim)', fontSize: 8 }}>
          Press ENTER in symbol box to load chart
        </span>
      </div>
    </div>
  )
}
