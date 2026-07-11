import React, { useState, useEffect } from 'react'
import MarketMonitor  from './components/MarketMonitor/MarketMonitor'
import PriceChart     from './components/Charts/PriceChart'
import MacroDashboard from './components/MacroDashboard/MacroDashboard'
import MacroExpanded from './components/MacroDashboard/MacroExpanded'
import YieldCurve     from './components/YieldCurve/YieldCurve'
import FearGreed      from './components/FearGreed/FearGreed'
import SectorHeatmap  from './components/SectorHeatmap/SectorHeatmap'
import NewsFeed       from './components/NewsFeed/NewsFeed'
import UnusualActivity from './components/UnusualActivity/UnusualActivity'
import OptionsFlow    from './components/OptionsFlow/OptionsFlow'
import OptionsChain   from './components/OptionsChain/OptionsChain'
import OptionsGreeksDashboard from './components/OptionsGreeks/OptionsGreeksDashboard'
import Backtest       from './components/Backtest/Backtest'
import Signals        from './components/Signals/Signals'
import Factors        from './components/Factors/Factors'
import VolSurface     from './components/VolSurface/VolSurface'
import Algo           from './components/Algo/Algo'
import Pairs          from './components/Research/Pairs'
import Correlation    from './components/Research/Correlation'
import Movers         from './components/Markets/Movers'
import Crypto         from './components/Markets/Crypto'
import CompanyDetail  from './components/Markets/CompanyDetail'
import Traders        from './components/Traders/Traders'
import YieldCurvePanel from './components/YieldCurve/YieldCurvePanel'
import WatchlistManager from './components/Watchlist/WatchlistManager'
import SymbolSearch from './components/common/SymbolSearch'
import Credit          from './components/Credit/Credit'
import OptionsResearch from './components/OptionsResearch/OptionsResearch'
import Portfolio       from './components/Portfolio/Portfolio'
import Network         from './components/Network/Network'
import Ties            from './components/Ties/Ties'
import International    from './components/International/International'
import Futures          from './components/Futures/Futures'
import MultiChart        from './components/MultiChart/MultiChart'
import NotificationBell  from './components/Alerts/NotificationBell'
import Regime            from './components/Regime/Regime'
import AltData          from './components/AltData/AltData'
import BacktestTab      from './components/Backtest/BacktestTab'
import Arbitrage        from './components/Arbitrage/Arbitrage'
import { SymbolProvider, useSymbol } from './hooks/useSymbol'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { useWatchlist, useWebSocketHealth } from './hooks/useMarketData'
import LoginScreen from './components/Auth/LoginScreen'
import { THEMES } from './themes'
import Events           from './components/Events/Events'
import SupplyMap       from './components/SupplyMap/SupplyMap'
import PortWatch       from './components/SupplyMap/PortWatch'

// ── Top bar clock ────────────────────────────────────────────────
function UserMenu() {
  const { user, logout, setTheme } = useAuth()
  const [open, setOpen] = useState(false)
  if (!user) return null

  return (
    <div style={{ position: 'relative' }}>
      <button className="btn" style={{ fontSize: 11 }} onClick={() => setOpen(o => !o)}>
        {user.username}
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 30, right: 0, zIndex: 100, width: 200,
          background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
          borderRadius: 'var(--radius)', boxShadow: '0 8px 32px rgba(0,0,0,0.5)', padding: 10,
        }}>
          <div className="label" style={{ marginBottom: 6 }}>Theme</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
            {Object.entries(THEMES).map(([key, t]) => (
              <button key={key} className={`btn ${user.theme === key ? 'active' : ''}`}
                style={{ fontSize: 10, textAlign: 'left' }}
                onClick={() => setTheme(key)}>
                {t.label}
              </button>
            ))}
          </div>
          <button className="btn" style={{ width: '100%', fontSize: 11 }}
            onClick={() => { setOpen(false); logout() }}>
            Log out
          </button>
        </div>
      )}
    </div>
  )
}

function LiveIndicator() {
  const { data } = useWebSocketHealth()
  const stocks = data?.feeds?.stocks_ws
  if (!stocks) return null

  const live = stocks.state === 'subscribed'
  const label = live ? 'LIVE'
    : stocks.circuit_open ? 'DELAYED (feed down)'
    : stocks.state === 'connecting' ? 'CONNECTING'
    : 'DELAYED'
  const color = live ? 'var(--green)' : 'var(--gold)'
  const title = stocks.last_error
    ? `Real-time feed unavailable: ${stocks.last_error}. Showing polled/delayed data.`
    : live ? 'Real-time WebSocket feed connected' : 'Real-time feed not connected — showing polled data'

  return (
    <span title={title} style={{ color, fontSize: 9, cursor: 'help' }}>
      ● {label}
    </span>
  )
}

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
      <LiveIndicator />
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
  { id: 'research',  label: 'RESEARCH' },
  { id: 'markets',   label: 'MARKETS' },
  { id: 'world',     label: 'WORLD' },
  { id: 'futures',   label: 'FUTURES' },
  { id: 'multichart',label: 'MULTI' },
  { id: 'regime',    label: 'REGIME' },
  { id: 'events',    label: 'EVENTS' },
  { id: 'altdata',   label: 'ALT-DATA' },
  { id: 'whales',    label: 'WHALES' },
  { id: 'network',   label: 'NETWORK' },
  { id: 'ties',      label: 'TIES' },
  { id: 'backtest',  label: 'BACKTEST' },
  { id: 'arb',       label: 'ARB' },
  { id: 'supply',    label: 'SUPPLY' },
  { id: 'algo',      label: 'ALGO' },
  { id: 'portfolio', label: 'PORTFOLIO' },
  { id: 'yield',     label: 'YIELD' },
  { id: 'credit',    label: 'CREDIT' },
  { id: 'macro',     label: 'MACRO' },
  { id: 'news',      label: 'NEWS' },
]

