// lib/canvasChart.js — dependency-free canvas price-chart engine.
//
// Replaces lightweight-charts. Mirrors the coordinate-transform / drag-pan /
// wheel-zoom pattern already proven in SupplyMap.jsx's VesselMap (view state
// as {scale, tx/rightIndex}, cursor-centered zoom, redraw-on-resize), applied
// to a categorical (index-based, not continuous-time) x-axis — the standard
// approach for financial charts so weekends/closed-market gaps don't appear
// as empty space.
//
// Bars are {t (unix seconds), o, h, l, c, v}. All colors are passed in by
// the caller (mirrors the "hardcode hex, comment which var it mirrors"
// convention used elsewhere in this codebase's canvas components, since
// canvas can't read CSS custom properties).

const MIN_BAR_SPACING = 2
const MAX_BAR_SPACING = 40
const VOLUME_FRACTION = 0.18   // bottom slice of the main pane reserved for volume
const SUBPANE_FRACTION = 0.22  // height fraction per indicator sub-pane (RSI, MACD)
const MIN_MAIN_FRACTION = 0.4  // main pane never shrinks below this, however many sub-panes are active

export function createChartEngine(canvas, colors) {
  let bars = []
  let mode = 'candle'        // 'candle' | 'bar' | 'line'
  let showVolume = true
  let overlays = []          // [{ color, points: [{t, v}] }] — drawn on the main price scale
  let compareSeries = null   // { color, points: [{t, v}] } — own normalized scale, drawn over the main pane
  let subPanes = []          // [{ label, series: [{ type: 'line'|'histogram', color, points, upColor?, downColor? }] }]

  let W = 0, H = 0
  let barSpacing = 8
  let rightIndex = 0         // fractional index of the rightmost visible bar
  let hover = null           // { x, y } in canvas px, or null
  let dragStart = null       // { x, rightIndex }

  const redrawListeners = new Set()
  const hoverListeners = new Set()

  function notifyRedraw() { for (const fn of redrawListeners) fn() }

  // ── Layout: main pane (+ volume strip at its bottom) + stacked sub-panes ──
  function layout() {
    const subCount = subPanes.length
    const subTotal = Math.min(subCount * SUBPANE_FRACTION, 1 - MIN_MAIN_FRACTION)
    const mainH = H * (1 - subTotal)
    const subH = subCount ? (H - mainH) / subCount : 0
    const panes = [{ top: 0, height: mainH, isMain: true }]
    for (let i = 0; i < subCount; i++) {
      panes.push({ top: mainH + i * subH, height: subH, isMain: false, index: i })
    }
    return { mainH, subH, panes }
  }

  function visibleIndexRange() {
    const barsVisible = W / barSpacing
    const lo = Math.max(0, Math.floor(rightIndex - barsVisible))
    const hi = Math.min(bars.length - 1, Math.ceil(rightIndex))
    return { lo, hi }
  }

  function indexToX(idx) { return W - (rightIndex - idx) * barSpacing }
  function xToIndex(x) { return rightIndex - (W - x) / barSpacing }

  function timeToX(t) {
    if (!bars.length) return null
    const idx = nearestIndexForTime(t)
    if (idx == null) return null
    return indexToX(idx)
  }
  function xToTime(x) {
    if (!bars.length) return null
    const idx = Math.round(Math.min(bars.length - 1, Math.max(0, xToIndex(x))))
    return bars[idx]?.t ?? null
  }
  function nearestIndexForTime(t) {
    if (!bars.length) return null
    // Bars are sorted ascending by time — binary search for nearest.
    let lo = 0, hi = bars.length - 1
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (bars[mid].t < t) lo = mid + 1; else hi = mid
    }
    return lo
  }

  function priceRangeFor(lo, hi, extra) {
    let min = Infinity, max = -Infinity
    for (let i = lo; i <= hi; i++) {
      const b = bars[i]
      if (b.l < min) min = b.l
      if (b.h > max) max = b.h
    }
    for (const pt of extra || []) {
      if (pt.v == null || isNaN(pt.v)) continue
      if (pt.v < min) min = pt.v
      if (pt.v > max) max = pt.v
    }
    if (!isFinite(min) || !isFinite(max)) return { min: 0, max: 1 }
    if (min === max) { min -= 1; max += 1 }
    const pad = (max - min) * 0.08
    return { min: min - pad, max: max + pad }
  }

  function priceToYIn(p, range, pane) {
    const usableH = pane.isMain && showVolume ? pane.height * (1 - VOLUME_FRACTION) : pane.height
    return pane.top + (range.max - p) / (range.max - range.min) * usableH
  }
  function yToPriceIn(y, range, pane) {
    const usableH = pane.isMain && showVolume ? pane.height * (1 - VOLUME_FRACTION) : pane.height
    return range.max - (y - pane.top) / usableH * (range.max - range.min)
  }

  // Public price<->y only operates on the MAIN pane's price scale (matches
  // the lightweight-charts API shape ChartDrawingLayer.jsx already calls).
  let mainRangeCache = { min: 0, max: 1 }
  function priceToY(p) { return priceToYIn(p, mainRangeCache, layout().panes[0]) }
  function yToPrice(y) { return yToPriceIn(y, mainRangeCache, layout().panes[0]) }

  function draw() {
    if (!canvas || !bars.length) return
    const ctx = canvas.getContext('2d')
    W = canvas.width = canvas.clientWidth
    H = canvas.height = canvas.clientHeight
    ctx.clearRect(0, 0, W, H)

    const { lo, hi } = visibleIndexRange()
    if (hi < lo) return
    const { panes } = layout()
    const mainPane = panes[0]
    // compareSeries has its own separately-scaled range (drawCompare), so it's
    // excluded here — only overlays sharing the main price scale count.
    const extraForRange = overlays.flatMap(o => o.points.filter(p => p.t >= bars[lo].t && p.t <= bars[hi].t))
    mainRangeCache = priceRangeFor(lo, hi, extraForRange)

    drawGrid(ctx, mainPane)
    if (showVolume) drawVolume(ctx, mainPane, lo, hi)
    drawSeries(ctx, mainPane, lo, hi)
    for (const o of overlays) drawLine(ctx, mainPane, mainRangeCache, o.points, o.color)
    if (compareSeries) drawCompare(ctx, mainPane, compareSeries)

    panes.slice(1).forEach((pane, i) => drawSubPane(ctx, pane, subPanes[i], lo, hi))

    if (hover) drawCrosshair(ctx, mainPane, panes)
  }

  function drawGrid(ctx, pane) {
    ctx.strokeStyle = colors.grid
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = pane.top + (pane.height / 4) * i
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
    }
  }

  function barWidth() { return Math.max(1, barSpacing * 0.6) }

  function drawSeries(ctx, pane, lo, hi) {
    if (mode === 'line') {
      const pts = []
      for (let i = lo; i <= hi; i++) pts.push({ t: bars[i].t, v: bars[i].c })
      drawLine(ctx, pane, mainRangeCache, pts, colors.line)
      return
    }
    const bw = barWidth()
    for (let i = lo; i <= hi; i++) {
      const b = bars[i]
      const x = indexToX(i)
      const up = b.c >= b.o
      const color = up ? colors.up : colors.down
      const yO = priceToYIn(b.o, mainRangeCache, pane)
      const yH = priceToYIn(b.h, mainRangeCache, pane)
      const yL = priceToYIn(b.l, mainRangeCache, pane)
      const yC = priceToYIn(b.c, mainRangeCache, pane)

      if (mode === 'candle') {
        ctx.strokeStyle = color
        ctx.lineWidth = 1
        ctx.beginPath(); ctx.moveTo(x, yH); ctx.lineTo(x, yL); ctx.stroke()
        ctx.fillStyle = color
        const top = Math.min(yO, yC), h = Math.max(1, Math.abs(yC - yO))
        ctx.fillRect(x - bw / 2, top, bw, h)
      } else if (mode === 'bar') {
        ctx.strokeStyle = color
        ctx.lineWidth = 1.5
        ctx.beginPath(); ctx.moveTo(x, yH); ctx.lineTo(x, yL); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(x - bw / 2, yO); ctx.lineTo(x, yO); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(x, yC); ctx.lineTo(x + bw / 2, yC); ctx.stroke()
      }
    }
  }

  function drawVolume(ctx, pane, lo, hi) {
    const volTop = pane.top + pane.height * (1 - VOLUME_FRACTION)
    const volH = pane.height * VOLUME_FRACTION
    let maxV = 0
    for (let i = lo; i <= hi; i++) maxV = Math.max(maxV, bars[i].v || 0)
    if (!maxV) return
    const bw = barWidth()
    for (let i = lo; i <= hi; i++) {
      const b = bars[i]
      const x = indexToX(i)
      const h = (b.v || 0) / maxV * volH
      ctx.fillStyle = b.c >= b.o ? colors.volUp : colors.volDown
      ctx.fillRect(x - bw / 2, volTop + volH - h, bw, h)
    }
  }

  function drawLine(ctx, pane, range, points, color) {
    if (!points.length) return
    ctx.strokeStyle = color
    ctx.lineWidth = 1.3
    ctx.beginPath()
    let started = false
    for (const pt of points) {
      if (pt.v == null || isNaN(pt.v)) { started = false; continue }
      const idx = nearestIndexForTime(pt.t)
      if (idx == null) continue
      const x = indexToX(idx)
      const y = priceToYIn(pt.v, range, pane)
      if (!started) { ctx.moveTo(x, y); started = true } else { ctx.lineTo(x, y) }
    }
    ctx.stroke()
  }

  function drawCompare(ctx, pane, cmp) {
    const vals = cmp.points.map(p => p.v).filter(v => v != null && !isNaN(v))
    if (!vals.length) return
    let min = Math.min(...vals), max = Math.max(...vals)
    if (min === max) { min -= 1; max += 1 }
    const pad = (max - min) * 0.1
    const range = { min: min - pad, max: max + pad }
    drawLine(ctx, pane, range, cmp.points, cmp.color)
  }

  function drawSubPane(ctx, pane, spec, lo, hi) {
    if (!spec) return
    ctx.strokeStyle = colors.border
    ctx.beginPath(); ctx.moveTo(0, pane.top); ctx.lineTo(W, pane.top); ctx.stroke()

    const allPts = spec.series.flatMap(s => s.points.filter(p => bars[lo] && bars[hi] && p.t >= bars[lo].t && p.t <= bars[hi].t))
    const vals = allPts.map(p => p.v).filter(v => v != null && !isNaN(v))
    let range = { min: 0, max: 1 }
    if (vals.length) {
      let min = Math.min(...vals), max = Math.max(...vals)
      if (min === max) { min -= 1; max += 1 }
      const pad = (max - min) * 0.15
      range = { min: min - pad, max: max + pad }
    }

    const bw = barWidth()
    for (const s of spec.series) {
      if (s.type === 'histogram') {
        for (const pt of s.points) {
          if (pt.v == null || isNaN(pt.v)) continue
          const idx = nearestIndexForTime(pt.t)
          if (idx == null || idx < lo || idx > hi) continue
          const x = indexToX(idx)
          const yZero = priceToYIn(0, range, pane)
          const y = priceToYIn(pt.v, range, pane)
          ctx.fillStyle = pt.v >= 0 ? (s.upColor || colors.up) : (s.downColor || colors.down)
          ctx.fillRect(x - bw / 2, Math.min(y, yZero), bw, Math.max(1, Math.abs(y - yZero)))
        }
      } else {
        drawLine(ctx, pane, range, s.points, s.color)
      }
    }
    if (spec.label) {
      ctx.fillStyle = colors.dimText
      ctx.font = '9px IBM Plex Mono, monospace'
      ctx.fillText(spec.label, 4, pane.top + 10)
    }
  }

  function drawCrosshair(ctx, mainPane, panes) {
    const { x, y } = hover
    ctx.strokeStyle = colors.crosshair
    ctx.setLineDash([3, 3])
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
    ctx.setLineDash([])

    const idx = Math.round(Math.min(bars.length - 1, Math.max(0, xToIndex(x))))
    const b = bars[idx]
    if (!b) return

    // Price label at cursor height, OHLC readout top-left of the main pane.
    const price = yToPriceIn(y, mainRangeCache, mainPane)
    ctx.font = '10px IBM Plex Mono, monospace'
    const label = price.toFixed(2)
    ctx.fillStyle = colors.crosshairLabelBg
    ctx.fillRect(W - 54, y - 8, 52, 16)
    ctx.fillStyle = colors.text
    ctx.fillText(label, W - 50, y + 4)

    const d = new Date(b.t * 1000)
    const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
      (b.t % 86400 !== 0 ? ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) : '')
    ctx.fillStyle = colors.dimText
    ctx.fillText(
      `O ${b.o.toFixed(2)}  H ${b.h.toFixed(2)}  L ${b.l.toFixed(2)}  C ${b.c.toFixed(2)}  ${dateStr}`,
      6, 12
    )
  }

  // ── Interaction: wheel zoom (cursor-centered), drag pan, hover crosshair ──
  function onWheel(ev) {
    ev.preventDefault()
    const rect = canvas.getBoundingClientRect()
    const mx = ev.clientX - rect.left
    const idxUnderCursor = xToIndex(mx)
    const factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15
    barSpacing = Math.max(MIN_BAR_SPACING, Math.min(MAX_BAR_SPACING, barSpacing * factor))
    rightIndex = idxUnderCursor + (W - mx) / barSpacing
    clampView()
    draw()
    notifyRedraw()
  }
  function onMouseDown(ev) {
    const rect = canvas.getBoundingClientRect()
    dragStart = { x: ev.clientX - rect.left, rightIndex }
  }
  function onMouseMove(ev) {
    const rect = canvas.getBoundingClientRect()
    const x = ev.clientX - rect.left, y = ev.clientY - rect.top
    if (dragStart) {
      rightIndex = dragStart.rightIndex - (x - dragStart.x) / barSpacing
      clampView()
      notifyRedraw()
    }
    hover = { x, y }
    for (const fn of hoverListeners) fn(hover)
    draw()
  }
  function onMouseUp() { dragStart = null }
  function onMouseLeave() { dragStart = null; hover = null; draw() }

  function clampView() {
    if (!bars.length) return
    const barsVisible = W / barSpacing
    rightIndex = Math.max(barsVisible * 0.5, Math.min(bars.length - 1, rightIndex))
  }

  canvas.addEventListener('wheel', onWheel, { passive: false })
  canvas.addEventListener('mousedown', onMouseDown)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
  canvas.addEventListener('mouseleave', onMouseLeave)

  return {
    setData(newBars) {
      bars = newBars
      rightIndex = bars.length - 1
      barSpacing = Math.max(MIN_BAR_SPACING, Math.min(MAX_BAR_SPACING, W / Math.max(1, Math.min(bars.length, 150))))
      draw()
      notifyRedraw()
    },
    updateLastBar(bar) {
      if (!bars.length) return
      const last = bars[bars.length - 1]
      if (last.t === bar.t) bars[bars.length - 1] = bar
      else { bars.push(bar); rightIndex = bars.length - 1 }
      draw()
      notifyRedraw()
    },
    setMode(m) { mode = m; draw() },
    setShowVolume(b) { showVolume = b; draw() },
    setOverlays(arr) { overlays = arr; draw() },
    setCompareSeries(cmp) { compareSeries = cmp; draw() },
    setSubPanes(arr) { subPanes = arr; draw() },
    resize() { draw(); notifyRedraw() },
    draw,
    timeToX, xToTime, priceToY, yToPrice,
    subscribeRedraw(fn) { redrawListeners.add(fn) },
    unsubscribeRedraw(fn) { redrawListeners.delete(fn) },
    subscribeHover(fn) { hoverListeners.add(fn) },
    unsubscribeHover(fn) { hoverListeners.delete(fn) },
    destroy() {
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('mouseleave', onMouseLeave)
    },
  }
}
