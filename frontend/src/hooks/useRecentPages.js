import { useCallback, useState } from 'react'

// useRecentPages — the "LAST" function from a real Bloomberg terminal:
// "Allows you to see the last 8 screens you visited." Persisted the same
// way useAuth.jsx persists the auth token (plain localStorage), since
// there's no per-user backend concept for this yet.
const KEY = 'terminal_recent_pages'
const MAX = 8

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function useRecentPages() {
  const [recentPages, setRecentPages] = useState(load)

  const recordVisit = useCallback((pageId) => {
    setRecentPages(prev => {
      const next = [pageId, ...prev.filter(id => id !== pageId)].slice(0, MAX)
      try { localStorage.setItem(KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }, [])

  return { recentPages, recordVisit }
}
