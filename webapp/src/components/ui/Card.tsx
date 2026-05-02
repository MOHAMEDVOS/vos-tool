import React from 'react'
import { motion } from 'framer-motion'

interface Props {
  children: React.ReactNode
  className?: string
  /** elevated = full Vercel 3-layer card shadow */
  elevated?: boolean
  /** hover lift — subtle translateY on hover, on by default */
  lift?: boolean
}

export function Card({ children, className = '', elevated = false, lift = true }: Props) {
  return (
    <motion.div
      whileHover={lift ? { y: -2, transition: { type: 'spring', stiffness: 400, damping: 22 } } : undefined}
      className={[
        'rounded-xl bg-surface-card text-t-primary transition-shadow duration-200',
        elevated
          ? 'shadow-card hover:shadow-[var(--shadow-card-hover)]'
          : 'shadow-border hover:shadow-[var(--shadow-soft)]',
        className,
      ].join(' ')}
    >
      {children}
    </motion.div>
  )
}
