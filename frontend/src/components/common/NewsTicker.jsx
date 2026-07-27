import React, { useMemo } from 'react'
import { useNews, useMovers } from '../../hooks/useMarketData'
import { useSymbol } from '../../hooks/useSymbol'

// A persistent, always-on scrolling strip that blends the latest headlines
// with live top-mover prices — the one piece of chrome every research
// platform (and every real Bloomberg terminal) keeps visible no matter what
// tab you're looking at, so it lives in AppInner outside the per-tab
// content area rather than as its own navigable page.

function fmtAge(iso) {
  if (!iso) return null
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'now'
  if (mins < 60) return `${mins}m`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h`
  return `${Math.round(hrs / 24)}d`
}

function MoverItem({ q, onPick }) {
  const up = (q.change_pct ?? 0) >= 0
  return (
    <span
      onClick={() => onPick(q.symbol)}
      style={{ display: 'inline-flex', alignItems: 'baseline', gap: 5, cursor: 'pointer', flexShrink: 0 }}
      title={`Chart ${q.symbol}`}
    >
      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--gold-bright)' }}>
        {q.symbol}
      </span>
      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
        {q.price != null ? q.price.toFixed(2) : '—'}
      </span>
      <span style={{ fontFamily: 'var(--font-mono)', color: up ? 'var(--green)' : 'var(--red)' }}>
        {up ? '▲' : '▼'} {Math.abs(q.change_pct ?? 0).toFixed(2)}%
      </span>
    </span>
  )
}

function NewsItem({ a }) {
  const age = fmtAge(a.published)
  return (
    <a
      href={a.url} target="_blank" rel="noreferrer"
      style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6, flexShrink: 0,
                color: 'var(--text-primary)', textDecoration: 'none' }}
      title={a.summary || a.title}
    >
      {age && <span style={{ color: 'var(--text-dim)', fontSize: 9 }}>{age}</span>}
      <span className="dim" style={{ fontSize: 9 }}>{a.source}</span>
      <span>{a.title}</span>
    </a>
  )
}

export default function NewsTicker() {
  const { data: news }    = useNews()
  const { data: gainers } = useMovers('gainers')
  const { data: losers }  = useMovers('losers')
  const { setSymbol } = useSymbol()

  // Interleave: a mover every 4th slot, headlines otherwise — keeps price
  // action visible without drowning out the news.
  const items = useMemo(() => {
    const headlines = (Array.isArray(news) ? news : []).slice(0, 24)
    const movers = [
      ...(gainers?.movers || gainers || []).slice(0, 6),
      ...(losers?.movers || losers || []).slice(0, 6),
    ].filter(m => m && m.symbol)

    if (!headlines.length && !movers.length) return []
    const out = []
    let hi = 0, mi = 0
    while (hi < headlines.length || mi < movers.length) {
      for (let k = 0; k < 3 && hi < headlines.length; k++, hi++) {
        out.push({ kind: 'news', key: `n${hi}`, data: headlines[hi] })
      }
      if (mi < movers.length) {
        out.push({ kind: 'mover', key: `m${mi}`, data: movers[mi] })
        mi++
      }
    }
    return out
  }, [news, gainers, losers])

  if (!items.length) return null

  // Duplicate the strip once so the CSS marquee loop (-50% translateX) is
  // seamless regardless of content width.
  const renderStrip = (suffix) => items.map(it => (
    <React.Fragment key={`${it.key}${suffix}`}>
      {it.kind === 'news'
        ? <NewsItem a={it.data} />
        : <MoverItem q={it.data} onPick={setSymbol} />}
      <span style={{ color: 'var(--border-bright)', flexShrink: 0 }}>•</span>
    </React.Fragment>
  ))

  return (
    <div style={{
      height: 22, flexShrink: 0, overflow: 'hidden', position: 'relative',
      background: 'var(--bg-header)', borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center',
    }}>
      <span style={{
        flexShrink: 0, fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
        color: 'var(--bg-header)', background: 'var(--gold)',
        padding: '2px 8px', height: '100%', display: 'flex', alignItems: 'center',
        zIndex: 2,
      }}>
        LIVE
      </span>
      <div className="news-ticker-track" style={{
        display: 'flex', alignItems: 'center', gap: 10, whiteSpace: 'nowrap',
        fontSize: 10.5, paddingLeft: 10, willChange: 'transform',
      }}>
        {renderStrip('a')}
        {renderStrip('b')}
      </div>
    </div>
  )
}