// ── Layout for each tab ──────────────────────────────────────────
function OverviewLayout({ chartSymbol, watchlistSymbols }) {
  const cell = { minHeight: 0, minWidth: 0, overflow: 'hidden' }
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '2fr 1fr 240px',
      gridTemplateRows:    '1fr 1fr',
      gap: 6,
      height: '100%',
      minHeight: 0,
    }}>
      {/* Chart dominates — spans both rows on the left */}
      <div style={{ ...cell, gridColumn: '1', gridRow: '1 / 3' }}>
        <PriceChart symbol={chartSymbol} />
      </div>
      <div style={{ ...cell, gridColumn: '2', gridRow: '1' }}>
        <MarketMonitor symbols={watchlistSymbols} />
      </div>
      <div style={{ ...cell, gridColumn: '3', gridRow: '1' }}>
        <FearGreed />
      </div>
      <div style={{ ...cell, gridColumn: '2', gridRow: '2' }}>
        <SectorHeatmap />
      </div>
      <div style={{ ...cell, gridColumn: '3', gridRow: '2' }}>
        <YieldCurve />
      </div>
    </div>
  )
}

function OptionsLayout() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 1.2fr',
      gridTemplateRows: '1fr 1fr',
      gap: 4,
      height: '100%',
    }}>
      <div style={{ gridColumn: '1', gridRow: '1 / 3' }}><OptionsFlow /></div>
      <div style={{ gridColumn: '2', gridRow: '1' }}><VolSurface /></div>
      <div style={{ gridColumn: '2', gridRow: '2' }}><UnusualActivity /></div>
      <div style={{ gridColumn: '3', gridRow: '1 / 3' }}><OptionsChain /></div>
    </div>
  )
}

function MacroLayout() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 1fr',
      gap: 4,
      height: '100%',
      minHeight: 0,
    }}>
      <div style={{ minHeight: 0 }}><MacroDashboard /></div>
      <div style={{ minHeight: 0 }}><MacroExpanded /></div>
      <div style={{ minHeight: 0 }}><YieldCurve /></div>
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

function ResearchLayout() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr', gap: 4, height: '100%' }}>
      <Pairs />
      <Correlation />
      <div style={{ gridColumn: '1 / 3' }}><OptionsResearch /></div>
    </div>
  )
}

function CreditLayout() {
  return (
    <div style={{ height: '100%', maxWidth: 1000, margin: '0 auto' }}>
      <Credit />
    </div>
  )
}

function PortfolioLayout() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, height: '100%' }}>
      <Portfolio />
      <OptionsGreeksDashboard />
    </div>
  )
}

function NetworkLayout() {
  return (
    <div style={{ height: '100%' }}>
      <Network />
    </div>
  )
}

function TiesLayout() {
  return (
    <div style={{ height: '100%' }}>
      <Ties />
    </div>
  )
}

function BacktestLayout() {
  return (
    <div style={{ height: '100%' }}>
      <BacktestTab />
    </div>
  )
}

function ArbLayout() {
  return (
    <div style={{ height: '100%' }}>
      <Arbitrage />
    </div>
  )
}

function WorldLayout() {
  return (
    <div style={{ height: '100%' }}>
      <International />
    </div>
  )
}

function FuturesLayout() {
  return (
    <div style={{ height: '100%' }}>
      <Futures />
    </div>
  )
}

function MultiChartLayout() {
  return (
    <div style={{ height: '100%' }}>
      <MultiChart />
    </div>
  )
}

function RegimeLayout() {
  return (
    <div style={{ height: '100%' }}>
      <Regime />
    </div>
  )
}

function EventsLayout() {
  return (
    <div style={{ height: '100%' }}>
      <Events />
    </div>
  )
}

function AltDataLayout() {
  return (
    <div style={{ height: '100%' }}>
      <AltData />
    </div>
  )
}

function SupplyLayout() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 6,
                  height: '100%', minHeight: 0 }}>
      <div style={{ minHeight: 0 }}>
        <SupplyMap />
      </div>
      <div style={{ minHeight: 0 }}>
        <PortWatch />
      </div>
    </div>
  )
}

