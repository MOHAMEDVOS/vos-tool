import React, { useEffect } from 'react'
import { useQuotaStore } from '@/store/quotaStore'
import { useUiStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'

function MiniRing({ percent, isUnlimited }: { percent: number; isUnlimited: boolean }) {
  const circ = 289
  const offset = circ * (1 - percent)
  return (
    <div className="relative h-7 w-7">
      <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
        <circle stroke="var(--b-strong)" strokeWidth="14" fill="transparent" cx="60" cy="60" r="46" />
        <circle
          stroke="var(--t-primary)"
          strokeWidth="14"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          fill="transparent"
          cx="60" cy="60" r="46"
          style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(0.16,1,0.3,1)' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-[8px] font-bold text-t-primary">
        {isUnlimited ? '∞' : Math.round(percent * 100)}
      </div>
    </div>
  )
}

export function UsageCard() {
  const { usage, fetchUsage, isLoading } = useQuotaStore()
  const { sidebarCollapsed } = useUiStore()
  const { role } = useAuthStore()

  useEffect(() => {
    fetchUsage()
    const interval = setInterval(fetchUsage, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [fetchUsage])

  if (isLoading) {
    return sidebarCollapsed ? null : (
      <div className="mb-2 rounded-md p-3 animate-pulse shadow-[var(--shadow-border)] bg-surface-card">
        <div className="h-2 w-12 bg-[var(--surface-soft)] rounded mx-auto mb-3" />
        <div className="h-14 w-14 rounded-full border-[6px] border-[var(--b-strong)] mx-auto mb-3" />
        <div className="space-y-2">
          <div className="h-2 w-full bg-[var(--surface-soft)] rounded" />
          <div className="h-2 w-full bg-[var(--surface-soft)] rounded" />
        </div>
      </div>
    )
  }

  if (!usage) return null

  const isUnlimited = usage.daily_limit >= 999999
  const used = usage.current_count
  const total = usage.daily_limit
  const remaining = usage.remaining
  const ringPercent = isUnlimited ? 1 : Math.min(Math.max(remaining / total, 0), 1)
  const ringCircumference = 289
  const ringOffset = ringCircumference * (1 - ringPercent)
  const progressText = isUnlimited ? '∞' : String(used)
  const remainingText = isUnlimited ? 'UNLIMITED' : String(remaining)
  const title = (role === 'Admin' || role === 'Owner') ? 'ADMIN QUOTA' : 'DAILY CREDITS'

  if (sidebarCollapsed) {
    return (
      <div className="mx-auto my-2 flex flex-col items-center" title={title}>
        <MiniRing percent={ringPercent} isUnlimited={isUnlimited} />
      </div>
    )
  }

  return (
    <div className="mb-2 rounded-md p-3 shadow-[var(--shadow-border)] bg-surface-card">
      {/* Title */}
      <div className="mb-2.5 mono-label text-center">{title}</div>

      {/* Ring */}
      <div className="relative mx-auto mb-3 h-[56px] w-[56px]">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
          <circle
            stroke="var(--b-strong)"
            strokeWidth="10"
            fill="transparent"
            cx="60" cy="60" r="48"
          />
          <circle
            stroke="var(--t-primary)"
            strokeWidth="10"
            strokeDasharray={ringCircumference}
            strokeDashoffset={ringOffset}
            strokeLinecap="round"
            fill="transparent"
            cx="60" cy="60" r="48"
            style={{ transition: 'stroke-dashoffset 0.8s var(--ease-out)' }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`${isUnlimited ? 'text-[20px]' : 'text-[11px]'} font-semibold text-t-primary tabular-nums`}>
            {isUnlimited ? '∞' : Math.round(ringPercent * 100) + '%'}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="space-y-1">
        {[
          { label: 'Used',      value: progressText },
          { label: 'Left',      value: remainingText },
        ].map(({ label, value }) => (
          <div key={label} className="flex items-center justify-between">
            <span className="mono-label">{label}</span>
            <span className={`text-[12px] font-semibold tabular-nums text-t-primary ${value === 'UNLIMITED' ? 'text-accent-primary' : ''}`}>{value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
