import { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE } from '../config'
import { authHeader } from './useAuth'

const API = API_BASE

export function useFetch(endpoint, intervalMs = null) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const fetch_ = useCallback(async () => {
    if (!endpoint) { setLoading(false); return }
    try {
      const r = await fetch(`${API}${endpoint}`, { headers: authHeader() })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setData(await r.json())
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [endpoint])

  useEffect(() => {
    fetch_()
    if (intervalMs) {
      const id = setInterval(fetch_, intervalMs)
      return () => clearInterval(id)
    }
  }, [fetch_, intervalMs])

  return { data, loading, error, refresh: fetch_ }
}

export function useQuotes(symbols) {
  // Live price ticks already arrive over the /quotes/ws websocket (see MarketMonitor);
  // this REST poll only needs to refresh the slower-moving day OHLC/volume/vwap fields,
  // so a 5s interval was pure redundant load on Polygon/Redis for no visible benefit.
  const symsParam = symbols.join(',')
  return useFetch(`/quotes/snapshot?symbols=${symsParam}`, 60_000)
}

export function useTickerDetails(symbol) {
  return useFetch(symbol ? `/quotes/${symbol}/details` : null, null)
}

export function useBars(symbol, multiplier = 1, timespan = 'minute', limit = 390, fromDate = null) {
  // 30s poll as a baseline so the chart doesn't go stale between symbol/timeframe
  // changes; PriceChart additionally layers live websocket ticks on top for 1D view.
  // fromDate overrides the backend's default lookback window — needed for YTD/All-Time
  // ranges, where the auto-computed lookback wouldn't reach far enough back.
  const fromQs = fromDate ? `&from_date=${fromDate}` : ''
  return useFetch(`/quotes/${symbol}/bars?multiplier=${multiplier}&timespan=${timespan}&limit=${limit}${fromQs}`, 30_000)
}

export function useMacroDashboard() {
  return useFetch('/macro/dashboard', 3600_000)
}

export function useYieldCurve() {
  return useFetch('/macro/yield-curve', 3600_000)
}

export function useSectors() {
  return useFetch('/sectors/', 30_000)
}

export function useNews(query = null) {
  const qs = query ? `?query=${encodeURIComponent(query)}` : ''
  return useFetch(`/news/${qs}`, 300_000)
}
export function useMANews() {
  return useFetch('/news/ma', 300_000)
}

export function useFearGreed() {
  return useFetch('/sentiment/fear-greed', 600_000)
}

export function useUnusualActivity(symbol = null) {
  const qs = symbol ? `?symbol=${symbol}` : ''
  return useFetch(`/unusual/${qs}`, 60_000)
}

export function useOptionsSnapshot(symbol) {
  return useFetch(`/options/${symbol}/snapshot`, 10_000)
}

export function useOptionsChainFull(symbol, expiration, window = 20) {
  const params = new URLSearchParams()
  if (expiration) params.set('expiration_date', expiration)
  params.set('window', window)
  return useFetch(symbol ? `/options/${symbol}/chain-full?${params}` : null, 15_000)
}

// ── Manual option positions / portfolio Greeks ──
export function useOptionPositionsGreeks() {
  return useFetch('/options/positions/greeks', 30_000)
}
export const optionPositionsApi = {
  async list() {
    const r = await fetch(`${API}/options/positions`, { headers: authHeader() }); return r.json()
  },
  async add(position) {
    const r = await fetch(`${API}/options/positions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify(position),
    }); return r.json()
  },
  async remove(id) {
    const r = await fetch(`${API}/options/positions/${id}`, { method: 'DELETE', headers: authHeader() }); return r.json()
  },
}

export function useSupplyChain() {
  return useFetch('/sentiment/supply-chain', 3600_000)
}

export function useStrategies() {
  return useFetch('/quant/strategies', null)
}

export function useBacktestCompare(symbol, days = 365, costBps = 1.0) {
  return useFetch(`/quant/backtest/${symbol}/compare?days=${days}&cost_bps=${costBps}`, null)
}

export function useSignals(symbol, days = 365) {
  return useFetch(`/quant/signals/${symbol}?days=${days}`, 60_000)
}

export function useFactorRankings(universe = 'watchlist', days = 400) {
  return useFetch(`/factors/rankings?universe=${universe}&days=${days}`, 300_000)
}

export function useVolSurface(symbol) {
  return useFetch(`/vol/surface/${symbol}`, 60_000)
}

export function useAlgoList() {
  return useFetch('/algo/list', 15_000)
}

export function useAlgoTemplates() {
  return useFetch('/algo/templates', null)
}

// Action helpers (POST/DELETE) — not hooks, just fetch wrappers
export const algoApi = {
  async create(body) {
    const r = await fetch(`${API}/algo/create`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify(body),
    })
    return r.json()
  },
  async run(id) {
    const r = await fetch(`${API}/algo/${id}/run`, { method: 'POST', headers: authHeader() })
    return r.json()
  },
  async reset(id) {
    const r = await fetch(`${API}/algo/${id}/reset`, { method: 'POST', headers: authHeader() })
    return r.json()
  },
  async remove(id) {
    const r = await fetch(`${API}/algo/${id}`, { method: 'DELETE', headers: authHeader() })
    return r.json()
  },
}

// ── Research: pairs, correlation, macro matrix ──
export function usePairs(universe = 'watchlist', days = 400) {
  return useFetch(`/research/pairs?universe=${universe}&days=${days}`, 300_000)
}
export function useCorrelation(universe = 'watchlist', days = 120) {
  return useFetch(`/research/correlation?universe=${universe}&days=${days}`, 300_000)
}
export function useMacroMatrix(days = 250) {
  return useFetch(`/research/macro-matrix?days=${days}`, 300_000)
}

// ── Markets: movers, crypto, earnings, filings, social ──
export function useMovers(direction = 'gainers') {
  return useFetch(`/markets/movers?direction=${direction}`, 30_000)
}
export function useCrypto() {
  return useFetch('/markets/crypto', 15_000)
}
// Wider coin coverage via Webull's OpenAPI (stopgap — see services/webull_client.py).
// Returns {} if WEBULL_APP_KEY/SECRET aren't configured, so callers should
// merge this on top of useCrypto() rather than replace it.
export function useCryptoWebull() {
  return useFetch('/markets/crypto/webull', 20_000)
}
export function useEarnings(symbol) {
  return useFetch(`/markets/earnings/${symbol}`, 3600_000)
}
export function useFilings(symbol) {
  return useFetch(`/markets/filings/${symbol}`, 3600_000)
}
export function useSocial(symbol) {
  return useFetch(`/markets/social/${symbol}`, 300_000)
}

// ── Corporate actions / fundamentals ──
export function useDividends(symbol) {
  return useFetch(symbol ? `/quotes/${symbol}/dividends` : null, 3600_000)
}
export function useSplits(symbol) {
  return useFetch(symbol ? `/quotes/${symbol}/splits` : null, 3600_000)
}
export function useShortInterest(symbol) {
  return useFetch(symbol ? `/fundamentals/${symbol}/short-interest` : null, 3600_000)
}
export function useAnalystRatings(symbol) {
  return useFetch(symbol ? `/fundamentals/${symbol}/ratings` : null, 3600_000)
}
export function useRelativeValuation(symbols) {
  return useFetch(symbols?.length ? `/fundamentals/relative-valuation?symbols=${symbols.join(',')}` : null, null)
}

// ── Watchlist ──
export function useWatchlist() {
  return useFetch('/watchlist/', null)
}

// ── Traders ──
export function useInsider(symbol) {
  return useFetch(`/traders/insider/${symbol}`, 600_000)
}
export function useCongress(chamber = 'house') {
  return useFetch(`/traders/congress?chamber=${chamber}`, 600_000)
}
export function useFunds() {
  return useFetch('/traders/funds', null)
}
export function use13F(fundKey) {
  return useFetch(`/traders/13f/${fundKey}`, 3600_000)
}

// ── Extended yield curve ──
export function useYieldCurveExtended() {
  return useFetch('/macro/yield-curve/extended', 3600_000)
}

// ── Global fixed income depth: sovereign 10Y yields + TIPS real yields ──
export function useGlobalYields() {
  return useFetch('/macro/global-yields', 3600_000)
}
export function useRealYields() {
  return useFetch('/macro/real-yields', 3600_000)
}

// ── Watchlist actions ──
export const watchlistApi = {
  async get() {
    const r = await fetch(`${API}/watchlist/`, { headers: authHeader() }); return r.json()
  },
  async set(symbols) {
    const r = await fetch(`${API}/watchlist/`, {
      method: 'PUT', headers: {'Content-Type': 'application/json', ...authHeader()},
      body: JSON.stringify({ symbols }),
    }); return r.json()
  },
  async add(symbol) {
    const r = await fetch(`${API}/watchlist/add/${symbol}`, { method: 'POST', headers: authHeader() }); return r.json()
  },
  async remove(symbol) {
    const r = await fetch(`${API}/watchlist/${symbol}`, { method: 'DELETE', headers: authHeader() }); return r.json()
  },
  async reset() {
    const r = await fetch(`${API}/watchlist/reset`, { method: 'POST', headers: authHeader() }); return r.json()
  },
}

// ── Price alerts (in-app, WebSocket-delivered) ──
export function useAlerts() {
  return useFetch('/alerts/', 60_000)
}
export const alertsApi = {
  async list() {
    const r = await fetch(`${API}/alerts/`, { headers: authHeader() }); return r.json()
  },
  async create(symbol, condition, threshold) {
    const r = await fetch(`${API}/alerts/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify({ symbol, condition, threshold }),
    }); return r.json()
  },
  async remove(id) {
    const r = await fetch(`${API}/alerts/${id}`, { method: 'DELETE', headers: authHeader() }); return r.json()
  },
}

