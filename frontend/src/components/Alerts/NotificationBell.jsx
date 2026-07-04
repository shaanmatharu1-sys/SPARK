import React, { useState, useCallback, useRef, useEffect } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { useAlerts, alertsApi } from '../../hooks/useMarketData'
import { useAlertsWs } from '../../hooks/useAlertsWs'
import SymbolSearch from '../common/SymbolSearch'

function Toast({ toast, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 6000)
    return () => clearTimeout(t)
  }, [toast, onDone])
  if (!toast) return null
  const isAbove = toast.condition === 'above'
  return (
    <div style={{
      position: 'fixed', top: 42, right: 16, zIndex: 999,
      background: 'var(--bg-panel)', border: '1px solid var(--gold-bright)',
      borderRadius: 6, padding: '10px 14px', minWidth: 220,
      boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--gold-bright)' }}>ALERT TRIGGERED</div>
      <div style={{ fontSize: 13, fontFamily: 'var(--font-mono)', marginTop: 4 }}>
        <span style={{ color: 'var(--gold)', fontWeight: 700 }}>{toast.symbol}</span>
        {' '}went {isAbove ? 'above' : 'below'} ${toast.threshold} — now ${toast.price}
      </div>
    </div>
  )
}

export default function NotificationBell() {
  const { user } = useAuth()
  const { data, refresh } = useAlerts()
  const [open, setOpen] = useState(false)
  const [toast, setToast] = useState(null)
  const [unread, setUnread] = useState(0)
  const [sym, setSym] = useState('')
  const [condition, setCondition] = useState('above')
  const [threshold, setThreshold] = useState('')
  const boxRef = useRef(null)

  const onAlert = useCallback((msg) => {
    if (msg.type !== 'alert_triggered') return
    setToast(msg)
    setUnread(u => u + 1)
    refresh()
  }, [refresh])

  useAlertsWs(!!user, onAlert)

  useEffect(() => {
    function onClickOutside(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const add = async () => {
    if (!sym || !threshold) return
    await alertsApi.create(sym.toUpperCase(), condition, parseFloat(threshold))
    setSym(''); setThreshold('')
    refresh()
  }
  const remove = async (id) => { await alertsApi.remove(id); refresh() }

  const alerts = data?.alerts || []
  const active = alerts.filter(a => a.active)
  const triggered = alerts.filter(a => !a.active)

  return (
    <div ref={boxRef} style={{ position: 'relative' }}>
      <button className="btn" style={{ fontSize: 11, position: 'relative' }}
        onClick={() => { setOpen(o => !o); setUnread(0) }}>
        🔔 Alerts
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: -5, right: -5, background: 'var(--red)',
            color: '#fff', borderRadius: '50%', fontSize: 9, width: 15, height: 15,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>{unread}</span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, marginTop: 4, width: 300,
          background: 'var(--bg-panel)', border: '1px solid var(--border-bright)',
          borderRadius: 6, zIndex: 200, maxHeight: 420, overflowY: 'auto',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)', padding: 10,
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--gold-bright)', marginBottom: 6 }}>
            NEW ALERT
          </div>
          <div style={{ display: 'flex', gap: 4, marginBottom: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <SymbolSearch value={sym} onChange={setSym} onSelect={setSym} width={80} />
            <select className="input" value={condition} onChange={e => setCondition(e.target.value)}
              style={{ fontSize: 10, padding: '3px 4px' }}>
              <option value="above">above</option>
              <option value="below">below</option>
            </select>
            <input className="input" placeholder="price" type="number" value={threshold}
              onChange={e => setThreshold(e.target.value)} style={{ width: 60 }} />
            <button className="btn active" style={{ fontSize: 10 }} onClick={add}>Add</button>
          </div>

          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--gold-bright)', margin: '6px 0' }}>
            ACTIVE ({active.length})
          </div>
          {active.length === 0 && <div className="dim" style={{ fontSize: 11 }}>No active alerts.</div>}
          {active.map(a => (
            <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                      padding: '3px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                {a.symbol} {a.condition} ${a.threshold}
              </span>
              <span style={{ cursor: 'pointer', color: 'var(--text-dim)', fontSize: 10 }}
                onClick={() => remove(a.id)}>remove</span>
            </div>
          ))}

          {triggered.length > 0 && (
            <>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--gold-bright)', margin: '10px 0 6px' }}>
                TRIGGERED
              </div>
              {triggered.map(a => (
                <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                          padding: '3px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                    {a.symbol} {a.condition} ${a.threshold}
                  </span>
                  <span style={{ cursor: 'pointer', color: 'var(--text-dim)', fontSize: 10 }}
                    onClick={() => remove(a.id)}>clear</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      <Toast toast={toast} onDone={() => setToast(null)} />
    </div>
  )
}
