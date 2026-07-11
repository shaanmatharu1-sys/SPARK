import React, { useRef, useEffect, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

// Builds a regular (moneyness x T) grid from scattered {moneyness, T, iv} points
// via inverse-distance-weighted interpolation, so a real mesh surface can be
// drawn even though raw strikes/expirations differ contract to contract.
function buildGrid(points, gridSize = 24) {
  if (!points.length) return null
  let mMin = Infinity, mMax = -Infinity, tMin = Infinity, tMax = -Infinity
  for (const p of points) {
    if (p.moneyness < mMin) mMin = p.moneyness
    if (p.moneyness > mMax) mMax = p.moneyness
    if (p.T < tMin) tMin = p.T
    if (p.T > tMax) tMax = p.T
  }
  if (mMin === mMax || tMin === tMax) return null

  const grid = []
  let ivMin = Infinity, ivMax = -Infinity
  for (let i = 0; i < gridSize; i++) {
    const m = mMin + (mMax - mMin) * (i / (gridSize - 1))
    const row = []
    for (let j = 0; j < gridSize; j++) {
      const t = tMin + (tMax - tMin) * (j / (gridSize - 1))
      // Inverse-distance weighting in normalized (moneyness, T) space
      let wSum = 0, ivSum = 0
      for (const p of points) {
        const dm = (p.moneyness - m) / (mMax - mMin || 1)
        const dt = (p.T - t) / (tMax - tMin || 1)
        const d2 = dm * dm + dt * dt
        const w = 1 / (d2 + 1e-4)
        wSum += w
        ivSum += w * p.iv
      }
      const iv = ivSum / wSum
      if (iv < ivMin) ivMin = iv
      if (iv > ivMax) ivMax = iv
      row.push(iv)
    }
    grid.push(row)
  }
  return { grid, mMin, mMax, tMin, tMax, ivMin, ivMax, gridSize }
}

// Bloomberg-esque cold-to-hot color ramp for IV level (blue=cheap, red=expensive)
const IV_COLOR_STOPS = [
  [0.10, 0.20, 0.55], // deep blue
  [0.20, 0.55, 0.55], // teal
  [0.75, 0.70, 0.25], // gold
  [0.85, 0.30, 0.25], // red
]
function ivColor(t) {
  const stops = IV_COLOR_STOPS
  const n = stops.length - 1
  const scaled = Math.max(0, Math.min(1, t)) * n
  const idx = Math.min(Math.floor(scaled), n - 1)
  const frac = scaled - idx
  const a = stops[idx], b = stops[idx + 1]
  return new THREE.Color(
    a[0] + (b[0] - a[0]) * frac,
    a[1] + (b[1] - a[1]) * frac,
    a[2] + (b[2] - a[2]) * frac,
  )
}
const IV_GRADIENT_CSS = `linear-gradient(90deg, ${IV_COLOR_STOPS.map(([r, g, b]) =>
  `rgb(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)})`).join(', ')})`

// Canvas-texture text sprite — cheaper and simpler than THREE.TextGeometry
// (no font-loading pipeline needed) for axis/tick labels in a 3D scene.
function makeTextSprite(text, { fontSize = 48, color = '#E8EAED', scale = 0.5 } = {}) {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  ctx.font = `600 ${fontSize}px IBM Plex Mono, monospace`
  const textWidth = ctx.measureText(text).width
  canvas.width = textWidth + 20
  canvas.height = fontSize * 1.4
  ctx.font = `600 ${fontSize}px IBM Plex Mono, monospace`
  ctx.fillStyle = color
  ctx.textBaseline = 'middle'
  ctx.fillText(text, 10, canvas.height / 2)

  const texture = new THREE.CanvasTexture(canvas)
  texture.minFilter = THREE.LinearFilter
  const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false })
  const sprite = new THREE.Sprite(mat)
  const aspect = canvas.width / canvas.height
  sprite.scale.set(scale * aspect, scale, 1)
  return sprite
}

