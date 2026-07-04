import React, { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'

export default function LoginScreen() {
  const { login, signup } = useAuth()
  const [mode, setMode] = useState('login') // login | signup
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(username, password)
      } else {
        await signup(username, password, inviteCode)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-base)',
    }}>
      <form onSubmit={submit} className="panel" style={{ width: 340, padding: 0 }}>
        <div className="panel-header" style={{ justifyContent: 'center' }}>
          <span style={{
            fontFamily: 'var(--font-display)', color: 'var(--gold)', fontWeight: 700,
            fontSize: 17, letterSpacing: '0.12em',
          }}>
            SPARK
          </span>
        </div>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
            <button type="button" className={`btn ${mode === 'login' ? 'active' : ''}`}
              style={{ flex: 1 }} onClick={() => setMode('login')}>Log in</button>
            <button type="button" className={`btn ${mode === 'signup' ? 'active' : ''}`}
              style={{ flex: 1 }} onClick={() => setMode('signup')}>Sign up</button>
          </div>

          <label className="label">Username</label>
          <input className="input" value={username} autoFocus
            onChange={e => setUsername(e.target.value)} />

          <label className="label">Password</label>
          <input className="input" type="password" value={password}
            onChange={e => setPassword(e.target.value)} />

          {mode === 'signup' && (
            <>
              <label className="label">Invite code (if required)</label>
              <input className="input" value={inviteCode}
                onChange={e => setInviteCode(e.target.value)} />
            </>
          )}

          {error && (
            <div className="red" style={{ fontSize: 11 }}>{error}</div>
          )}

          <button className="btn active" type="submit" disabled={busy} style={{ marginTop: 6 }}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </div>
      </form>
    </div>
  )
}
