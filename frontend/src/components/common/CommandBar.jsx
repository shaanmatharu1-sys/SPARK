import React, { useState, useEffect, useRef, useCallback } from 'react'
import { searchSymbols } from '../../hooks/useMarketData'
import { ALL_PAGES, MNEMONIC_ALIASES, pageLabel } from '../../lib/navigation'

// CommandBar — the Bloomberg <GO>-key command line: type a page name, a
// real Bloomberg mnemonic (OMON, YCRV, DES, GP, ...), a ticker, or "LAST"
// to see recently visited screens, and jump straight there. Generalizes
// SymbolSearch.jsx's debounce/dropdown/keyboard-nav pattern to match
// against pages+mnemonics (instant, local) and tickers (debounced, remote)
// at the same time.
export default function CommandBar({ recentPages, onNavigate, onSymbol }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [tickerResults, setTickerResults] = useState([])
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

  const runTickerSearch = useCallback((q) => {
    clearTimeout(debounceRef.current)
    if (!q || q.length < 1) { setTickerResults([]); return }
    debounceRef.current = setTimeout(async () => {
      setTickerResults(await searchSymbols(q))
    }, 250)
  }, [])

  const isLast = query.trim().toUpperCase() === 'LAST'

  const pageMatches = isLast ? [] : ALL_PAGES
    .filter(p => p.label.toLowerCase().includes(query.toLowerCase()))
    .map(p => ({ kind: 'page', id: p.id, label: p.label, sub: 'PAGE' }))

  const mnemonicMatches = isLast || !query ? [] : Object.keys(MNEMONIC_ALIASES)
    .filter(code => code.startsWith(query.toUpperCase()))
    .slice(0, 6)
    .map(code => ({ kind: 'mnemonic', id: MNEMONIC_ALIASES[code], label: code, sub: `→ ${pageLabel(MNEMONIC_ALIASES[code])}` }))

  const recentMatches = isLast ? (recentPages || [])
    .map(id => ({ kind: 'recent', id, label: pageLabel(id), sub: 'RECENT' })) : []

  const tickerMatches = isLast ? [] : tickerResults
    .map(r => ({ kind: 'ticker', id: r.ticker, label: r.ticker, sub: r.name }))

  const results = [...recentMatches, ...mnemonicMatches, ...pageMatches, ...tickerMatches].slice(0, 12)

  const pick = (r) => {
    if (r.kind === 'ticker') onSymbol(r.id)
    else onNavigate(r.id)
    setQuery('')
    setTickerResults([])
    setOpen(false)
  }

  return (
    <div ref={boxRef} style={{ position: 'relative' }}>
      <input
        className="input"
        value={query}
        onChange={e => {
          const v = e.target.value
          setQuery(v)
          setOpen(true)
          setHighlight(0)
          runTickerSearch(v)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={e => {
          if (e.key === 'Enter') {
            if (results[highlight]) pick(results[highlight])
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
        placeholder="Go to page, code, or ticker… (try LAST)"
        style={{ width: 220, fontFamily: 'var(--font-mono)' }}
      />
      {open && results.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, marginTop: 2, width: 300,
          background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
          borderRadius: 4, zIndex: 200, maxHeight: 320, overflowY: 'auto',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}>
          {results.map((r, i) => (
            <div
              key={`${r.kind}-${r.id}-${i}`}
              onMouseDown={() => pick(r)}
              onMouseEnter={() => setHighlight(i)}
              style={{
                padding: '6px 10px', cursor: 'pointer', display: 'flex',
                justifyContent: 'space-between', gap: 8, fontSize: 11,
                background: i === highlight ? 'var(--bg-raised)' : 'transparent',
              }}
            >
              <span style={{
                color: r.kind === 'ticker' ? 'var(--gold)' : 'var(--text-primary)',
                fontWeight: 600, flexShrink: 0,
              }}>
                {r.label}
              </span>
              <span className="dim" style={{
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'right',
                fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>{r.sub}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
