import { motion } from 'framer-motion'

interface Props {
  size?: 'sm' | 'md' | 'lg'
  /** 'ring'  = arc spinner (default)
      'dots'  = three pulsing dots (inline use)
      'bars'  = equaliser bars (audio/processing feel) */
  variant?: 'ring' | 'dots' | 'bars'
}

const ring = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' }
const dotSize = { sm: 'h-1 w-1', md: 'h-1.5 w-1.5', lg: 'h-2 w-2' }
const barH = { sm: 'h-3', md: 'h-4', lg: 'h-5' }

export function Spinner({ size = 'md', variant = 'ring' }: Props) {

  if (variant === 'dots') {
    return (
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className={`${dotSize[size]} rounded-full bg-current`}
            animate={{ scale: [1, 1.5, 1], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.18, ease: 'easeInOut' }}
          />
        ))}
      </div>
    )
  }

  if (variant === 'bars') {
    return (
      <div className="flex items-end gap-[3px]">
        {[0.9, 1.4, 0.7, 1.2, 0.85].map((scale, i) => (
          <motion.div
            key={i}
            className={`w-[3px] ${barH[size]} rounded-sm bg-current`}
            animate={{ scaleY: [0.3, scale, 0.3] }}
            transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.1, ease: 'easeInOut' }}
            style={{ originY: '100%' }}
          />
        ))}
      </div>
    )
  }

  /* default: ring */
  return (
    <div className={`${ring[size]} relative`}>
      {/* Track */}
      <div className="absolute inset-0 rounded-full border-2 border-[var(--b-subtle)]" />
      {/* Arc */}
      <motion.div
        className="absolute inset-0 rounded-full border-2 border-transparent"
        style={{
          borderTopColor: 'var(--accent)',
          boxShadow: '0 0 6px rgba(120,80,255,0.4)',
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 0.75, repeat: Infinity, ease: 'linear' }}
      />
    </div>
  )
}
