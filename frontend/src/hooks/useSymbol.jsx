import { createContext, useContext, useState, useCallback } from 'react'

/**
 * SymbolContext — one "active symbol" shared across all tabs.
 * The header input drives it; symbol-aware tabs read it and can update it,
 * so a ticker typed in one place follows you everywhere.
 */
const SymbolContext = createContext(null)

export function SymbolProvider({ children, initial = 'SPY' }) {
  const [symbol, setSymbolState] = useState(initial)

  const setSymbol = useCallback((s) => {
    if (!s) return
    setSymbolState(String(s).toUpperCase().trim())
  }, [])

  return (
    <SymbolContext.Provider value={{ symbol, setSymbol }}>
      {children}
    </SymbolContext.Provider>
  )
}

export function useSymbol() {
  const ctx = useContext(SymbolContext)
  if (!ctx) {
    // Fallback so components don't crash if rendered outside provider
    return { symbol: 'SPY', setSymbol: () => {} }
  }
  return ctx
}
