// src/config.js — resolves backend base URLs for REST and WebSocket.
//
// Dev:  VITE_API_BASE unset -> use '/api' and ws://localhost:8000 (Vite proxy)
// Prod: set VITE_API_BASE to your Railway backend URL, e.g.
//         VITE_API_BASE=https://meridian-backend.up.railway.app

const RAW = import.meta.env.VITE_API_BASE || ''

// REST base. In dev we use the Vite proxy at '/api'. In prod we hit the
// backend directly at VITE_API_BASE.
export const API_BASE = RAW ? RAW.replace(/\/$/, '') : '/api'

// WebSocket base. Derive ws(s):// from the API base.
export const WS_BASE = (() => {
  if (RAW) {
    return RAW.replace(/^http/, 'ws').replace(/\/$/, '')
  }
  // dev default — Vite proxies /quotes/ws etc. straight through on 8000
  return 'ws://localhost:8000'
})()