function MarketsLayout() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gridTemplateRows: '1fr 1fr',
      gap: 4, height: '100%',
    }}>
      <div style={{ gridColumn: '1', gridRow: '1' }}><Movers /></div>
      <div style={{ gridColumn: '1', gridRow: '2' }}><Crypto /></div>
      <div style={{ gridColumn: '2', gridRow: '1 / 3' }}><CompanyDetail /></div>
    </div>
  )
}

function WhalesLayout() {
  return (
    <div style={{ height: '100%', maxWidth: 1000, margin: '0 auto' }}>
      <Traders />
    </div>
  )
}

function YieldLayout() {
  return (
    <div style={{ height: '100%', maxWidth: 1100, margin: '0 auto' }}>
      <YieldCurvePanel />
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  )
}

function AuthGate() {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div style={{
        height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-base)', color: 'var(--text-dim)', fontSize: 12,
      }}>
        Loading…
      </div>
    )
  }
  if (!user) return <LoginScreen />
  return (
    <SymbolProvider initial="SPY">
      <AppInner />
    </SymbolProvider>
  )
}

function AppInner() {
  const [activeTab,    setActiveTab]    = useState('overview')
  const { symbol: chartSymbol, setSymbol: setChartSymbol } = useSymbol()
  const [symbolInput,  setSymbolInput]  = useState(chartSymbol)
  useEffect(() => { setSymbolInput(chartSymbol) }, [chartSymbol])
  const [showWatchlist, setShowWatchlist] = useState(false)
  const { data: watchlistData, refresh: refreshWatchlist } = useWatchlist()

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
        {/* Logo + scrollable tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0, flex: 1 }}>
          <span style={{
            fontFamily: 'var(--font-display)',
            color: 'var(--gold)', fontWeight: 700, fontSize: 17,
            letterSpacing: '0.12em', display: 'flex', alignItems: 'center', gap: 7,
            flexShrink: 0,
          }}>
            SPARK
          </span>
          {/* Tabs — horizontally scrollable strip */}
          <div className="tab-strip" style={{
            display: 'flex', gap: 3, overflowX: 'auto', overflowY: 'hidden',
            minWidth: 0, flex: 1, scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch',
          }}>
            {TABS.map(t => (
              <button
                key={t.id}
                ref={t.id === activeTab ? (el) => el?.scrollIntoView({ inline: 'nearest', block: 'nearest' }) : null}
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
                  whiteSpace:   'nowrap',
                  flexShrink:   0,
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Symbol lookup + watchlist editor */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, position: 'relative',
                      flexShrink: 0, marginLeft: 12 }}>
          <button
            onClick={() => setShowWatchlist(!showWatchlist)}
            className="btn"
            style={{ fontSize: 11 }}
            title="Edit watchlist"
          >
            Watchlist
          </button>
          <NotificationBell />
          <span className="dim" style={{ fontSize: 9 }}>CHART:</span>
          <SymbolSearch
            value={symbolInput}
            onChange={setSymbolInput}
            onSelect={(sym) => { setSymbolInput(sym); setChartSymbol(sym) }}
            width={90}
          />
          {showWatchlist && (
            <WatchlistManager onClose={() => setShowWatchlist(false)} onChange={refreshWatchlist} />
          )}
        </div>

        <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
          <UserMenu />
          <Clock />
        </div>
      </div>

      {/* ── Main Content ─────────────────────────────────────────── */}
      <div style={{ flex: 1, padding: 4, overflow: 'hidden', minHeight: 0 }}>
        {activeTab === 'overview' && <OverviewLayout chartSymbol={chartSymbol} watchlistSymbols={watchlistData?.symbols} />}
        {activeTab === 'options'  && <OptionsLayout />}
        {activeTab === 'quant'    && <QuantLayout />}
        {activeTab === 'research' && <ResearchLayout />}
        {activeTab === 'markets'  && <MarketsLayout />}
        {activeTab === 'world'    && <WorldLayout />}
        {activeTab === 'futures'  && <FuturesLayout />}
        {activeTab === 'multichart' && <MultiChartLayout />}
        {activeTab === 'regime'   && <RegimeLayout />}
        {activeTab === 'events'   && <EventsLayout />}
        {activeTab === 'altdata'  && <AltDataLayout />}
        {activeTab === 'whales'   && <WhalesLayout />}
        {activeTab === 'network'  && <NetworkLayout />}
        {activeTab === 'ties'     && <TiesLayout />}
        {activeTab === 'backtest' && <BacktestLayout />}
        {activeTab === 'arb'      && <ArbLayout />}
        {activeTab === 'supply'   && <SupplyLayout />}
        {activeTab === 'yield'    && <YieldLayout />}
        {activeTab === 'algo'     && <AlgoLayout />}
        {activeTab === 'portfolio' && <PortfolioLayout />}
        {activeTab === 'credit'   && <CreditLayout />}
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
