// colorScale.js — magnitude-based background tinting for table cells.
// Uses CSS color-mix() against the existing theme vars (--green/--red/...)
// so the tint automatically follows whatever theme is active, instead of
// hardcoding hex values that would go stale the moment a theme changes.

export function heatBg(value, max = 5, posVar = '--green', negVar = '--red', capPct = 35) {
  if (value == null || !isFinite(value) || value === 0) return {}
  const pct = Math.min(Math.abs(value) / max, 1)
  const opacity = Math.round(pct * capPct)
  const varName = value > 0 ? posVar : negVar
  return { background: `color-mix(in srgb, var(${varName}) ${opacity}%, transparent)` }
}
