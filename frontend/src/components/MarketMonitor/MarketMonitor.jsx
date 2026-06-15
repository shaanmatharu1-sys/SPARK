import React, { useState, useCallback, useRef } from 'react'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useQuotes } from '../../hooks/useMarketData'

const WATCHLIST = ['SPY','QQQ','IWM','AAPL','MSFT','NVDA','TSLA','META','GOOGL','AMZN']

function fmt(n, decimals = 2) {
  if (n == null) return '—'
  return Number(n).toFixed(decimals)
}

function PctChange({ value }) {
  if (value == null) return <span className="dim">—</span>
  const positive = value >= 0
  return (
    <span className={positive ? 'green' : 'red'}>
      {positive ? '+' : ''}{fmt(value, 2)}%
    </span>
  )
}

export default function MarketMonitor() {
  const [prices, setPrices] = useState({})
  const flashRef = useRef({})

  // Initial snapshot via REST
  const { data: snapshot } = useQuotes(WATCHLIST)

  // Merge snapshot into prices
  React.useEffect(() => {
    if (!snapshot) return
    const merged = {}
    for (const [sym, snap] of Object.entries(snapshot)) {
      merged[sym] = {
        price:      snap?.lastTrade?.p || snap?.day?.c,
        prev_close: snap?.prevDay?.c,
        open:       snap?.day?.o,
        high:       snap?.day?.h,
        low:        snap?.day?.l,
        volume:     snap?.day?.v,
        vwap:       snap?.day?.vw,
      }
    }
    setPrices(merged)
  }, [snapshot])

  // Real-time trades via WebSocket
  const onMessage = useCallback((msg) => {
    if (msg.type !== 'trade') return
    const sym = msg.symbol
    setPrices(prev => {
      const existing = prev[sym] || {}
      return {
        ...prev,
        [sym]: {
          ...existing,
          price: msg.price,
          size:  msg.size,
          ts:    msg.ts,
        }
      }
    })
    // Track flash direction
    const prev = prices[sym]?.price
    flashRef.current[sym] = prev != null
      ? (msg.price >= prev ? 'flash-green' : 'flash-red')
      : ''
    setTimeout(() => { flashRef.current[sym] = '' }, 600)
  }, [prices])

  const wsStatus = useWebSocket(
    `/quotes/ws?symbols=${WATCHLIST.join(',')}`,
    onMessage
  )

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">⬡ Market Monitor</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {wsStatus === 'connected' && <span className="live-dot" />}
          <span className="dim" style={{ fontSize: 9 }}>
            {wsStatus === 'connected' ? 'LIVE' : wsStatus.toUpperCase()}
          </span>
        </span>
      </div>

      <div className="panel-body">
        <table className="bbg-table">
          <thead>
            <tr>
              <th>SYMBOL</th>
              <th>PRICE</th>
              <th>CHG%</th>
              <th>OPEN</th>
              <th>HIGH</th>
              <th>LOW</th>
              <th>VWAP</th>
              <th>VOLUME</th>
            </tr>
          </thead>
          <tbody>
            {WATCHLIST.map(sym => {
              const q = prices[sym] || {}
              const pct = q.price && q.prev_close
                ? ((q.price - q.prev_close) / q.prev_close) * 100
                : null

              return (
                <tr key={sym} className={flashRef.current[sym] || ''}>
                  <td style={{ color: 'var(--yellow)', fontWeight: 'bold' }}>{sym}</td>
                  <td style={{ color: 'var(--text-primary)' }}>{fmt(q.price)}</td>
                  <td><PctChange value={pct} /></td>
                  <td>{fmt(q.open)}</td>
                  <td className="green">{fmt(q.high)}</td>
                  <td className="red">{fmt(q.low)}</td>
                  <td>{fmt(q.vwap)}</td>
                  <td className="dim">
                    {q.volume ? (q.volume / 1e6).toFixed(1) + 'M' : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
