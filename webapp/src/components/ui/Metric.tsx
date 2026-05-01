import { useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'

interface Props {
  label: string
  value: number | string
  sub?: string
}

/* Animates numeric values from 0 → target when scrolled into view.
   Non-numeric values just fade in. */
function useCountUp(target: number | string, inView: boolean) {
  const [display, setDisplay] = useState<number | string>(
    typeof target === 'number' ? 0 : target,
  )
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    if (!inView || typeof target !== 'number') {
      setDisplay(target)
      return
    }
    const duration = 900   // ms
    const start    = performance.now()
    const from     = 0

    function tick(now: number) {
      const elapsed  = now - start
      const progress = Math.min(elapsed / duration, 1)
      /* ease-out-expo */
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
      const current = Math.round(from + (target - from) * eased)
      setDisplay(current)
      if (progress < 1) rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [target, inView])

  return display
}

export function Metric({ label, value, sub }: Props) {
  const ref    = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '0px 0px -40px 0px' })
  const count  = useCountUp(value, inView)

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 12 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col justify-center items-center text-center py-1"
    >
      <div className="text-[40px] font-semibold text-t-primary leading-none tracking-[-2.4px] tabular-nums font-feature-settings-liga">
        {count}
      </div>
      <div className="mt-2 mono-label">{label}</div>
      {sub && <div className="mt-1 text-[12px] text-t-muted">{sub}</div>}
    </motion.div>
  )
}
