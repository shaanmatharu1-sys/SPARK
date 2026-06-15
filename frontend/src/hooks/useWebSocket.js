import { useEffect, useRef, useState, useCallback } from 'react'
import { WS_BASE } from '../config'

/**
 * useWebSocket — persistent WebSocket hook with auto-reconnect
 * @param {string} path    — e.g. "/quotes/ws?symbols=AAPL,SPY"
 * @param {Function} onMessage — callback(data: object)
 * @param {boolean} enabled — set false to disable connection
 */
export function useWebSocket(path, onMessage, enabled = true) {
  const wsRef       = useRef(null)
  const reconnTimer = useRef(null)
  const backoff     = useRef(1000)
  const onMessageRef = useRef(onMessage)
  const [status, setStatus] = useState('disconnected') // connected | disconnected | error

  // Keep the latest onMessage without forcing a reconnect each render
  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])

  const connect = useCallback(() => {
    if (!enabled || !path) return
    try {
      const ws = new WebSocket(`${WS_BASE}${path}`)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('connected')
        backoff.current = 1000
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          onMessageRef.current?.(data)
        } catch {}
      }

      ws.onerror = () => setStatus('error')

      ws.onclose = () => {
        setStatus('disconnected')
        if (enabled) {
          reconnTimer.current = setTimeout(() => {
            backoff.current = Math.min(backoff.current * 1.5, 30000)
            connect()
          }, backoff.current)
        }
      }
    } catch (e) {
      setStatus('error')
    }
  }, [path, enabled])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return status
}