export default function Surface3D({ points, height = 320 }) {
  const mountRef = useRef(null)
  const controlsRef = useRef(null)
  const [autoRotate, setAutoRotate] = useState(false)
  const [ivRange, setIvRange] = useState(null) // {min, max} for the HTML color-bar legend

  useEffect(() => {
    if (!mountRef.current || !points?.length) return
    const built = buildGrid(points)
    if (!built) return
    const { grid, mMin, mMax, tMin, tMax, ivMin, ivMax, gridSize } = built
    setIvRange({ min: ivMin, max: ivMax })

    const width = mountRef.current.clientWidth
    const scene = new THREE.Scene()
    scene.background = null

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
    camera.position.set(2.2, 1.8, 2.2)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mountRef.current.innerHTML = ''
    mountRef.current.appendChild(renderer.domElement)

    // Build mesh geometry: X = moneyness, Z = time-to-expiry, Y = IV (scaled)
    const geo = new THREE.PlaneGeometry(2, 2, gridSize - 1, gridSize - 1)
    const posAttr = geo.attributes.position
    const colors = new Float32Array(posAttr.count * 3)
    const ivSpan = (ivMax - ivMin) || 1

    for (let i = 0; i < gridSize; i++) {
      for (let j = 0; j < gridSize; j++) {
        const idx = i * gridSize + j
        const iv = grid[i][j]
        const scaledHeight = ((iv - ivMin) / ivSpan) * 1.1
        posAttr.setZ(idx, scaledHeight)
        const c = ivColor((iv - ivMin) / ivSpan)
        colors[idx * 3] = c.r
        colors[idx * 3 + 1] = c.g
        colors[idx * 3 + 2] = c.b
      }
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    geo.computeVertexNormals()

    const mat = new THREE.MeshPhongMaterial({
      vertexColors: true, side: THREE.DoubleSide, flatShading: false,
      shininess: 20, transparent: true, opacity: 0.96,
    })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.rotation.x = -Math.PI / 2.6
    scene.add(mesh)

    // Wireframe overlay for a "quant terminal" grid look
    const wire = new THREE.Mesh(
      geo, new THREE.MeshBasicMaterial({ color: 0x1a2b45, wireframe: true, transparent: true, opacity: 0.35 })
    )
    wire.rotation.x = mesh.rotation.x
    scene.add(wire)

    // Axis guide lines (a corner bracket along the plane's two base edges +
    // a vertical IV reference edge) so the mesh has a visible frame of
    // reference instead of floating unlabeled in space.
    const axisMat = new THREE.LineBasicMaterial({ color: 0x4a7ba6, transparent: true, opacity: 0.6 })
    const toWorld = (x, y, z) => {
      const v = new THREE.Vector3(x, y, z)
      v.applyEuler(new THREE.Euler(mesh.rotation.x, 0, 0))
      return v
    }
    const corner = toWorld(-1, -1, 0)
    const xEnd = toWorld(1, -1, 0)
    const zEnd = toWorld(-1, 1, 0)
    const yEnd = corner.clone().add(new THREE.Vector3(0, 1.3, 0))
    const axisGeo = new THREE.BufferGeometry().setFromPoints([
      corner, xEnd,   // moneyness axis
      corner, zEnd,   // time-to-expiry axis
      corner, yEnd,   // IV axis
    ])
    scene.add(new THREE.LineSegments(axisGeo, axisMat))

    // Axis + tick labels (sprites — no font loading pipeline required)
    const labelGroup = new THREE.Group()
    const addLabel = (text, pos, opts) => {
      const sprite = makeTextSprite(text, opts)
      sprite.position.copy(pos)
      labelGroup.add(sprite)
    }
    addLabel('MONEYNESS (K/S)', xEnd.clone().add(new THREE.Vector3(0.12, 0.03, 0)), { fontSize: 40, color: '#8BA3C7', scale: 0.14 })
    addLabel('DAYS TO EXPIRY', zEnd.clone().add(new THREE.Vector3(0, 0.03, 0.08)), { fontSize: 40, color: '#8BA3C7', scale: 0.14 })
    addLabel('IV', yEnd.clone().add(new THREE.Vector3(0, 0.08, 0)), { fontSize: 40, color: '#8BA3C7', scale: 0.14 })

    const TICKS = 5
    for (let i = 0; i < TICKS; i++) {
      const f = i / (TICKS - 1)
      const mVal = (mMin + (mMax - mMin) * f).toFixed(2)
      const tVal = Math.round((tMin + (tMax - tMin) * f) * 365)
      const xPos = toWorld(-1 + 2 * f, -1, 0).add(new THREE.Vector3(0, -0.05, 0))
      const zPos = toWorld(-1, -1 + 2 * f, 0).add(new THREE.Vector3(0, -0.05, 0))
      addLabel(mVal, xPos, { fontSize: 30, scale: 0.08 })
      addLabel(`${tVal}d`, zPos, { fontSize: 30, scale: 0.08 })
    }
    scene.add(labelGroup)

    scene.add(new THREE.AmbientLight(0xffffff, 0.65))
    const dir = new THREE.DirectionalLight(0xffffff, 0.9)
    dir.position.set(3, 4, 2)
    scene.add(dir)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.autoRotate = autoRotate
    controls.autoRotateSpeed = 1.1
    controls.minDistance = 1.2
    controls.maxDistance = 6
    controlsRef.current = controls

    let frame
    const animate = () => {
      frame = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const onResize = () => {
      if (!mountRef.current) return
      const w = mountRef.current.clientWidth
      camera.aspect = w / height
      camera.updateProjectionMatrix()
      renderer.setSize(w, height)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', onResize)
      controls.dispose()
      geo.dispose()
      mat.dispose()
      renderer.dispose()
      controlsRef.current = null
      if (mountRef.current) mountRef.current.innerHTML = ''
    }
    // autoRotate intentionally excluded — toggled live via controlsRef below,
    // re-running this whole effect on every toggle would rebuild the scene.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, height])

  const toggleAutoRotate = () => {
    setAutoRotate(v => {
      const next = !v
      if (controlsRef.current) controlsRef.current.autoRotate = next
      return next
    })
  }

  if (!points?.length) return null
  return (
    <div style={{ position: 'relative' }}>
      <div ref={mountRef} style={{ width: '100%', height, cursor: 'grab' }} />
      <button
        className={`btn ${autoRotate ? 'active' : ''}`}
        onClick={toggleAutoRotate}
        style={{ position: 'absolute', top: 4, right: 4, fontSize: 9, padding: '2px 6px' }}
      >
        {autoRotate ? '⟲ auto-rotate on' : '⟲ auto-rotate off'}
      </button>
      {ivRange && (
        <div style={{ position: 'absolute', bottom: 4, left: 8, right: 8,
                      display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="dim" style={{ fontSize: 8 }}>{(ivRange.min * 100).toFixed(0)}%</span>
          <div style={{ flex: 1, height: 6, borderRadius: 3, background: IV_GRADIENT_CSS }} />
          <span className="dim" style={{ fontSize: 8 }}>{(ivRange.max * 100).toFixed(0)}%</span>
          <span className="dim" style={{ fontSize: 8, marginLeft: 4 }}>IV</span>
        </div>
      )}
    </div>
  )
}
