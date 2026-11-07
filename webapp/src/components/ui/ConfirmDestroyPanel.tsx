import type { ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button, DestroyButton } from './Button'

interface ConfirmDestroyPanelProps {
  /** Controlled open state -- parent owns it so it can close the panel from a mutation's onSuccess. */
  open: boolean
  onOpenChange: (open: boolean) => void
  triggerLabel: ReactNode
  triggerDisabled?: boolean
  message: ReactNode
  confirmLabel: string
  pendingLabel: string
  isPending: boolean
  onConfirm: () => void
  /** Show the AlertTriangle icon next to "Confirm Deletion" (AgentAuditDashboard only). */
  showIcon?: boolean
}

// Shared delete-confirmation UI: a DestroyButton that swaps into a confirm/cancel panel.
// Used by AgentAuditDashboard, LiteAuditDashboard, and CampaignAuditDashboard, which each
// used to reimplement this markup with their own copy/paste.
export function ConfirmDestroyPanel({
  open,
  onOpenChange,
  triggerLabel,
  triggerDisabled,
  message,
  confirmLabel,
  pendingLabel,
  isPending,
  onConfirm,
  showIcon,
}: ConfirmDestroyPanelProps) {
  if (!open) {
    return (
      <DestroyButton onClick={() => onOpenChange(true)} disabled={triggerDisabled}>
        {triggerLabel}
      </DestroyButton>
    )
  }

  return (
    <div className="flex flex-col gap-3 p-4 rounded-xl border border-ship-red/20 bg-ship-red/5 min-w-[300px]">
      <div className="flex items-center gap-2">
        {showIcon && <AlertTriangle size={14} className="text-ship-red" strokeWidth={3} />}
        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-ship-red">Confirm Deletion</h3>
      </div>
      <p className="text-[10px] text-t-primary leading-relaxed font-bold opacity-80">
        {message}
      </p>
      <div className="flex justify-start gap-2">
        <DestroyButton size="sm" onClick={onConfirm} disabled={isPending}>
          {isPending ? pendingLabel : confirmLabel}
        </DestroyButton>
        <Button size="sm" variant="action" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
