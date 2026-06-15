import React, { useState, useEffect } from 'react'
import { useSymbol } from '../../hooks/useSymbol'
import {
  LineChart, Line, ScatterChart, Scatter, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ZAxis, Legend
} from 'recharts'
import { useVolSurface } from '../../hooks/useMarketData'

function Metric({ label, value, color }) {
  return (
    <div style={{ flex: 1, textAlign: 'center', padding: '6px 4px',
                  background: '#0a0c10', borderRadius: 3 }}>
      <div className="dim" style={{ fontSize: 8 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 'bold', color: color || 'var(--text-primary)' }}>
        {value}
      </div>
    </div>
  )
}

// Distinct colors per expiration for the smile scatter
const EXP_COLORS = ['#42a5f5', '#00c853', '#f0a500', '#7c4dff', '#ff3d57', '#00bcd4', '#ff8c00']

export default function VolSurface() {
  const { symbol, setSymbol } = useSymbol()
  const [input, setInput]   = useState(symbol)
  useEffect(() => { setInput(symbol) }, [symbol])
  const { data, loading, error } = useVolSurface(symbol)

  const s = data?.summary || {}

  // Group surface points by expiration for the smile chart
  const smileByExp = React.useMemo(() => {
    if (!data?.surface_points) return []
    const groups = {}
    for (const p of data.surface_points) {
      (groups[p.expiration] ||= []).push({ moneyness: p.moneyness, iv: p.iv * 100 })
    }
    return Object.entries(groups)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([exp, pts], i) => ({
        exp,
        color: EXP_COLORS[i % EXP_COLORS.length],
        points: pts.sort((a, b) => a.moneyness - b.moneyness),
      }))
  }, [data])

  const termData = (data?.term_structure || [])
    .slice().sort((a, b) => a.T - b.T)
    .map(t => ({ exp: t.expiration?.slice(5), iv: (t.atm_iv * 100).toFixed(1), T: t.T }))

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        <span className="title">Vol Surface</span>
        <input value={input} onChange={e => setInput(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && setSymbol(input)}
          style={{ background: '#0a0c10', border: '1px solid var(--border-accent)',
                   color: 'var(--yellow)', padding: '2px 6px', fontSize: 10,
                   borderRadius: 3, width: 64, fontFamily: 'Courier New', fontWeight: 'bold' }} />
      </div>
      <div className="panel-body" style={{ padding: 8 }}>
        {loading && <div style={{ color: 'var(--text-dim)' }}>Solving IV surface for {symbol}...</div>}
        {error && <div style={{ color: 'var(--red)' }}>Error: {error}</div>}
        {data?.error && <div style={{ color: 'var(--red)', fontSize: 11 }}>{data.error}</div>}

        {data?.summary && (
          <>
            {/* Summary metrics */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
              <Metric label="ATM IV (FRONT)" value={s.atm_iv_front ? `${(s.atm_iv_front*100).toFixed(1)}%` : '—'} />
              <Metric label="ATM IV (BACK)" value={s.atm_iv_back ? `${(s.atm_iv_back*100).toFixed(1)}%` : '—'} />
              <Metric label="TERM"
                value={s.term_shape || '—'}
                color={s.term_shape === 'contango' ? 'var(--green)' : 'var(--red)'} />
              <Metric label="SKEW"
                value={s.skew_direction || '—'}
                color={s.skew_direction === 'put skew' ? 'var(--yellow)' : 'var(--blue-bright)'} />
            </div>

            {/* Term structure */}
            <div className="dim" style={{ fontSize: 9, margin: '4px 0' }}>ATM TERM STRUCTURE</div>
            <div style={{ height: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={termData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#131820" />
                  <XAxis dataKey="exp" tick={{ fill: '#546e7a', fontSize: 8 }} axisLine={{ stroke: '#1c2333' }} />
                  <YAxis tick={{ fill: '#546e7a', fontSize: 8 }} axisLine={{ stroke: '#1c2333' }}
                         tickFormatter={v => `${v}%`} width={38} domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: '#0e1118', border: '1px solid #1c2333',
                           borderRadius: 4, fontSize: 10, fontFamily: 'Courier New' }}
                           formatter={v => `${v}%`} />
                  <Line type="monotone" dataKey="iv" stroke="#42a5f5" strokeWidth={2}
                        dot={{ fill: '#42a5f5', r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Vol smile by expiration */}
            <div className="dim" style={{ fontSize: 9, margin: '8px 0 4px' }}>IV SMILE (by moneyness)</div>
            <div style={{ height: 140 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#131820" />
                  <XAxis type="number" dataKey="moneyness" name="moneyness"
                         domain={['auto', 'auto']} tick={{ fill: '#546e7a', fontSize: 8 }}
                         axisLine={{ stroke: '#1c2333' }}
                         tickFormatter={v => v.toFixed(2)} />
                  <YAxis type="number" dataKey="iv" name="IV"
                         tick={{ fill: '#546e7a', fontSize: 8 }} axisLine={{ stroke: '#1c2333' }}
                         tickFormatter={v => `${v.toFixed(0)}%`} width={38} domain={['auto', 'auto']} />
                  <ZAxis range={[20, 20]} />
                  <Tooltip contentStyle={{ background: '#0e1118', border: '1px solid #1c2333',
                           borderRadius: 4, fontSize: 10, fontFamily: 'Courier New' }}
                           formatter={(v, n) => n === 'IV' ? `${v.toFixed(1)}%` : v.toFixed(3)} />
                  <Legend wrapperStyle={{ fontSize: 8 }} />
                  {smileByExp.slice(0, 5).map(g => (
                    <Scatter key={g.exp} name={g.exp.slice(5)} data={g.points}
                             fill={g.color} line={{ stroke: g.color, strokeWidth: 1 }} lineType="joint" />
                  ))}
                </ScatterChart>
              </ResponsiveContainer>
            </div>

            {/* Skew table */}
            {data.skew?.length > 0 && (
              <table className="bbg-table" style={{ marginTop: 8 }}>
                <thead>
                  <tr><th>EXP</th><th>RISK REV</th><th>BFLY</th><th>PUT IV</th><th>CALL IV</th></tr>
                </thead>
                <tbody>
                  {data.skew.map(sk => (
                    <tr key={sk.expiration}>
                      <td style={{ fontSize: 10 }}>{sk.expiration?.slice(5)}</td>
                      <td style={{ color: sk.risk_reversal > 0 ? 'var(--yellow)' : 'var(--blue-bright)' }}>
                        {sk.risk_reversal >= 0 ? '+' : ''}{(sk.risk_reversal * 100).toFixed(2)}
                      </td>
                      <td>{(sk.butterfly * 100).toFixed(2)}</td>
                      <td>{(sk.put_iv * 100).toFixed(1)}%</td>
                      <td>{(sk.call_iv * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </div>
  )
}
