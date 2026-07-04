import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { API_BASE } from '../config'
import { THEMES, DEFAULT_THEME, applyTheme } from '../themes'

/**
 * AuthContext — current user + JWT, mirrors the SymbolContext pattern
 * (frontend/src/hooks/useSymbol.jsx). Token persists in localStorage so a
 * refresh doesn't log you out; cleared on logout.
 */
const AuthContext = createContext(null)

const TOKEN_KEY = 'terminal_token'

async function authRequest(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`)
  return data
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // On mount (or token change), resolve the current user from the token.
  useEffect(() => {
    if (!token) { setUser(null); setLoading(false); return }
    let cancelled = false
    setLoading(true)
    authRequest('/auth/me', { token })
      .then(u => { if (!cancelled) setUser(u) })
      .catch(() => {
        if (!cancelled) {
          // stale/invalid/expired token — drop it rather than looping
          localStorage.removeItem(TOKEN_KEY)
          setToken(null)
          setUser(null)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token])

  // Apply the user's theme (or the default) whenever it's known.
  useEffect(() => {
    applyTheme(user?.theme || DEFAULT_THEME)
  }, [user?.theme])

  const login = useCallback(async (username, password) => {
    const data = await authRequest('/auth/login', { method: 'POST', body: { username, password } })
    localStorage.setItem(TOKEN_KEY, data.token)
    setToken(data.token)
    setUser(data.user)
  }, [])

  const signup = useCallback(async (username, password, inviteCode) => {
    const data = await authRequest('/auth/signup', {
      method: 'POST',
      body: { username, password, invite_code: inviteCode || null },
    })
    localStorage.setItem(TOKEN_KEY, data.token)
    setToken(data.token)
    setUser(data.user)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const setTheme = useCallback(async (theme) => {
    if (!THEMES[theme]) return
    applyTheme(theme)  // apply immediately, don't wait on the round-trip
    setUser(u => u ? { ...u, theme } : u)
    try {
      await authRequest('/auth/me', { method: 'PATCH', body: { theme }, token })
    } catch {
      // best-effort persistence — the live theme change already applied
    }
  }, [token])

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, logout, setTheme }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}

/** Shared auth header helper for the rest of the app's fetch calls. */
export function authHeader() {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}
