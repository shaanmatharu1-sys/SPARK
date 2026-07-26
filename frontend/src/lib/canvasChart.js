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
const AXIS_RIGHT_WIDTH = 60    // gutter reserved for price/value labels
const AXIS_BOTTOM_HEIGHT = 22  // gutter reserved for date/time labels

export function createChartEngine(canvas, colors) {
  let bars = []
  let mode = 'candle'        // 'candle' | 'bar' | 'line'
  let showVolume = true
  let overlays = []          // [{ color, points: [{t, v}] }] — drawn on the main price scale
  let compareSeries = null   // { color, points: [{t, v}] } — own normalized scale, drawn over the main pane
  let subPanes = []          // [{ label, series: [{ type: 'line'|'histogram', color, points, upColor?, downColor? }] }]

  let W = 0, H = 0
  let plotW = 0, plotH = 0   // chart-plotting area, excluding the axis gutters
  let barSpacing = 8
  let rightIndex = 0         // fractional index of the rightmost visible bar
  let barIntervalSeconds = 86400 // per-bar granularity, drives time-axis label format
  let hover = null           // { x, y } in canvas px, or null
  let dragStart = null       // { x, rightIndex }
  let mainRangeCache = { min: 0, max: 1 }
  let subPaneRangesCache = []

  const redrawListeners = new Set()
  const hoverListeners = new Set()

  function notifyRedraw() { for (const fn of redrawListeners) fn() }

  // ── Layout: main pane (+ volume strip at its bottom) + stacked sub-panes ──
  function layout() {
    const subCount = subPanes.length
    const subTotal = Math.min(subCount * SUBPANE_FRACTION, 1 - MIN_MAIN_FRACTION)
    const mainH = plotH * (1 - subTotal)
    const subH = subCount ? (plotH - mainH) / subCount : 0
    const panes = [{ top: 0, height: mainH, isMain: true }]
    for (let i = 0; i < subCount; i++) {
      panes.push({ top: mainH + i * subH, height: subH, isMain: false, index: i })
    }
    return { mainH, subH, panes }
  }

  function usableHeightFor(pane) {
    return pane.isMain && showVolume ? pane.height * (1 - VOLUME_FRACTION) : pane.height
  }

  function visibleIndexRange() {
    const barsVisible = plotW / barSpacing
    const lo = Math.max(0, Math.floor(rightIndex - barsVisible))
    const hi = Math.min(bars.length - 1, Math.ceil(rightIndex))
    return { lo, hi }
  }

  function indexToX(idx) { return plotW - (rightIndex - idx) * barSpacing }
  function xToIndex(x) { return rightIndex - (plotW - x) / barSpacing }

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
    const usableH = usableHeightFor(pane)
    return pane.top + (range.max - p) / (range.max - range.min) * usableH
  }
  function yToPriceIn(y, range, pane) {
    const usableH = usableHeightFor(pane)
    return range.max - (y - pane.top) / usableH * (range.max - range.min)
  }

  // Public price<->y only operates on the MAIN pane's price scale (matches
  // the lightweight-charts API shape ChartDrawingLayer.jsx already calls).
  function priceToY(p) { return priceToYIn(p, mainRangeCache, layout().panes[0]) }
  function yToPrice(y) { return yToPriceIn(y, mainRangeCache, layout().panes[0]) }

  function formatAxisValue(v, span) {
    if (v == null || isNaN(v)) return ''
    if (span < 1) return v.toFixed(4)
    if (span >= 1000) return v.toFixed(0)
    return v.toFixed(2)
  }

  function formatTimeLabel(t) {
    const d = new Date(t * 1000)
    if (barIntervalSeconds < 86400) {
      return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: false })
    }
    if (barIntervalSeconds < 86400 * 25) {
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }
    return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
  }

  function computeTimeTicks(lo, hi) {
    const minPxPerLabel = 80
    const stepBars = Math.max(1, Math.round(minPxPerLabel / barSpacing))
    const ticks = []
    const start = Math.ceil(lo / stepBars) * stepBars
    for (let i = start; i <= hi; i += stepBars) {
      if (i < 0 || i >= bars.length) continue
      const x = indexToX(i)
      if (x < 0 || x > plotW) continue
      ticks.push({ i, x })
    }
    return ticks
  }

  function draw() {
    if (!canvas || !bars.length) return
    const ctx = canvas.getContext('2d')
    W = canvas.width = canvas.clientWidth
    H = canvas.height = canvas.clientHeight
    plotW = Math.max(0, W - AXIS_RIGHT_WIDTH)
    plotH = Math.max(0, H - AXIS_BOTTOM_HEIGHT)
    ctx.clearRect(0, 0, W, H)

    const { lo, hi } = visibleIndexRange()
    if (hi < lo) return
    const { panes } = layout()
    const mainPane = panes[0]
    // compareSeries has its own separately-scaled range (drawCompare), so it's
    // excluded here — only overlays sharing the main price scale count.
    const extraForRange = overlays.flatMap(o => o.points.filter(p => p.t >= bars[lo].t && p.t <= bars[hi].t))
    mainRangeCache = priceRangeFor(lo, hi, extraForRange)
    subPaneRangesCache = []

    const ticks = computeTimeTicks(lo, hi)
    drawVerticalGrid(ctx, ticks)
    drawPaneAxis(ctx, mainPane, mainRangeCache)
    if (showVolume) drawVolume(ctx, mainPane, lo, hi)
    drawSeries(ctx, mainPane, lo, hi)
    for (const o of overlays) drawLine(ctx, mainPane, mainRangeCache, o.points, o.color)
    if (compareSeries) drawCompare(ctx, mainPane, compareSeries)

    panes.slice(1).forEach((pane, i) => drawSubPane(ctx, pane, subPanes[i], lo, hi))

    drawTimeAxisLabels(ctx, ticks)
    if (hover) drawCrosshair(ctx, panes)
  }

  function drawVerticalGrid(ctx, ticks) {
    ctx.strokeStyle = colors.grid
    ctx.lineWidth = 1
    for (const t of ticks) {
      ctx.beginPath(); ctx.moveTo(t.x, 0); ctx.lineTo(t.x, plotH); ctx.stroke()
    }
  }

  function drawPaneAxis(ctx, pane, range) {
    const usableH = usableHeightFor(pane)
    const nLines = 4
    ctx.strokeStyle = colors.grid
    ctx.lineWidth = 1
    ctx.font = '9px IBM Plex Mono, monospace'
    for (let i = 0; i <= nLines; i++) {
      const frac = i / nLines
      const y = pane.top + frac * usableH
      const price = range.max - frac * (range.max - range.min)
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(plotW, y); ctx.stroke()
      ctx.fillStyle = colors.dimText
      ctx.fillText(formatAxisValue(price, range.max - range.min), plotW + 4, y + 3)
    }
  }

  function drawTimeAxisLabels(ctx, ticks) {
    ctx.strokeStyle = colors.border
    ctx.beginPath(); ctx.moveTo(0, plotH); ctx.lineTo(plotW, plotH); ctx.stroke()
    ctx.font = '9px IBM Plex Mono, monospace'
    for (const t of ticks) {
      const label = formatTimeLabel(bars[t.i].t)
      const textW = ctx.measureText(label).width
      const x = Math.min(Math.max(t.x - textW / 2, 2), plotW - textW - 2)
      ctx.fillStyle = colors.dimText
      ctx.fillText(label, x, plotH + 14)
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
    subPaneRangesCache[pane.index] = range
    drawPaneAxis(ctx, pane, range)

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

  function drawCrosshair(ctx, panes) {
    const { x, y } = hover
    if (x < 0 || x > plotW || y < 0 || y > plotH) return
    ctx.strokeStyle = colors.crosshair
    ctx.setLineDash([3, 3])
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, plotH); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(plotW, y); ctx.stroke()
    ctx.setLineDash([])

    const idx = Math.round(Math.min(bars.length - 1, Math.max(0, xToIndex(x))))
    const b = bars[idx]
    if (!b) return

    // Value label in the right gutter, scaled to whichever pane the cursor
    // is actually over (main price scale, or a sub-pane's own RSI/MACD scale).
    let hoveredPane = panes[0], hoveredRange = mainRangeCache
    for (const p of panes) {
      if (y >= p.top && y <= p.top + p.height) {
        hoveredPane = p
        hoveredRange = p.isMain ? mainRangeCache : (subPaneRangesCache[p.index] || { min: 0, max: 1 })
        break
      }
    }
    const value = yToPriceIn(y, hoveredRange, hoveredPane)
    const label = formatAxisValue(value, hoveredRange.max - hoveredRange.min)
    ctx.font = '10px IBM Plex Mono, monospace'
    ctx.fillStyle = colors.crosshairLabelBg
    ctx.fillRect(plotW + 2, y - 8, AXIS_RIGHT_WIDTH - 4, 16)
    ctx.fillStyle = colors.text
    ctx.fillText(label, plotW + 6, y + 4)

    // Time label in the bottom gutter, under the cursor.
    const timeLabel = formatTimeLabel(b.t)
    const timeW = ctx.measureText(timeLabel).width
    const tx = Math.min(Math.max(x - timeW / 2 - 4, 0), plotW - timeW - 4)
    ctx.fillStyle = colors.crosshairLabelBg
    ctx.fillRect(tx, plotH + 2, timeW + 8, 16)
    ctx.fillStyle = colors.text
    ctx.fillText(timeLabel, tx + 4, plotH + 14)

    // OHLC readout, top-left of the main pane.
    const d = new Date(b.t * 1000)
    const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
      (b.t % 86400 !== 0 ? ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) : '')
    ctx.font = '10px IBM Plex Mono, monospace'
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
    rightIndex = idxUnderCursor + (plotW - mx) / barSpacing
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
    const barsVisible = plotW / barSpacing
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
      barIntervalSeconds = bars.length > 1 ? Math.max(1, bars[bars.length - 1].t - bars[bars.length - 2].t) : 86400
      rightIndex = bars.length - 1
      const availW = Math.max(0, (canvas.clientWidth || W) - AXIS_RIGHT_WIDTH)
      barSpacing = Math.max(MIN_BAR_SPACING, Math.min(MAX_BAR_SPACING, availW / Math.max(1, Math.min(bars.length, 150))))
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
