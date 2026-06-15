import { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE } from '../config'

const API = API_BASE

export function useFetch(endpoint, intervalMs = null) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const fetch_ = useCallback(async () => {
    try {
      const r = await fetch(`${API}${endpoint}`)
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
  const symsParam = symbols.join(',')
  return useFetch(`/quotes/snapshot?symbols=${symsParam}`, 5000)
}

export function useBars(symbol, multiplier = 1, timespan = 'minute') {
  return useFetch(`/quotes/${symbol}/bars?multiplier=${multiplier}&timespan=${timespan}`, null)
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
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return r.json()
  },
  async run(id) {
    const r = await fetch(`${API}/algo/${id}/run`, { method: 'POST' })
    return r.json()
  },
  async reset(id) {
    const r = await fetch(`${API}/algo/${id}/reset`, { method: 'POST' })
    return r.json()
  },
  async remove(id) {
    const r = await fetch(`${API}/algo/${id}`, { method: 'DELETE' })
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
export function useEarnings(symbol) {
  return useFetch(`/markets/earnings/${symbol}`, 3600_000)
}
export function useFilings(symbol) {
  return useFetch(`/markets/filings/${symbol}`, 3600_000)
}
export function useSocial(symbol) {
  return useFetch(`/markets/social/${symbol}`, 300_000)
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

// ── Watchlist actions ──
export const watchlistApi = {
  async get() {
    const r = await fetch(`${API}/watchlist/`); return r.json()
  },
  async set(symbols) {
    const r = await fetch(`${API}/watchlist/`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ symbols }),
    }); return r.json()
  },
  async add(symbol) {
    const r = await fetch(`${API}/watchlist/add/${symbol}`, { method: 'POST' }); return r.json()
  },
  async remove(symbol) {
    const r = await fetch(`${API}/watchlist/${symbol}`, { method: 'DELETE' }); return r.json()
  },
  async reset() {
    const r = await fetch(`${API}/watchlist/reset`, { method: 'POST' }); return r.json()
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
}

// ── Portfolio (manual) ──
export function usePortfolio() {
  return useFetch('/portfolio', 60_000)
}
export const portfolioApi = {
  async add(symbol, shares, cost_basis) {
    const r = await fetch(`${API}/portfolio/add`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ symbol, shares, cost_basis }),
    }); return r.json()
  },
  async remove(symbol) {
    const r = await fetch(`${API}/portfolio/${symbol}`, { method: 'DELETE' }); return r.json()
  },
}
