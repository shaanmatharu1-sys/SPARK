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
