import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface Props {
  show: boolean
  label?: string
}

export function SuccessFlash({ show, label = 'Done' }: Props) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (show) {
      setVisible(true)
      const t = setTimeout(() => setVisible(false), 2200)
      return () => clearTimeout(t)
    }
  }, [show])

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, scale: 0.6, y: 4 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.8, y: -4 }}
          transition={{ type: 'spring', stiffness: 500, damping: 28 }}
          className="inline-flex items-center gap-1.5"
        >
          {/* Circle with checkmark */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 600, damping: 20, delay: 0.05 }}
            className="flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.6)]"
          >
            <motion.svg
              width="10" height="8" viewBox="0 0 10 8" fill="none"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.3, delay: 0.1, ease: 'easeOut' }}
            >
              <motion.path
                d="M1 4L3.5 6.5L9 1"
                stroke="white"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.3, delay: 0.1 }}
              />
            </motion.svg>
          </motion.div>
          <motion.span
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 }}
            className="text-[10px] font-black uppercase tracking-widest text-emerald-500"
          >
            {label}
          </motion.span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
