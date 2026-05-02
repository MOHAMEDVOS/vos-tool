import React, { forwardRef } from 'react'
import { motion } from 'framer-motion'

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'action'
  size?: 'sm' | 'md'
}

/* Vercel button system:
   primary   = dark fill (#171717 light / #ededed dark), 6px radius
   secondary = white/dark fill + shadow-as-border ring
   ghost     = transparent, text only, subtle hover bg
   danger    = workflow red tint
   action    = pill-shaped, uppercase, heavy tracking (dashboard buttons) */

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = 'primary', size = 'md', className = '', children, disabled, ...rest }, ref) => {
    const base = [
      'inline-flex items-center justify-center gap-1.5 font-medium',
      'transition-all duration-150 cursor-pointer select-none',
      'focus-visible:outline-none focus-visible:ring-2',
      'focus-visible:ring-[var(--b-focus)] focus-visible:ring-offset-2',
      'focus-visible:ring-offset-[var(--surface-page)]',
      'disabled:opacity-40 disabled:pointer-events-none',
      variant === 'action' ? 'rounded-full' : 'rounded-md',
    ]

    const variants = {
      primary:
        'bg-[var(--btn-primary-bg)] text-[var(--btn-primary-text)] ' +
        'hover:bg-[var(--btn-primary-hover)] ' +
        'shadow-[var(--shadow-accent)] hover:shadow-[var(--shadow-accent)]',

      secondary:
        'bg-[var(--btn-secondary-bg)] text-[var(--btn-secondary-text)] ' +
        'shadow-[var(--btn-secondary-shadow)] ' +
        'hover:bg-[var(--hover-overlay)]',

      ghost:
        'bg-transparent text-t-muted ' +
        'hover:bg-[var(--hover-overlay)] hover:text-t-primary',

      danger:
        'bg-[var(--semantic-error)] text-white ' +
        'hover:opacity-90 shadow-lg',

      action:
        'bg-[var(--btn-heavy-bg)] text-[var(--btn-heavy-text)] ' +
        'font-black uppercase tracking-[0.2em] ' +
        'hover:bg-[var(--btn-heavy-hover)] shadow-xl',
    }

    const sizes = {
      sm: 'px-3 py-1.5 leading-none',
      md: 'px-4 py-2 leading-[1.43]',
    }

    const textSizes = {
      action: 'text-[10px]',
      sm: 'text-[10px]',
      md: 'text-[10px]',
    }

    const currentTextSize = variant === 'action' ? textSizes.action : textSizes[size]

    return (
      <motion.button
        ref={ref}
        whileHover={disabled ? undefined : { scale: 1.02 }}
        whileTap={disabled  ? undefined : { scale: 0.96 }}
        transition={{ type: 'spring', stiffness: 500, damping: 22 }}
        disabled={disabled}
        className={[...base, variants[variant], sizes[size], currentTextSize, className].join(' ')}
        {...(rest as any)}
      >
        {children}
      </motion.button>
    )
  },
)
Button.displayName = 'Button'
