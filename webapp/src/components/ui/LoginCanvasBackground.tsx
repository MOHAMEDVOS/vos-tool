import { useEffect, useRef } from 'react'

/* ── Neural graph canvas for login page ──────────────────────────
   Floating nodes connected by proximity lines. Occasional signal
   pulse travels along edges. Mouse repels nearby nodes.
   Color: pure white at ultra-low opacity — keeps pitch-black brand.
──────────────────────────────────────────────────────────────────── */

const NODE_COUNT   = 72
const CONNECT_DIST = 140   // px — max edge length
const NODE_SPEED   = 0.28  // px per frame
const REPEL_RADIUS = 110   // px — mouse influence radius
const REPEL_FORCE  = 1.8   // push strength

type Node = {
  x: number; y: number
  vx: number; vy: number
  r: number              // radius 1.2–2.4
  pulse: number          // 0–1 brightness oscillation phase
  pulseSpeed: number
}

type Signal = {
  fromIdx: number
  toIdx:   number
  t:       number        // 0→1 progress along the edge
  speed:   number
}

export function LoginCanvasBackground() {
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const mouseRef   = useRef<{ x: number; y: number } | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    let w = canvas.width  = window.innerWidth
    let h = canvas.height = window.innerHeight

    const onResize = () => {
      w = canvas.width  = window.innerWidth
      h = canvas.height = window.innerHeight
    }
    const onMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY }
    }
    const onMouseLeave = () => { mouseRef.current = null }

    window.addEventListener('resize',     onResize)
    window.addEventListener('mousemove',  onMouseMove)
    window.addEventListener('mouseleave', onMouseLeave)

    /* ── Init nodes ── */
    const nodes: Node[] = Array.from({ length: NODE_COUNT }, () => {
      const angle = Math.random() * Math.PI * 2
      const speed = NODE_SPEED * (0.5 + Math.random() * 0.8)
      return {
        x:          Math.random() * w,
        y:          Math.random() * h,
        vx:         Math.cos(angle) * speed,
        vy:         Math.sin(angle) * speed,
        r:          1.2 + Math.random() * 1.2,
        pulse:      Math.random() * Math.PI * 2,
        pulseSpeed: 0.008 + Math.random() * 0.012,
      }
    })

    /* ── Signal pulses ── */
    const signals: Signal[] = []
    let frameCount = 0

    function spawnSignal() {
      /* pick a random connected pair */
      for (let attempt = 0; attempt < 20; attempt++) {
        const fromIdx = Math.floor(Math.random() * nodes.length)
        const a = nodes[fromIdx]
        for (let j = 0; j < nodes.length; j++) {
          if (j === fromIdx) continue
          const b = nodes[j]
          const dx = b.x - a.x
          const dy = b.y - a.y
          if (dx * dx + dy * dy < CONNECT_DIST * CONNECT_DIST) {
            signals.push({ fromIdx, toIdx: j, t: 0, speed: 0.012 + Math.random() * 0.016 })
            return
          }
        }
      }
    }

    function draw() {
      if (!ctx) return
      ctx.clearRect(0, 0, w, h)

      /* ── Update nodes ── */
      const mouse = mouseRef.current
      nodes.forEach(n => {
        n.pulse += n.pulseSpeed

        /* mouse repel */
        if (mouse) {
          const dx = n.x - mouse.x
          const dy = n.y - mouse.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < REPEL_RADIUS && dist > 0) {
            const force = (1 - dist / REPEL_RADIUS) * REPEL_FORCE
            n.vx += (dx / dist) * force * 0.05
            n.vy += (dy / dist) * force * 0.05
          }
        }

        /* speed cap */
        const spd = Math.sqrt(n.vx * n.vx + n.vy * n.vy)
        if (spd > NODE_SPEED * 3) {
          n.vx = (n.vx / spd) * NODE_SPEED * 3
          n.vy = (n.vy / spd) * NODE_SPEED * 3
        }

        /* drift back to base speed */
        const target = NODE_SPEED * (0.6 + 0.4)
        if (spd > target) {
          n.vx *= 0.98
          n.vy *= 0.98
        }

        n.x += n.vx
        n.y += n.vy

        /* wrap edges */
        if (n.x < -20) n.x = w + 20
        if (n.x > w + 20) n.x = -20
        if (n.y < -20) n.y = h + 20
        if (n.y > h + 20) n.y = -20
      })

      /* ── Edges ── */
      const cd2 = CONNECT_DIST * CONNECT_DIST
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i]
          const b = nodes[j]
          const dx = b.x - a.x
          const dy = b.y - a.y
          const d2 = dx * dx + dy * dy
          if (d2 > cd2) continue
          const alpha = (1 - d2 / cd2) * 0.10
          ctx.strokeStyle = `rgba(255,255,255,${alpha})`
          ctx.lineWidth   = 0.5
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(b.x, b.y)
          ctx.stroke()
        }
      }

      /* ── Signal pulses ── */
      for (let s = signals.length - 1; s >= 0; s--) {
        const sig = signals[s]
        sig.t += sig.speed
        if (sig.t >= 1) { signals.splice(s, 1); continue }

        const a = nodes[sig.fromIdx]
        const b = nodes[sig.toIdx]
        const px = a.x + (b.x - a.x) * sig.t
        const py = a.y + (b.y - a.y) * sig.t

        /* glow dot */
        const grd = ctx.createRadialGradient(px, py, 0, px, py, 6)
        grd.addColorStop(0,   'rgba(200,220,255,0.85)')
        grd.addColorStop(0.4, 'rgba(180,200,255,0.30)')
        grd.addColorStop(1,   'rgba(180,200,255,0)')
        ctx.fillStyle = grd
        ctx.beginPath()
        ctx.arc(px, py, 6, 0, Math.PI * 2)
        ctx.fill()

        /* bright core */
        ctx.fillStyle = 'rgba(255,255,255,0.95)'
        ctx.beginPath()
        ctx.arc(px, py, 1.2, 0, Math.PI * 2)
        ctx.fill()
      }

      /* ── Nodes ── */
      nodes.forEach(n => {
        const bright = 0.45 + 0.25 * Math.sin(n.pulse)
        ctx.fillStyle = `rgba(255,255,255,${bright})`
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx.fill()
      })

      /* ── Spawn new signal ~every 55 frames ── */
      frameCount++
      if (frameCount % 55 === 0) spawnSignal()

      animId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize',     onResize)
      window.removeEventListener('mousemove',  onMouseMove)
      window.removeEventListener('mouseleave', onMouseLeave)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 z-0 block pointer-events-none"
    />
  )
}
