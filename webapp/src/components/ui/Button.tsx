import { forwardRef } from 'react'
import { motion } from 'framer-motion'

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
}

/* Vercel button system:
   primary   = dark fill (#171717 light / #ededed dark), 6px radius
   secondary = white/dark fill + shadow-as-border ring
   ghost     = transparent, text only, subtle hover bg
   danger    = workflow red tint                              */

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = 'primary', size = 'md', className = '', children, disabled, ...rest }, ref) => {
    const base = [
      'inline-flex items-center justify-center gap-1.5 font-medium',
      'transition-colors duration-150 cursor-pointer select-none',
      'focus-visible:outline-none focus-visible:ring-2',
      'focus-visible:ring-[var(--b-focus)] focus-visible:ring-offset-2',
      'focus-visible:ring-offset-[var(--surface-page)]',
      'disabled:opacity-40 disabled:pointer-events-none',
      'rounded-md',
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
        'bg-[var(--semantic-error)]/10 text-[var(--semantic-error)] ' +
        'shadow-[inset_0_0_0_1px_var(--semantic-error)] ' +
        'hover:bg-[var(--semantic-error)]/15',
    }

    const sizes = {
      sm: 'px-3 py-1.5 text-[13px] leading-none',
      md: 'px-4 py-2 text-[14px] leading-[1.43]',
    }

    return (
      <motion.button
        ref={ref}
        whileHover={disabled ? undefined : { scale: 1.02 }}
        whileTap={disabled  ? undefined : { scale: 0.96 }}
        transition={{ type: 'spring', stiffness: 500, damping: 22 }}
        disabled={disabled}
        className={[...base, variants[variant], sizes[size], className].join(' ')}
        {...(rest as any)}
      >
        {children}
      </motion.button>
    )
  },
)
Button.displayName = 'Button'
