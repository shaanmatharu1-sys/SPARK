import React, { useState, useEffect } from 'react'
import { watchlistApi } from '../../hooks/useMarketData'

export default function WatchlistManager({ onClose, onChange }) {
  const [symbols, setSymbols] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    watchlistApi.get().then(d => { setSymbols(d.symbols || []); setLoading(false) })
  }, [])

  const add = async () => {
    const sym = input.trim().toUpperCase()
    if (!sym || symbols.includes(sym)) { setInput(''); return }
    const d = await watchlistApi.add(sym)
    setSymbols(d.symbols); setInput('')
    onChange?.(d.symbols)
  }
  const remove = async (sym) => {
    const d = await watchlistApi.remove(sym)
    setSymbols(d.symbols)
    onChange?.(d.symbols)
  }
  const reset = async () => {
    const d = await watchlistApi.reset()
    setSymbols(d.symbols)
    onChange?.(d.symbols)
  }

  return (
    <div style={{
      position: 'absolute', top: 44, right: 12, width: 320, zIndex: 100,
      background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
      borderRadius: 'var(--radius)', boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
    }}>
      <div className="panel-header">
        <span className="title">Edit Watchlist</span>
        <button className="btn" onClick={onClose}>close</button>
      </div>
      <div style={{ padding: 12 }}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
          <input className="input" style={{ flex: 1 }} placeholder="ADD SYMBOL…"
            value={input} onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && add()} />
          <button className="btn active" onClick={add}>Add</button>
        </div>
        {loading ? <div className="dim">Loading…</div> : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {symbols.map(s => (
              <div key={s} style={{
                display: 'flex', alignItems: 'center', gap: 5,
                background: 'var(--bg-raised)', borderRadius: 4, padding: '3px 8px',
                fontSize: 11, fontFamily: 'var(--font-mono)',
              }}>
                <span style={{ color: 'var(--gold)' }}>{s}</span>
                <span style={{ cursor: 'pointer', color: 'var(--text-dim)' }}
                  onClick={() => remove(s)}>remove</span>
              </div>
            ))}
          </div>
        )}
        <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between' }}>
          <span className="dim" style={{ fontSize: 9 }}>{symbols.length} symbols · max 50</span>
          <button className="btn" onClick={reset}>Reset to default</button>
        </div>
      </div>
    </div>
  )
}