// ── WebSocket feed health (honest LIVE/DELAYED indicator — see backend
// main.py's /health, which now reports real connection state instead of
// the old always-true `.running` flag) ──
export function useWebSocketHealth() {
  return useFetch('/health', 15_000)
}

// ── Market regime dashboard ──
export function useMarketRegime() {
  return useFetch('/regime/', 300_000)
}

// ── Multi-chart workspace (persisted per-user grid layout) ──
export function useWorkspace() {
  return useFetch('/workspace/', null)
}
export const workspaceApi = {
  async get() {
    const r = await fetch(`${API}/workspace/`, { headers: authHeader() }); return r.json()
  },
  async set(rows, cols, cells) {
    const r = await fetch(`${API}/workspace/`, {
      method: 'PUT', headers: {'Content-Type': 'application/json', ...authHeader()},
      body: JSON.stringify({ rows, cols, cells }),
    }); return r.json()
  },
}

// ── Credit ──
export function useCreditDashboard() {
  return useFetch('/credit/dashboard', 600_000)
}

// ── Options research ──
export function useOptionsStrategies() {
  return useFetch('/options-research/strategies', null)
}
export function useIVRank(symbol) {
  return useFetch(`/options-research/iv-rank/${symbol}`, 600_000)
}
export function useOptionsFlow(symbol) {
  return useFetch(`/options-research/flow/${symbol}`, 120_000)
}
export function useOptionsSkew(symbol) {
  return useFetch(`/options-research/skew/${symbol}`, 300_000)
}
export const optionsApi = {
  async payoff(strategy, spot, params) {
    const r = await fetch(`${API}/options-research/payoff`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ strategy, spot, params }),
    }); return r.json()
  },
  async payoffCustom(legs, spot) {
    const r = await fetch(`${API}/options-research/payoff/custom`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ legs, spot }),
    }); return r.json()
  },
}

