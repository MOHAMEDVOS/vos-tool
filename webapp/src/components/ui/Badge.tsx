import React from 'react'
import { motion } from 'framer-motion'

interface Props {
  variant?: 'success' | 'danger' | 'warning' | 'muted' | 'info' | 'ship' | 'preview' | 'develop'
  children: React.ReactNode
  /** Animate in with a spring pop — on by default */
  animate?: boolean
}

/* Vercel pill-badge system: tinted bg + matching text, 9999px radius */
const classes: Record<NonNullable<Props['variant']>, string> = {
  info:    'bg-[var(--badge-bg)] text-[var(--badge-text)]',
  muted:   'bg-[var(--surface-soft)] text-t-muted shadow-[inset_0_0_0_1px_var(--b-strong)]',
  success: 'bg-[var(--semantic-success)]/12 text-[var(--semantic-success)]',
  danger:  'bg-[var(--semantic-error)]/12   text-[var(--semantic-error)]',
  warning: 'bg-[var(--semantic-warning)]/12 text-[var(--semantic-warning)]',
  ship:    'bg-[var(--ship-red)]/10    text-[var(--ship-red)]',
  preview: 'bg-[var(--preview-pink)]/10 text-[var(--preview-pink)]',
  develop: 'bg-[var(--dev-blue)]/10   text-[var(--dev-blue)]',
}

export function Badge({ variant = 'muted', children, animate = true }: Props) {
  return (
    <motion.span
      initial={animate ? { scale: 0.7, opacity: 0 } : undefined}
      animate={animate ? { scale: 1,   opacity: 1 } : undefined}
      transition={{ type: 'spring', stiffness: 500, damping: 22 }}
      className={[
        'inline-flex items-center rounded-full px-[10px] py-0.5 text-[12px] font-medium',
        classes[variant],
      ].join(' ')}
    >
      {children}
    </motion.span>
  )
}
