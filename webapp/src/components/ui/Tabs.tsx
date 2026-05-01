import { motion } from 'framer-motion'

interface Tab {
  id: string
  label: string
  badge?: number
}

interface Props {
  tabs: Tab[]
  active: string
  onChange: (id: string) => void
  variant?: 'primary' | 'sub'
}

export function Tabs({ tabs, active, onChange, variant = 'primary' }: Props) {
  const isSub = variant === 'sub'

  return (
    <div className={[
      'flex',
      !isSub
        ? 'gap-6 border-b border-[var(--b-divider)]'
        : 'gap-1 p-1 rounded-lg shadow-[var(--shadow-border)] bg-surface-soft',
    ].join(' ')}>
      {tabs.map((t) => {
        const isActive = active === t.id
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={[
              'relative transition-colors duration-150 font-medium',
              !isSub
                ? [
                    'py-3 text-[13px] tracking-normal pb-[11px]',
                    isActive ? 'text-t-primary' : 'text-t-muted hover:text-t-secondary',
                  ].join(' ')
                : [
                    'px-3 py-1.5 text-[13px] rounded-md',
                    isActive
                      ? 'bg-surface-card text-t-primary shadow-[var(--shadow-border)]'
                      : 'text-t-muted hover:text-t-secondary hover:bg-[var(--hover-overlay)]',
                  ].join(' '),
            ].join(' ')}
          >
            <span className="flex items-center gap-1.5">
              {t.label}
              {t.badge !== undefined && t.badge > 0 && (
                <span className="rounded-full bg-[var(--ship-red)]/10 text-[var(--ship-red)] px-1.5 py-0.5 text-[10px] font-semibold leading-none">
                  {t.badge}
                </span>
              )}
            </span>

            {/* Underline indicator — primary tabs only */}
            {!isSub && isActive && (
              <motion.div
                layoutId="activeTab"
                className="absolute bottom-0 left-0 right-0 h-[1px] bg-t-primary"
                transition={{ type: 'spring', stiffness: 500, damping: 35 }}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}
