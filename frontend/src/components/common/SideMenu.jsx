import React, { useState } from 'react'
import { CATEGORIES } from '../../lib/navigation'

// SideMenu — collapsible left rail replacing the old horizontal tab strip.
// Groups the same 24 pages into categories (see lib/navigation.js).
const COLLAPSE_KEY = 'terminal_sidemenu_collapsed'

export default function SideMenu({ activeTab, onSelect }) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === '1' } catch { return false }
  })

  const toggle = () => setCollapsed(c => {
    const next = !c
    try { localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0') } catch {}
    return next
  })

  return (
    <div style={{
      width: collapsed ? 44 : 176, flexShrink: 0, height: '100%',
      background: 'var(--bg-header)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      transition: 'width 0.15s ease',
    }}>
      <button className="btn" onClick={toggle} style={{ margin: 6, fontSize: 11, flexShrink: 0 }}
        title={collapsed ? 'Expand menu' : 'Collapse menu'}>
        {collapsed ? '»' : '« Menu'}
      </button>
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '0 6px 10px' }}>
        {CATEGORIES.map(cat => (
          <div key={cat.label} style={{ marginBottom: 10 }}>
            {!collapsed && (
              <div className="label" style={{ padding: '6px 6px 3px', fontSize: 9 }}>
                {cat.label}
              </div>
            )}
            {cat.pages.map(p => {
              const active = p.id === activeTab
              return (
                <button
                  key={p.id}
                  onClick={() => onSelect(p.id)}
                  title={p.label}
                  style={{
                    display: 'block', width: '100%',
                    background: active ? 'var(--bg-raised)' : 'transparent',
                    color: active ? 'var(--gold-bright)' : 'var(--text-secondary)',
                    border: active ? '1px solid var(--border-bright)' : '1px solid transparent',
                    borderRadius: 6, padding: collapsed ? '6px 0' : '5px 8px',
                    fontSize: 11, fontWeight: active ? 600 : 500, cursor: 'pointer',
                    fontFamily: 'var(--font-ui)', letterSpacing: '0.03em',
                    marginBottom: 2, whiteSpace: 'nowrap', overflow: 'hidden',
                    textOverflow: 'ellipsis', textAlign: collapsed ? 'center' : 'left',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {collapsed ? p.label.slice(0, 2).toUpperCase() : p.label}
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
