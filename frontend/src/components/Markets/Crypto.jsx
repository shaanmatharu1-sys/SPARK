import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useCrypto, useCryptoWebull } from '../../hooks/useMarketData'
import { useWebSocket } from '../../hooks/useWebSocket'
import { heatBg } from '../../lib/colorScale'

export default function Crypto() {
  const { data, loading } = useCrypto()
  const { data: webullData } = useCryptoWebull()
  const [prices, setPrices] = useState({})
  const flashRef = useRef({})

  // Seed from the REST snapshot, then let the Binance WS overlay keep it live.
  useEffect(() => {
    if (!data) return
    setPrices(prev => {
      const merged = { ...prev }
      for (const c of Object.values(data)) {
        if (!merged[c.symbol]) merged[c.symbol] = c
      }
      return merged
    })
  }, [data])

  // Webull (stopgap, wider coverage) only fills in coins Polygon/Coinbase
  // don't already cover — never overrides the live-streamed majors.
  useEffect(() => {
    if (!webullData) return
    setPrices(prev => {
      const merged = { ...prev }
      for (const c of Object.values(webullData)) {
        if (!merged[c.symbol]) merged[c.symbol] = c
      }
      return merged
    })
  }, [webullData])

  const onMessage = useCallback((msg) => {
    if (msg.type !== 'crypto_ticker') return
    const sym = msg.symbol
    setPrices(prev => {
      const existing = prev[sym] || {}
      flashRef.current[sym] = existing.price != null
        ? (msg.price >= existing.price ? 'flash-green' : 'flash-red')
        : ''
      return {
        ...prev,
        [sym]: { ...existing, symbol: sym, price: msg.price, change_pct: msg.change_pct, high: msg.high, low: msg.low, volume: msg.volume },
      }
    })
    setTimeout(() => { flashRef.current[sym] = '' }, 600)
  }, [])

  const wsStatus = useWebSocket('/markets/crypto/ws', onMessage)
  const coins = Object.values(prices)

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Crypto</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {wsStatus === 'connected' && <span className="live-dot" />}
          <span className="dim" style={{ fontSize: 9 }}>
            {wsStatus === 'connected' ? 'LIVE · 24/7' : '24/7'}
          </span>
        </span>
      </div>
      <div className="panel-body">
        {loading && coins.length === 0 ? <div style={{ padding: 16, color: 'var(--text-dim)' }}>Loading…</div> : (
          <table className="bbg-table">
            <thead>
              <tr><th>PAIR</th><th>PRICE</th><th>CHG%</th><th>HIGH</th><th>LOW</th></tr>
            </thead>
            <tbody>
              {coins.map(c => (
                <tr key={c.symbol} className={flashRef.current[c.symbol] || ''}>
                  <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{c.symbol}</td>
                  <td>{c.price?.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                  <td style={{ ...heatBg(c.change_pct, 5), color: c.change_pct >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {c.change_pct >= 0 ? '+' : ''}{c.change_pct?.toFixed(2)}%
                  </td>
                  <td className="dim">{c.high?.toLocaleString(undefined,{maximumFractionDigits:2})}</td>
                  <td className="dim">{c.low?.toLocaleString(undefined,{maximumFractionDigits:2})}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