// ── Portfolio (manual) ──
export function usePortfolio() {
  return useFetch('/portfolio', 60_000)
}
export const portfolioApi = {
  async add(symbol, shares, cost_basis) {
    const r = await fetch(`${API}/portfolio/add`, {
      method: 'POST', headers: {'Content-Type': 'application/json', ...authHeader()},
      body: JSON.stringify({ symbol, shares, cost_basis }),
    }); return r.json()
  },
  async remove(symbol) {
    const r = await fetch(`${API}/portfolio/${symbol}`, { method: 'DELETE', headers: authHeader() }); return r.json()
  },
}

// ── Correlation network ──
export function useNetwork(symbols, threshold = 0.4) {
  const q = symbols ? `?symbols=${symbols}&threshold=${threshold}` : ''
  return useFetch(symbols ? `/network${q}` : null, null)
}

// ── Expanded macro ──
export function useMacroExpanded(category) {
  return useFetch(`/macro/expanded${category ? '?category='+category : ''}`, 600_000)
}

// ── Vessel map (AISstream) ──
export function useVessels() {
  return useFetch('/markets/vessels', 20_000)
}

// ── Flight tracking (OpenSky Network) ──
export function useFlights() {
  return useFetch('/markets/flights', 18_000)
}

// ── Company relationship ties (SPLC-style) ──
export function useCompanyTies(symbol) {
  return useFetch(symbol ? `/ties?symbol=${symbol}` : null, null)
}

