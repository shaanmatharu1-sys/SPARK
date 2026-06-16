import React, { useState } from 'react'

/**
 * Explain — a small "?" button that toggles an explanatory popover.
 * Used in panel headers to give plain-English context for each tab's data.
 */
export default function Explain({ title, children }) {
  const [open, setOpen] = useState(false)
  return (
    <span style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpen(!open)}
        title="What is this?"
        style={{
          background: open ? 'var(--gold)' : 'transparent',
          color: open ? 'var(--bg-base)' : 'var(--text-dim)',
          border: '1px solid var(--border-bright)', borderRadius: '50%',
          width: 16, height: 16, fontSize: 10, cursor: 'pointer', lineHeight: 1,
          padding: 0, fontWeight: 700,
        }}
      >?</button>
      {open && (
        <div style={{
          position: 'absolute', top: 22, right: 0, zIndex: 100,
          width: 300, background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
          borderRadius: 6, padding: 12, boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}>
          {title && <div style={{ fontWeight: 700, color: 'var(--gold)', fontSize: 12, marginBottom: 6 }}>{title}</div>}
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{children}</div>
        </div>
      )}
    </span>
  )
}
