import React, { useState, useEffect, useRef, useCallback } from 'react'
import { searchSymbols } from '../../hooks/useMarketData'

// Full-market symbol search box with autocomplete — finds any listed US
// equity by ticker or company name, not just the curated ~500-name S&P
// universe used elsewhere (relationship map, screeners). Falls back to
// direct entry: typing a known ticker + Enter still works with no dropdown.
export default function SymbolSearch({ value, onChange, onSelect, width = 120 }) {
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState([])
  const [highlight, setHighlight] = useState(0)
  const debounceRef = useRef(null)
  const boxRef = useRef(null)

  useEffect(() => {
    function onClickOutside(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const runSearch = useCallback((q) => {
    clearTimeout(debounceRef.current)
    if (!q || q.length < 1) { setResults([]); return }
    debounceRef.current = setTimeout(async () => {
      const r = await searchSymbols(q)
      setResults(r)
      setHighlight(0)
    }, 250)
  }, [])

  const pick = (ticker) => {
    onSelect(ticker)
    setOpen(false)
    setResults([])
  }

  return (
    <div ref={boxRef} style={{ position: 'relative' }}>
      <input
        className="input"
        value={value}
        onChange={e => {
          const v = e.target.value.toUpperCase()
          onChange(v)
          setOpen(true)
          runSearch(v)
        }}
        onFocus={() => value && runSearch(value)}
        onKeyDown={e => {
          if (e.key === 'Enter') {
            // An exact typed ticker should win over whatever's highlighted —
            // otherwise Enter silently picks the top-scored suggestion (e.g.
            // typing "AAPL" and hitting Enter could select "AAPB" if that
            // ranked first), which is surprising for the very common case of
            // typing a ticker you already know.
            const exact = open && results.find(r => r.ticker.toUpperCase() === value.toUpperCase())
            if (exact) pick(exact.ticker)
            else if (open && results[highlight]) pick(results[highlight].ticker)
            else onSelect(value)
          } else if (e.key === 'ArrowDown') {
            e.preventDefault()
            setHighlight(h => Math.min(h + 1, results.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setHighlight(h => Math.max(h - 1, 0))
          } else if (e.key === 'Escape') {
            setOpen(false)
          }
        }}
        placeholder="Search ticker or company..."
        style={{ width }}
      />
      {open && results.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, marginTop: 2, width: 260,
          background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
          borderRadius: 4, zIndex: 200, maxHeight: 280, overflowY: 'auto',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}>
          {results.map((r, i) => (
            <div
              key={r.ticker}
              onMouseDown={() => pick(r.ticker)}
              onMouseEnter={() => setHighlight(i)}
              style={{
                padding: '6px 10px', cursor: 'pointer', display: 'flex',
                justifyContent: 'space-between', gap: 8, fontSize: 11,
                background: i === highlight ? 'var(--bg-raised)' : 'transparent',
              }}
            >
              <span style={{ color: 'var(--gold)', fontWeight: 600, flexShrink: 0 }}>{r.ticker}</span>
              <span className="dim" style={{
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'right',
              }}>{r.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