// ── International markets ──
export function useInternational() {
  return useFetch('/international/all', 60_000)
}
export function useIndexBars(symbol, interval = '5m') {
  // World Indices (^GSPC, ^N225, ...) aren't Polygon-covered — EODHD-backed,
  // separate from useBars. 30s poll to match useBars' live-chart cadence.
  return useFetch(symbol ? `/international/indices/${encodeURIComponent(symbol)}/bars?interval=${interval}` : null, 30_000)
}
export function useCountryDirectory() {
  return useFetch('/international/directory', 60_000)
}

// ── Futures (yfinance quotes + CFTC COT positioning) ──
export function useFuturesAll() {
  return useFetch('/futures/all', 60_000)
}
export function useFuturesBars(symbol, days = 90) {
  return useFetch(symbol ? `/futures/${encodeURIComponent(symbol)}/bars?days=${days}` : null, null)
}
export function useFuturesCOT(symbol, weeks = 26) {
  return useFetch(symbol ? `/futures/${encodeURIComponent(symbol)}/cot?weeks=${weeks}` : null, null)
}

// ── Alt-data & events ──
export function useAltData() {
  return useFetch('/altdata/all', 300_000)  // 5 min
}
export function useEvents() {
  return useFetch('/events/all', 600_000)    // 10 min
}

// ── IMF PortWatch ──
export function usePortWatch() {
  return useFetch('/markets/portwatch', 3600_000)  // 1h (weekly data)
}

// ── Backtest, BYO-algo, arbitrage ──
export function useIndicators() {
  return useFetch('/quant/indicators', null)
}
export function useETFArb() {
  return useFetch('/arbitrage/etf', 30_000)
}
export async function runCustomBacktest(symbol, entry, exit, days = 730, costBps = 1.0) {
  const r = await fetch(`${API}/quant/backtest/${symbol}/custom?days=${days}&cost_bps=${costBps}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entry, exit }),
  })
  return r.json()
}
export async function runPresetBacktest(symbol, strategy, days = 730, costBps = 1.0) {
  const r = await fetch(`${API}/quant/backtest/${symbol}?strategy=${strategy}&days=${days}&cost_bps=${costBps}`)
  return r.json()
}

// ── Graph Builder — formula bar -> chart (Bloomberg GP-style) ──
export function useGraphFunctions() {
  return useFetch('/quant/graph/functions', null)
}
export async function runGraphEval(expr, days = 365, timespan = 'day') {
  const r = await fetch(`${API}/quant/graph/eval?days=${days}&timespan=${timespan}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expr }),
  })
  return r.json()
}

// ── Beta calculator ──
export async function fetchBeta(symbol, benchmark = 'SPY', days = 365) {
  const r = await fetch(`${API}/quant/beta/${symbol}?benchmark=${benchmark}&days=${days}`)
  return r.json()
}

// ── Full-market symbol search (not just the curated S&P universe) ──
export async function searchSymbols(query, limit = 12) {
  if (!query?.trim()) return []
  const r = await fetch(`${API}/markets/search?q=${encodeURIComponent(query)}&limit=${limit}`, {
    headers: authHeader(),
  })
  if (!r.ok) return []
  const data = await r.json()
  return data.results || []
}

// ── Weather — commodity-region conditions/forecast/anomaly, tied to futures ──
export function useWeatherRegions() {
  return useFetch('/weather/regions', 1800_000) // 30min, matches backend TTL_WEATHER
}

// ── Order book — full L2 crypto depth (Coinbase), top-of-book-only equities ──
export function useOrderBookSnapshot(symbol) {
  return useFetch(symbol ? `/orderbook/${symbol}` : null, 10_000)
}
export function useOrderBookProducts() {
  return useFetch('/orderbook/products', null)
}

// ── FX depth — cross-rate matrix + per-pair historical drill-down ──
export function useFxMatrix() {
  return useFetch('/international/fx/matrix', 1800_000)
}
export function useFxHistory(code, days = 180) {
  return useFetch(code ? `/international/fx/${code}/history?days=${days}` : null, null)
}
