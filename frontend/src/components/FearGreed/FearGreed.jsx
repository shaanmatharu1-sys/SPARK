import React from 'react'
import { useFearGreed } from '../../hooks/useMarketData'

function GaugeMeter({ score }) {
  const angle = ((score / 100) * 180) - 90  // -90 to +90 degrees
  const color = score < 25 ? '#ff3d57'
              : score < 45 ? '#ff8c00'
              : score < 55 ? '#f0a500'
              : score < 75 ? '#7cb342'
              : '#00c853'

  return (
    <div style={{ textAlign: 'center', padding: '12px 0' }}>
      <svg viewBox="0 0 120 70" width="160" height="90">
        {/* Arc background */}
        <path d="M10,65 A55,55 0 0,1 110,65" fill="none" stroke="#1c2333" strokeWidth="8" />
        {/* Colored arc */}
        <path d="M10,65 A55,55 0 0,1 110,65" fill="none" stroke={color}
              strokeWidth="8" strokeDasharray={`${(score / 100) * 172} 172`} />
        {/* Needle */}
        <line
          x1="60" y1="65"
          x2={60 + 45 * Math.cos((angle - 90) * Math.PI / 180)}
          y2={65 + 45 * Math.sin((angle - 90) * Math.PI / 180)}
          stroke={color} strokeWidth="2" strokeLinecap="round"
        />
        <circle cx="60" cy="65" r="3" fill={color} />
        {/* Score */}
        <text x="60" y="55" textAnchor="middle" fill={color}
              fontSize="18" fontWeight="bold" fontFamily="Courier New">
          {Math.round(score)}
        </text>
      </svg>
    </div>
  )
}

export default function FearGreed() {
  const { data, loading } = useFearGreed()

  const score   = data?.score || 50
  const rating  = data?.rating || '—'
  const inds    = data?.indicators || {}

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Fear &amp; Greed</span>
        <span className="dim" style={{ fontSize: 9 }}>CNN</span>
      </div>
      <div className="panel-body">
        {loading ? (
          <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading...</div>
        ) : (
          <>
            <GaugeMeter score={score} />
            <div style={{ textAlign: 'center', marginBottom: 12, fontSize: 13,
                          color: 'var(--yellow)', fontWeight: 'bold' }}>
              {rating}
            </div>
            <div style={{ padding: '0 10px' }}>
              {Object.entries(inds).map(([key, val]) => (
                <div key={key} style={{ display: 'flex', justifyContent: 'space-between',
                                        padding: '3px 0', borderBottom: '1px solid #0f151e' }}>
                  <span className="dim" style={{ fontSize: 9, textTransform: 'uppercase' }}>
                    {key.replace(/_/g, ' ')}
                  </span>
                  <span style={{ fontSize: 10, color: val > 50 ? 'var(--green)' : 'var(--red)' }}>
                    {val != null ? Math.round(val) : '—'}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
