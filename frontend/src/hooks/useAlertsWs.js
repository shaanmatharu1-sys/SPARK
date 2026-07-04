import { useEffect, useRef, useState, useCallback } from 'react'
import { WS_BASE, API_BASE } from '../config'
import { authHeader } from './useAuth'

/**
 * useAlertsWs — live alert-trigger feed over an authenticated WebSocket.
 *
 * The generic useWebSocket hook (hooks/useWebSocket.js) reconnects by
 * reopening the SAME path — fine for the public quote/option streams, but
 * the alerts WS requires a fresh single-use ticket per connection (see
 * routers/alerts.py), so a stale ticket would just fail forever on
 * reconnect. This hook mints a new ticket itself before every (re)connect.
 */
export function useAlertsWs(enabled, onAlert) {
  const [status, setStatus] = useState('disconnected')
  const wsRef = useRef(null)
  const reconnTimer = useRef(null)
  const backoff = useRef(2000)
  const onAlertRef = useRef(onAlert)
  useEffect(() => { onAlertRef.current = onAlert }, [onAlert])

  const connect = useCallback(async () => {
    if (!enabled) return
    try {
      const r = await fetch(`${API_BASE}/alerts/ws-ticket`, { method: 'POST', headers: authHeader() })
      if (!r.ok) throw new Error(`ticket HTTP ${r.status}`)
      const { ticket } = await r.json()

      const ws = new WebSocket(`${WS_BASE}/alerts/ws?ticket=${ticket}`)
      wsRef.current = ws

      ws.onopen = () => { setStatus('connected'); backoff.current = 2000 }
      ws.onmessage = (e) => {
        try { onAlertRef.current?.(JSON.parse(e.data)) } catch {}
      }
      ws.onerror = () => setStatus('error')
      ws.onclose = () => {
        setStatus('disconnected')
        if (enabled) {
          backoff.current = Math.min(backoff.current * 1.7, 30000)
          reconnTimer.current = setTimeout(connect, backoff.current)
        }
      }
    } catch {
      setStatus('error')
      if (enabled) {
        backoff.current = Math.min(backoff.current * 1.7, 30000)
        reconnTimer.current = setTimeout(connect, backoff.current)
      }
    }
  }, [enabled])

  useEffect(() => {
    if (enabled) connect()
    return () => {
      clearTimeout(reconnTimer.current)
      wsRef.current?.close()
    }
  }, [enabled, connect])

  return status
}
