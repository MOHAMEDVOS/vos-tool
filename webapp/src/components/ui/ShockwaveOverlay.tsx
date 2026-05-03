import { useEffect, useRef } from 'react'
import { animate } from 'animejs'
import { useUiStore } from '@/store/uiStore'

/**
 * Full-screen clip-path shockwave that fires once after login.
 * Mounts in App.tsx. Watches loginAnimating from uiStore.
 * Expands from center, then auto-dismisses and clears the flag.
 */
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

    el.style.background = theme === 'dark' ? '#0a0a0a' : '#ffffff'
    el.style.clipPath   = 'circle(0% at 50% 50%)'
    el.style.opacity    = '1'

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
            setLoginAnimating(false)
            hasRun.current = false
          },
        })
      },
    })
  }, [loginAnimating, theme, setLoginAnimating])

  if (!loginAnimating) return null

  return (
    <div
      ref={overlayRef}
      style={{
        position:      'fixed',
        inset:         0,
        zIndex:        9999,
        pointerEvents: 'none',
        willChange:    'clip-path, opacity',
      }}
    />
  )
}
