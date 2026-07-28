import React, { useState, useMemo, useCallback, useRef } from 'react'
import { useOrderBookSnapshot, useOrderBookProducts } from '../../hooks/useMarketData'
import { useWebSocket } from '../../hooks/useWebSocket'

// Real, live, top-50-depth L2 order book for crypto (Coinbase's public feed —
// genuinely real market depth, not a simulation) plus honest top-of-book-
// only quotes for equities where a quote entitlement exists. No synthetic
// equity depth is ever fabricated — see backend/services/orderbook_client.py.

const DEPTH_H = 140

function DepthChart({ bids, asks, mid }) {
  const w = 100, h = DEPTH_H
  const maxTotal = Math.max(
    bids[bids.length - 1]?.total || 0,
    asks[asks.length - 1]?.total || 0,
  ) || 1
  const maxPriceDist = Math.max(
    mid - (bids[bids.length - 1]?.price ?? mid),
    (asks[asks.length - 1]?.price ?? mid) - mid,
  ) || 1

  // bid side: price descends away from mid (left half), ask side ascends (right half)
  const bidPts = bids.map(b => {
    const x = 50 - ((mid - b.price) / maxPriceDist) * 50
    const y = h - (b.total / maxTotal) * h
    return `${x},${y}`
  })
  const askPts = asks.map(a => {
    const x = 50 + ((a.price - mid) / maxPriceDist) * 50
    const y = h - (a.total / maxTotal) * h
    return `${x},${y}`
  })
  const bidPath = bidPts.length ? `M50,${h} L${bidPts.join(' L')} L50,${h} Z` : ''
  const askPath = askPts.length ? `M50,${h} L${askPts.join(' L')} L50,${h} Z` : ''

  return (
    <svg viewBox={`0 0 100 ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: DEPTH_H, display: 'block' }}>
      <line x1="50" y1="0" x2="50" y2={h} stroke="var(--border-bright)" strokeWidth="0.3" />
      {bidPath && <path d={bidPath} fill="rgba(63,182,139,0.28)" stroke="#3FB68B" strokeWidth="0.6" vectorEffect="non-scaling-stroke" />}
      {askPath && <path d={askPath} fill="rgba(224,85,107,0.28)" stroke="#E0556B" strokeWidth="0.6" vectorEffect="non-scaling-stroke" />}
    </svg>
  )
}

function Ladder({ bids, asks, best }) {
  const maxTotal = Math.max(bids[bids.length - 1]?.total || 0, asks[asks.length - 1]?.total || 0) || 1
  const rows = Math.max(bids.length, asks.length)
  const items = []
  for (let i = 0; i < rows; i++) {
    items.push({ bid: bids[i], ask: asks[i] })
  }
  return (
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 2,
                    fontSize: 8.5, color: 'var(--text-dim)', padding: '2px 4px' }}>
        <span>SIZE</span><span style={{ textAlign: 'right' }}>BID</span>
        <span>ASK</span><span style={{ textAlign: 'right' }}>SIZE</span>
      </div>
      {items.map((row, i) => (
        <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 2, position: 'relative' }}>
          <div style={{ position: 'absolute', inset: 0, left: '50%', right: 0,
                        background: 'rgba(224,85,107,0.10)',
                        width: row.ask ? `${(row.ask.total / maxTotal) * 50}%` : 0 }} />
          <div style={{ position: 'absolute', inset: 0, right: '50%', left: 0,
                        background: 'rgba(63,182,139,0.10)',
                        width: row.bid ? `${(row.bid.total / maxTotal) * 50}%` : 0, marginLeft: 'auto' }} />
          <span style={{ padding: '1px 4px', position: 'relative', color: 'var(--text-dim)' }}>
            {row.bid ? row.bid.size.toFixed(row.bid.size < 1 ? 5 : 3) : ''}
          </span>
          <span style={{ padding: '1px 4px', position: 'relative', textAlign: 'right', color: 'var(--green)', fontWeight: 600 }}>
            {row.bid ? row.bid.price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : ''}
          </span>
          <span style={{ padding: '1px 4px', position: 'relative', color: 'var(--red)', fontWeight: 600 }}>
            {row.ask ? row.ask.price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : ''}
          </span>
          <span style={{ padding: '1px 4px', position: 'relative', textAlign: 'right', color: 'var(--text-dim)' }}>
            {row.ask ? row.ask.size.toFixed(row.ask.size < 1 ? 5 : 3) : ''}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function OrderBook() {
  const { data: productsData } = useOrderBookProducts()
  const [symbol, setSymbol] = useState('BTCUSD')
  const { data: snap, loading } = useOrderBookSnapshot(symbol)
  const [live, setLive] = useState(null)
  const symbolRef = useRef(symbol)
  symbolRef.current = symbol

  const onMessage = useCallback((msg) => {
    if (msg?.type !== 'orderbook') return
    const sym = (msg.symbol || '').replace('-', '')
    if (sym !== symbolRef.current) return
    setLive(msg)
  }, [])

  useWebSocket('/orderbook/ws', onMessage, true)

  const book = live?.symbol?.replace('-', '') === symbol ? live : snap

  const products = productsData?.products || ['BTCUSD', 'ETHUSD', 'SOLUSD', 'DOGEUSD']

  const isCrypto = book?.crypto
  const bids = book?.bids || []
  const asks = book?.asks || []
  const mid = book?.mid

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: 6 }}>
        <span className="title">Order Book</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
          {products.map(p => (
            <button key={p} className={`btn ${symbol === p ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 8px' }}
              onClick={() => { setSymbol(p); setLive(null) }}>
              {p}
            </button>
          ))}
          <input className="input" placeholder="or type a ticker (e.g. AAPL)"
            style={{ width: 150, fontSize: 10, padding: '2px 6px' }}
            onKeyDown={e => {
              if (e.key === 'Enter' && e.currentTarget.value.trim()) {
                setSymbol(e.currentTarget.value.trim().toUpperCase())
                setLive(null)
              }
            }} />
        </div>
      </div>
      <div className="panel-body" style={{ padding: 10, overflowY: 'auto' }}>
        {loading && !book && <div className="dim" style={{ fontSize: 11 }}>Loading order book…</div>}

        {book && !isCrypto && (
          <div style={{ marginBottom: 10, padding: '8px 10px', background: 'var(--bg-base)', borderRadius: 5 }}>
            <div className="dim" style={{ fontSize: 10, marginBottom: 6 }}>{book.note}</div>
            {book.available ? (
              <div style={{ display: 'flex', gap: 24, fontFamily: 'var(--font-mono)', fontSize: 14 }}>
                <span>Bid <b style={{ color: 'var(--green)' }}>{book.best_bid?.toFixed(2)}</b>
                  <span className="dim" style={{ fontSize: 9, marginLeft: 4 }}>×{book.best_bid_size}</span></span>
                <span>Ask <b style={{ color: 'var(--red)' }}>{book.best_ask?.toFixed(2)}</b>
                  <span className="dim" style={{ fontSize: 9, marginLeft: 4 }}>×{book.best_ask_size}</span></span>
                <span className="dim">Spread {book.spread?.toFixed(4)}</span>
              </div>
            ) : (
              <div style={{ color: 'var(--text-dim)', fontSize: 11 }}>No quote available for {symbol}.</div>
            )}
          </div>
        )}

        {book && isCrypto && bids.length > 0 && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                          marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
              <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>{book.note}</span>
              <span style={{ fontSize: 13 }}>
                Mid <b style={{ color: 'var(--gold-bright)' }}>{mid?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</b>
                <span className="dim" style={{ fontSize: 10, marginLeft: 10 }}>Spread {book.spread?.toFixed(2)}</span>
              </span>
            </div>
            <DepthChart bids={bids} asks={asks} mid={mid} />
            <div style={{ marginTop: 8 }}>
              <Ladder bids={bids} asks={asks} best={{ bid: book.best_bid, ask: book.best_ask }} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
