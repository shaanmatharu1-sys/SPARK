import React, { useState } from 'react'
import { useNews } from '../../hooks/useMarketData'

export default function NewsFeed() {
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState(null)
  const { data: articles, loading } = useNews(submitted)

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">📰 News Feed</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && setSubmitted(query || null)}
            placeholder="search..."
            style={{
              background: '#0a0c10', border: '1px solid var(--border-accent)',
              color: 'var(--text-primary)', padding: '2px 6px',
              fontSize: 9, borderRadius: 3, fontFamily: 'Courier New', width: 80,
            }}
          />
        </div>
      </div>
      <div className="panel-body">
        {loading ? (
          <div style={{ padding: 12, color: 'var(--text-dim)' }}>Loading news...</div>
        ) : (
          (articles || []).map((a, i) => (
            <div key={i} style={{
              padding: '7px 10px',
              borderBottom: '1px solid #0f151e',
            }}>
              <a
                href={a.url}
                target="_blank"
                rel="noreferrer"
                style={{
                  color: 'var(--text-primary)',
                  textDecoration: 'none',
                  fontSize: 11,
                  lineHeight: 1.4,
                  display: 'block',
                  marginBottom: 2,
                }}
                onMouseOver={e => e.target.style.color = 'var(--blue-bright)'}
                onMouseOut={e  => e.target.style.color = 'var(--text-primary)'}
              >
                {a.title}
              </a>
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ color: 'var(--yellow)', fontSize: 9 }}>{a.source}</span>
                <span style={{ color: 'var(--text-dim)', fontSize: 9 }}>
                  {a.published
                    ? new Date(a.published).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : ''}
                </span>
              </div>
              {a.summary && (
                <div style={{ color: 'var(--text-secondary)', fontSize: 9, marginTop: 2,
                              lineHeight: 1.4, overflow: 'hidden',
                              display: '-webkit-box', WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical' }}>
                  {a.summary}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
