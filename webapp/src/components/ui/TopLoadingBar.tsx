import { useEffect, useState } from 'react'
import { useIsFetching, useIsMutating } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'

/* ── Top loading bar — fires whenever any React Query fetch or mutation is active.
   Indeterminate: races from 0→82% while loading, then snaps to 100% on done.
──────────────────────────────────────────────────────────────────────────────── */

export function TopLoadingBar() {
  const fetching  = useIsFetching()
  const mutating  = useIsMutating()
  const isActive  = fetching > 0 || mutating > 0

  const [progress, setProgress] = useState(0)
  const [visible,  setVisible]  = useState(false)

  useEffect(() => {
    let raf: number
    let timeout: ReturnType<typeof setTimeout>

    if (isActive) {
      setVisible(true)
      setProgress(0)

      /* race toward 82% — slows as it approaches */
      let current = 0
      function tick() {
        const remaining = 82 - current
        const step      = remaining * 0.035           // exponential ease-in
        current = Math.min(current + Math.max(step, 0.4), 82)
        setProgress(current)
        if (current < 82) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    } else {
      /* snap to 100% then fade out */
      setProgress(100)
      timeout = setTimeout(() => {
        setVisible(false)
        setProgress(0)
      }, 400)
    }

    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(timeout)
    }
  }, [isActive])

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="top-bar"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed top-0 left-0 right-0 z-[9999] h-[2px] pointer-events-none"
          style={{ background: 'transparent' }}
        >
          {/* Track */}
          <div className="absolute inset-0 bg-transparent" />

          {/* Bar */}
          <motion.div
            className="absolute left-0 top-0 h-full rounded-r-full"
            style={{
              width: `${progress}%`,
              background: 'linear-gradient(90deg, rgba(120,80,255,0.9), rgba(80,160,255,0.95), rgba(0,210,210,0.85))',
              boxShadow: '0 0 10px rgba(120,80,255,0.6), 0 0 20px rgba(80,160,255,0.3)',
            }}
            transition={{
              width: progress === 100
                ? { duration: 0.25, ease: [0.16, 1, 0.3, 1] }
                : { duration: 0.08, ease: 'linear' },
            }}
          />

          {/* Leading glow dot */}
          {progress < 100 && (
            <motion.div
              className="absolute top-1/2 -translate-y-1/2 w-[5px] h-[5px] rounded-full"
              style={{
                left: `calc(${progress}% - 2px)`,
                background: 'rgba(200,180,255,1)',
                boxShadow: '0 0 8px 3px rgba(160,120,255,0.7)',
              }}
              animate={{ opacity: [1, 0.5, 1] }}
              transition={{ duration: 0.6, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
