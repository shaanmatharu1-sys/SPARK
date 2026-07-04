import { useEffect, useRef, useState, useCallback } from 'react'

const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]

function storageKey(symbol) { return `chart_drawings:${symbol}` }

function loadDrawings(symbol) {
  try { return JSON.parse(localStorage.getItem(storageKey(symbol)) || '[]') } catch { return [] }
}
function saveDrawings(symbol, drawings) {
  try { localStorage.setItem(storageKey(symbol), JSON.stringify(drawings)) } catch { /* storage full/unavailable — drop silently */ }
}

/**
 * Drawing-tools state + canvas renderer, shared between the toolbar (in the
 * panel header) and the overlay canvas (on top of the chart). Uses the
 * chart's own coordinate-conversion methods (time<->x, price<->y) rather
 * than hand-rolled projection math, but otherwise mirrors the click-to-place
 * / redraw-on-pan-zoom pattern already proven in SupplyMap.jsx's canvas.
 */
export function useDrawingTools(chartRef, seriesRef, containerRef, symbol) {
  const canvasRef = useRef(null)
  const [drawings, setDrawings] = useState(() => loadDrawings(symbol))
  const [activeTool, setActiveTool] = useState(null)
  const pendingRef = useRef(null) // first click of a two-click drawing (trend/fib)

  useEffect(() => { setDrawings(loadDrawings(symbol)); pendingRef.current = null }, [symbol])
  useEffect(() => { saveDrawings(symbol, drawings) }, [symbol, drawings])

  const redraw = useCallback(() => {
    const canvas = canvasRef.current, chart = chartRef.current, series = seriesRef.current
    const container = containerRef.current
    if (!canvas || !chart || !series || !container) return
    const W = canvas.width  = container.clientWidth
    const H = canvas.height = container.clientHeight
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, W, H)

    const toXY = (time, price) => {
      const x = chart.timeScale().timeToCoordinate(time)
      const y = series.priceToCoordinate(price)
      return (x == null || y == null) ? null : { x, y }
    }

    ctx.font = '10px IBM Plex Mono, monospace'
    for (const d of drawings) {
      if (d.type === 'trend') {
        const p1 = toXY(d.t1, d.p1), p2 = toXY(d.t2, d.p2)
        if (!p1 || !p2) continue
        ctx.strokeStyle = '#E0C168' // var(--gold-bright)
        ctx.lineWidth = 1.5
        ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke()
      } else if (d.type === 'ray') {
        const p1 = toXY(d.t1, d.p1)
        if (!p1) continue
        ctx.strokeStyle = '#6BA3D4' // var(--steel-bright)
        ctx.lineWidth = 1.5
        ctx.setLineDash([5, 3])
        ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(W, p1.y); ctx.stroke()
        ctx.setLineDash([])
        ctx.fillStyle = '#6BA3D4'
        ctx.fillText(d.p1.toFixed(2), p1.x + 4, p1.y - 4)
      } else if (d.type === 'fib') {
        const p1 = toXY(d.t1, d.p1), p2 = toXY(d.t2, d.p2)
        if (!p1 || !p2) continue
        const xLo = Math.min(p1.x, p2.x), xHi = Math.max(p1.x, p2.x)
        for (const level of FIB_LEVELS) {
          const price = d.p1 + level * (d.p2 - d.p1)
          const y = series.priceToCoordinate(price)
          if (y == null) continue
          ctx.strokeStyle = 'rgba(155,139,212,0.6)' // var(--purple)
          ctx.lineWidth = 1
          ctx.beginPath(); ctx.moveTo(xLo, y); ctx.lineTo(xHi, y); ctx.stroke()
          ctx.fillStyle = '#9B8Bd4'
          ctx.fillText(`${(level * 100).toFixed(1)}% ${price.toFixed(2)}`, xHi + 4, y + 3)
        }
      }
    }

    if (pendingRef.current) {
      const p = toXY(pendingRef.current.t1, pendingRef.current.p1)
      if (p) {
        ctx.fillStyle = '#E0C168'
        ctx.beginPath(); ctx.arc(p.x, p.y, 3, 0, Math.PI * 2); ctx.fill()
      }
    }
  }, [drawings, chartRef, seriesRef, containerRef])

  useEffect(() => {
    redraw()
    const chart = chartRef.current
    if (!chart) return
    chart.timeScale().subscribeVisibleLogicalRangeChange(redraw)
    const ro = new ResizeObserver(redraw)
    if (containerRef.current) ro.observe(containerRef.current)
    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(redraw)
      ro.disconnect()
    }
  }, [redraw, chartRef, containerRef])

  const onCanvasClick = (ev) => {
    if (!activeTool) return
    const chart = chartRef.current, series = seriesRef.current
    if (!chart || !series) return
    const rect = canvasRef.current.getBoundingClientRect()
    const x = ev.clientX - rect.left, y = ev.clientY - rect.top
    const time = chart.timeScale().coordinateToTime(x)
    const price = series.coordinateToPrice(y)
    if (time == null || price == null) return

    if (activeTool === 'ray') {
      setDrawings(d => [...d, { type: 'ray', t1: time, p1: price }])
      setActiveTool(null)
      return
    }
    if (!pendingRef.current) {
      pendingRef.current = { t1: time, p1: price }
      redraw()
    } else {
      const { t1, p1 } = pendingRef.current
      setDrawings(d => [...d, { type: activeTool, t1, p1, t2: time, p2: price }])
      pendingRef.current = null
      setActiveTool(null)
    }
  }

  const selectTool = (key) => {
    pendingRef.current = null
    setActiveTool(t => (t === key ? null : key))
  }

  const clearDrawings = () => { setDrawings([]); pendingRef.current = null }

  return { canvasRef, activeTool, selectTool, drawings, clearDrawings, onCanvasClick }
}
