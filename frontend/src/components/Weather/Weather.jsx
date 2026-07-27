import React, { useState, useMemo } from 'react'
import { useWeatherRegions } from '../../hooks/useMarketData'

// Weather-driven commodity research: every region is tagged with the
// futures contract(s) it's a trading signal for (drought in Iowa -> corn/
// soy, freezes in the Permian -> WTI, etc — see backend/services/
// weather_client.py's REGIONS dict for the full rationale). This is
// deliberately not a generic weather widget.

const anomalyColor = (v) => v == null ? 'var(--text-dim)' : v > 0 ? 'var(--red)' : v < 0 ? 'var(--steel-bright)' : 'var(--text)'
const precipAnomalyColor = (v) => v == null ? 'var(--text-dim)' : v > 15 ? 'var(--steel-bright)' : v < -15 ? 'var(--red)' : 'var(--text)'

function ForecastStrip({ days }) {
  if (!days?.length) return null
  return (
    <div style={{ display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 2 }}>
      {days.map(d => (
        <div key={d.date} style={{
          flex: '0 0 auto', minWidth: 46, textAlign: 'center', padding: '4px 3px',
          background: 'var(--bg-base)', borderRadius: 4,
        }}>
          <div className="dim" style={{ fontSize: 8 }}>
            {new Date(d.date + 'T00:00').toLocaleDateString(undefined, { weekday: 'short' })}
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-primary)' }}>
            {d.temp_max_f != null ? Math.round(d.temp_max_f) : '—'}°
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)' }}>
            {d.temp_min_f != null ? Math.round(d.temp_min_f) : '—'}°
          </div>
          {d.precip_prob_pct != null && d.precip_prob_pct >= 20 && (
            <div style={{ fontSize: 8, color: 'var(--steel-bright)' }}>{Math.round(d.precip_prob_pct)}%</div>
          )}
        </div>
      ))}
    </div>
  )
}

function FuturesBadges({ futures, note }) {
  if (!futures?.length) {
    return note ? <span className="dim" style={{ fontSize: 9, fontStyle: 'italic' }}>{note}</span> : null
  }
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {futures.map(f => (
        <span key={f} style={{
          fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
          color: 'var(--gold-bright)', background: 'var(--bg-base)',
          border: '1px solid var(--border-bright)', borderRadius: 3, padding: '1px 6px',
        }}>
          {f}
        </span>
      ))}
    </div>
  )
}

function RegionCard({ r }) {
  if (!r.available) {
    return (
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">{r.name}</span></div>
        <div className="panel-body" style={{ padding: 10 }}>
          <div className="dim" style={{ fontSize: 10 }}>{r.reason || 'Unavailable'}</div>
        </div>
      </div>
    )
  }
  const a = r.anomaly
  return (
    <div className="panel" style={{ minHeight: 0 }}>
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: 4 }}>
        <span className="title">{r.name}</span>
        <FuturesBadges futures={r.futures} note={r.futures_note} />
      </div>
      <div className="panel-body" style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>
              {r.current.temp_f != null ? Math.round(r.current.temp_f) : '—'}°F
            </span>
            <span className="dim" style={{ fontSize: 10, marginLeft: 8 }}>{r.current.condition}</span>
          </div>
          <div className="dim" style={{ fontSize: 9, textAlign: 'right' }}>
            {r.current.wind_mph != null && <div>{Math.round(r.current.wind_mph)} mph wind</div>}
            {r.current.precip_in > 0 && <div>{r.current.precip_in.toFixed(2)}" now</div>}
          </div>
        </div>

        {a && (
          <div style={{ display: 'flex', gap: 14, fontSize: 10, fontFamily: 'var(--font-mono)' }}>
            <span>
              <span className="dim" style={{ fontFamily: 'var(--font-body)' }}>Temp vs normal: </span>
              <span style={{ color: anomalyColor(a.temp_vs_normal_f), fontWeight: 700 }}>
                {a.temp_vs_normal_f == null ? '—' : `${a.temp_vs_normal_f > 0 ? '+' : ''}${a.temp_vs_normal_f}°F`}
              </span>
            </span>
            <span>
              <span className="dim" style={{ fontFamily: 'var(--font-body)' }}>7d precip vs normal: </span>
              <span style={{ color: precipAnomalyColor(a.precip_vs_normal_pct), fontWeight: 700 }}>
                {a.precip_vs_normal_pct == null ? '—' : `${a.precip_vs_normal_pct > 0 ? '+' : ''}${a.precip_vs_normal_pct}%`}
              </span>
            </span>
          </div>
        )}

        <ForecastStrip days={r.forecast_7d} />

        <div className="dim" style={{ fontSize: 9, lineHeight: 1.4 }}>{r.risk}</div>
      </div>
    </div>
  )
}

export default function Weather() {
  const { data, loading } = useWeatherRegions()
  const [filter, setFilter] = useState('all')

  const regions = data?.regions || []
  const linkedFutures = useMemo(() => (
    [...new Set(regions.flatMap(r => r.futures || []))].sort()
  ), [regions])

  const filtered = filter === 'all' ? regions : regions.filter(r => (r.futures || []).includes(filter))

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: 6 }}>
        <span className="title">Weather — Commodity Regions</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="dim" style={{ fontSize: 9 }}>Open-Meteo · 7d fcst · vs 10yr normal</span>
          <button className={`btn ${filter === 'all' ? 'active' : ''}`}
            style={{ fontSize: 9, padding: '2px 7px' }} onClick={() => setFilter('all')}>All</button>
          {linkedFutures.map(f => (
            <button key={f} className={`btn ${filter === f ? 'active' : ''}`}
              style={{ fontSize: 9, padding: '2px 7px' }} onClick={() => setFilter(f)}>
              {f}
            </button>
          ))}
        </div>
      </div>
      <div className="panel-body" style={{ padding: 8, overflowY: 'auto' }}>
        {loading && <div className="dim" style={{ fontSize: 11, padding: 8 }}>Loading regional conditions…</div>}
        {!loading && (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 8, alignItems: 'start',
          }}>
            {filtered.map(r => <RegionCard key={r.region_key} r={r} />)}
          </div>
        )}
      </div>
    </div>
  )
}
