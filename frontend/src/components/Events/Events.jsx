import React from 'react'
import { useEvents } from '../../hooks/useMarketData'

const IMP_COLOR = { high: 'var(--red)', med: 'var(--gold)', low: 'var(--text-dim)' }

function dayLabel(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  const today = new Date(); today.setHours(0,0,0,0)
  const diff = Math.round((d - today) / 86400000)
  const wd = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  if (diff === 0) return `${wd} · TODAY`
  if (diff === 1) return `${wd} · tomorrow`
  if (diff < 0) return `${wd} · ${-diff}d ago`
  return `${wd} · in ${diff}d`
}

export default function Events() {
  const { data, loading } = useEvents()

  const econ = data?.economic?.events || []
  const earnings = data?.earnings?.earnings || []

  // Merge and group by date
  const all = [...econ, ...earnings].sort((a, b) => a.date.localeCompare(b.date))
  const byDate = {}
  for (const e of all) (byDate[e.date] ||= []).push(e)
  const dates = Object.keys(byDate).sort()

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 6, height: '100%', minHeight: 0 }}>
      {/* Timeline */}
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">Events Calendar</span></div>
        <div className="panel-body" style={{ padding: '8px 14px' }}>
          {loading && <div className="dim" style={{ fontSize: 11 }}>Loading calendar…</div>}
          {!loading && dates.length === 0 &&
            <div className="dim" style={{ fontSize: 11 }}>No upcoming events found.</div>}
          {dates.map(date => (
            <div key={date} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold-bright)',
                            letterSpacing: '0.05em', marginBottom: 4,
                            borderBottom: '1px solid var(--border-bright)', paddingBottom: 3 }}>
                {dayLabel(date)}
              </div>
              {byDate[date].map((e, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0' }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%',
                                 background: IMP_COLOR[e.importance] || 'var(--text-dim)', flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: 'var(--text)' }}>{e.name}</span>
                  <span className="dim" style={{ fontSize: 9, marginLeft: 'auto',
                          textTransform: 'uppercase', letterSpacing: '0.05em' }}>{e.type}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* This week summary */}
      <div className="panel" style={{ minHeight: 0 }}>
        <div className="panel-header"><span className="title">High-Impact Ahead</span></div>
        <div className="panel-body" style={{ padding: '8px 14px' }}>
          {all.filter(e => e.importance === 'high').slice(0, 12).map((e, i) => (
            <div key={i} style={{ padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 12, color: 'var(--text)' }}>{e.name}</div>
              <div className="dim" style={{ fontSize: 10 }}>{dayLabel(e.date)}</div>
            </div>
          ))}
          {all.filter(e => e.importance === 'high').length === 0 && !loading &&
            <div className="dim" style={{ fontSize: 11 }}>No high-impact events in window.</div>}
          <div className="dim" style={{ fontSize: 9, marginTop: 10, lineHeight: 1.5 }}>
            Economic releases via FRED official schedules. Earnings via Polygon (best-effort).
            Red = high impact, gold = medium.
          </div>
        </div>
      </div>
    </div>
  )
}
