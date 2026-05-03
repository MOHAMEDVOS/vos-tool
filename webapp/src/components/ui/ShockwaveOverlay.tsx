import { useEffect, useRef } from 'react'
import { animate } from 'animejs'
import { useUiStore } from '@/store/uiStore'

export function ShockwaveOverlay() {
  const loginAnimating    = useUiStore((s) => s.loginAnimating)
  const setLoginAnimating = useUiStore((s) => s.setLoginAnimating)
  const theme             = useUiStore((s) => s.theme)
  const overlayRef        = useRef<HTMLDivElement>(null)
  const hasRun            = useRef(false)

  useEffect(() => {
    if (!loginAnimating || hasRun.current) return
    const el = overlayRef.current
    if (!el) return

    hasRun.current = true

    // Reset to hidden start state before animating
    el.style.background = theme === 'dark' ? '#0a0a0a' : '#ffffff'
    el.style.clipPath   = 'circle(0% at 50% 50%)'
    el.style.opacity    = '1'
    el.style.display    = 'block'

    animate(el, {
      clipPath: [
        { to: 'circle(0% at 50% 50%)' },
        { to: 'circle(150% at 50% 50%)' },
      ],
      duration: 750,
      ease: 'cubicBezier(0.4, 0, 0.2, 1)',
      onComplete: () => {
        animate(el, {
          opacity: [1, 0],
          duration: 320,
          ease: 'cubicBezier(0.16, 1, 0.3, 1)',
          onComplete: () => {
            el.style.display = 'none'
            setLoginAnimating(false)
            hasRun.current = false
          },
        })
      },
    })
  }, [loginAnimating, theme, setLoginAnimating])

  // Always rendered so overlayRef is always populated — hidden via display:none when idle
  return (
    <div
      ref={overlayRef}
      style={{
        display:       'none',
        position:      'fixed',
        inset:         0,
        zIndex:        9999,
        pointerEvents: 'none',
        willChange:    'clip-path, opacity',
      }}
    />
  )
}
