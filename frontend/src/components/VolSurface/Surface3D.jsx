import React, { useRef, useEffect } from 'react'
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
function ivColor(t) {
  const stops = [
    [0.10, 0.20, 0.55], // deep blue
    [0.20, 0.55, 0.55], // teal
    [0.75, 0.70, 0.25], // gold
    [0.85, 0.30, 0.25], // red
  ]
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

export default function Surface3D({ points, height = 320 }) {
  const mountRef = useRef(null)

  useEffect(() => {
    if (!mountRef.current || !points?.length) return
    const built = buildGrid(points)
    if (!built) return
    const { grid, ivMin, ivMax, gridSize } = built

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
    const ivRange = (ivMax - ivMin) || 1

    for (let i = 0; i < gridSize; i++) {
      for (let j = 0; j < gridSize; j++) {
        const idx = i * gridSize + j
        const iv = grid[i][j]
        const scaledHeight = ((iv - ivMin) / ivRange) * 1.1
        posAttr.setZ(idx, scaledHeight)
        const c = ivColor((iv - ivMin) / ivRange)
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

    scene.add(new THREE.AmbientLight(0xffffff, 0.65))
    const dir = new THREE.DirectionalLight(0xffffff, 0.9)
    dir.position.set(3, 4, 2)
    scene.add(dir)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.autoRotate = true
    controls.autoRotateSpeed = 1.1
    controls.minDistance = 1.2
    controls.maxDistance = 6

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
      if (mountRef.current) mountRef.current.innerHTML = ''
    }
  }, [points, height])

  if (!points?.length) return null
  return <div ref={mountRef} style={{ width: '100%', height, cursor: 'grab' }} />
}
