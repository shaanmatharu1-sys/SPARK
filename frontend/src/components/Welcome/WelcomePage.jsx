import React from 'react'
import { CATEGORIES, pageLabel } from '../../lib/navigation'
import MarketMonitor from '../MarketMonitor/MarketMonitor'
import FearGreed from '../FearGreed/FearGreed'

// WelcomePage — shown before any page is selected (default screen), instead
// of dropping straight into Overview. Category tiles for browsing, a
// "Recently Viewed" row (the "LAST" function from the source Bloomberg
// code list), and a compact live snapshot so the screen isn't empty.
export default function WelcomePage({ recentPages, onNavigate }) {
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 16 }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ marginBottom: 18 }}>
          <div style={{
            fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700,
            color: 'var(--gold)', letterSpacing: '0.06em',
          }}>
            SPARK TERMINAL
          </div>
          <div className="dim" style={{ fontSize: 11, marginTop: 4, lineHeight: 1.5 }}>
            Pick a screen below, or use the command bar at the top — type a page
            name, a Bloomberg-style code (try <b>OMON</b> or <b>YCRV</b>), a
            ticker, or <b>LAST</b> for your recent screens.
          </div>
        </div>

        {recentPages?.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div className="label" style={{ marginBottom: 8 }}>Recently Viewed</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {recentPages.map(id => (
                <button key={id} className="btn" style={{ fontSize: 11 }} onClick={() => onNavigate(id)}>
                  {pageLabel(id)}
                </button>
              ))}
            </div>
          </div>
        )}

        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 12, marginBottom: 20,
        }}>
          {CATEGORIES.map(cat => (
            <div key={cat.label} className="panel">
              <div className="panel-header">
                <span className="title">{cat.label}</span>
              </div>
              <div className="panel-body" style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {cat.pages.map(p => (
                  <button key={p.id} className="btn" style={{ fontSize: 11, textAlign: 'left' }}
                    onClick={() => onNavigate(p.id)}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, height: 320 }}>
          <MarketMonitor />
          <FearGreed />
        </div>
      </div>
    </div>
  )
}
