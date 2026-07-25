import React, { useState, useEffect, useRef, useCallback } from 'react'
import PriceChart from '../Charts/PriceChart'
import SymbolSearch from '../common/SymbolSearch'
import { useWorkspace, workspaceApi } from '../../hooks/useMarketData'

const LAYOUTS = [
  { rows: 2, cols: 2, label: '2x2' },
  { rows: 2, cols: 3, label: '2x3' },
  { rows: 3, cols: 3, label: '3x3' },
]

function cellsForLayout(rows, cols, prevCells) {
  const bySlot = {}
  for (const c of prevCells || []) bySlot[`${c.row}-${c.col}`] = c
  const fallback = (prevCells || []).map(c => c.symbol)
  let fi = 0
  const out = []
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const existing = bySlot[`${r}-${c}`]
      out.push(existing || { row: r, col: c, symbol: fallback[fi++] || 'SPY', timeframe: '1D' })
    }
  }
  return out
}

export default function MultiChart() {
  const { data, loading } = useWorkspace()
  const [rows, setRows] = useState(2)
  const [cols, setCols] = useState(2)
  const [cells, setCells] = useState([])
  const initialized = useRef(false)
  const saveTimer = useRef(null)

  useEffect(() => {
    if (data && !initialized.current) {
      setRows(data.rows || 2)
      setCols(data.cols || 2)
      setCells(data.cells || [])
      initialized.current = true
    }
  }, [data])

  const persist = useCallback((r, c, cellList) => {
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      workspaceApi.set(r, c, cellList)
    }, 400)
  }, [])

  const setLayout = (r, c) => {
    const next = cellsForLayout(r, c, cells)
    setRows(r); setCols(c); setCells(next)
    persist(r, c, next)
  }

  const setCellSymbol = (row, col, symbol) => {
    const next = cells.map(cell => cell.row === row && cell.col === col ? { ...cell, symbol } : cell)
    setCells(next)
    persist(rows, cols, next)
  }

  if (loading && !initialized.current) {
    return <div className="panel" style={{ height: '100%' }}>
      <div className="panel-body" style={{ padding: 16, color: 'var(--text-dim)' }}>Loading workspace…</div>
    </div>
  }

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Multi-Chart Workspace</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {LAYOUTS.map(l => (
            <button key={l.label} className={`btn ${rows === l.rows && cols === l.cols ? 'active' : ''}`}
              onClick={() => setLayout(l.rows, l.cols)}>{l.label}</button>
          ))}
        </div>
      </div>
      <div className="panel-body" style={{ padding: 6 }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
          gap: 6, height: '100%', minHeight: 0,
        }}>
          {cells.map(cell => (
            <div key={`${cell.row}-${cell.col}`}
                 style={{ position: 'relative', minHeight: 0, minWidth: 0, overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: 6, right: 8, zIndex: 5 }}>
                <SymbolSearch
                  value={cell.symbol}
                  onChange={(v) => setCellSymbol(cell.row, cell.col, v)}
                  onSelect={(sym) => setCellSymbol(cell.row, cell.col, sym)}
                  width={100}
                />
              </div>
              <PriceChart symbol={cell.symbol} initialTimeframe={cell.timeframe} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
