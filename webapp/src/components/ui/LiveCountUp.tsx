import { useEffect, useRef, useState } from 'react'

/* Animates numeric values from PREVIOUS → NEW value.
   Useful for live progress counters. */
export function LiveCountUp({ value }: { value: number }) {
  const [display, setDisplay] = useState(value)
  const prevRef = useRef(value)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    const from = prevRef.current
    const to = value
    if (from === to) return

    const duration = 300 // shorter duration for live updates
    const start = performance.now()

    function tick(now: number) {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      /* ease-out-quad */
      const eased = progress * (2 - progress)
      const current = Math.round(from + (to - from) * eased)
      
      setDisplay(current)
      
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        prevRef.current = to
      }
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      prevRef.current = to // ensure we sync up on unmount/re-run
    }
  }, [value])

  return <>{display}</>
}
