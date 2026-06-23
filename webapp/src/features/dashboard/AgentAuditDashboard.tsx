import { useMemo, useState } from 'react'
import { useAgentAudits } from '@/hooks/useDashboard'
import { AuditTable } from '@/components/tables/AuditTable'
import { Metric } from '@/components/ui/Metric'
import { Button, DestroyButton } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { isRowFlagged } from '@/utils/audit'
import type { AgentAuditRow } from '@/types/api'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { dashboardApi } from '@/api/dashboard'
import { RefreshCw, AlertTriangle } from 'lucide-react'

const FLAG_THRESHOLD = 5

export function AgentAuditDashboard() {
  const qc = useQueryClient()
  const [showConfirm, setShowConfirm] = useState(false)
  const { data, isLoading, isError } = useAgentAudits()

  const clearData = useMutation({
    mutationFn: () => dashboardApi.clearAgentAudits(),
    onSuccess: () => {
      setShowConfirm(false)
      qc.invalidateQueries({ queryKey: ['agent-audits'] })
      qc.invalidateQueries({ queryKey: ['flagged-calls'] })
      qc.invalidateQueries({ queryKey: ['badge-count'] })
    },
  })

  const rows = useMemo(() => {
    const raw: AgentAuditRow[] = (data?.records ?? []).map((r) => r.metadata as AgentAuditRow ?? {})
    return [...raw].sort((a, b) =>
      (a['Agent Name'] ?? '').toString().toLowerCase() < (b['Agent Name'] ?? '').toString().toLowerCase() ? -1 : 1,
    )
  }, [data])

  const metrics = useMemo(() => {
    let releasing = 0, lateHello = 0, noRebuttal = 0
    for (const r of rows) {
      if (r['Releasing Detection'] === 'Yes') releasing++
      if (r['Late Hello Detection'] === 'Yes') lateHello++
      if (r['Rebuttal Detection'] === 'No') noRebuttal++
    }
    return { total: rows.length, releasing, lateHello, noRebuttal }
  }, [rows])

  const problematicAgents = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const r of rows) {
      const name = String(r['Agent Name'] ?? 'Unknown')
      if (isRowFlagged(r)) counts[name] = (counts[name] ?? 0) + 1
    }
    return Object.entries(counts).filter(([, c]) => c >= FLAG_THRESHOLD)
  }, [rows])

  const problematicAgentNames = useMemo(() => new Set(problematicAgents.map(([n]) => n)), [problematicAgents])

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (isError)   return <p className="text-sm text-ship-red">Failed to load agent audits.</p>
  if (!rows.length) return <p className="text-sm text-t-muted py-8">No agent audit data. Run audits first.</p>

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-black uppercase tracking-tight text-t-primary">Agent Audit</h2>
        <Button size="sm" variant="action" onClick={() => qc.invalidateQueries({ queryKey: ['agent-audits'] })}>
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-8 sm:grid-cols-4 py-2">
        <Metric label="Total Calls"       value={metrics.total} />
        <Metric label="Late Hello Calls"  value={metrics.lateHello} />
        <Metric label="Missing Rebuttals" value={metrics.noRebuttal} />
      </div>

      {problematicAgents.length > 0 && (
        <div className="rounded-xl border border-[#d97706]/20 bg-[#d97706]/5 p-5 shadow-2xl backdrop-blur-sm">
          <div className="mb-4 flex items-center gap-2.5 text-[text-semantic-warning] text-[10px] font-black uppercase tracking-[0.2em]">
            <AlertTriangle size={14} strokeWidth={3} /> Attention Required
          </div>
          <div className="flex flex-wrap gap-2.5">
            {problematicAgents.map(([name, count]) => (
              <span key={name} className="rounded-md bg-[#d97706]/10 border border-[#d97706]/20 px-3 py-1.5 text-xs font-bold text-[text-semantic-warning] shadow-sm">
                {name}: {count} flagged
              </span>
            ))}
          </div>
        </div>
      )}

      <AuditTable
        rows={rows}
        excludeColumns={['Long VM/Dead Detection']}
        getRowClassName={(r) => problematicAgentNames.has(String(r['Agent Name'] || '')) ? 'border-l-2 border-l-ship-red' : ''}
        leftActions={
          !showConfirm ? (
            <DestroyButton onClick={() => setShowConfirm(true)}>
              Clear Agent Audit Data
            </DestroyButton>
          ) : (
          <div className="flex flex-col gap-3 p-4 rounded-xl border border-ship-red/20 bg-ship-red/5 min-w-[300px]">
            <div className="flex items-center gap-2">
              <AlertTriangle size={14} className="text-ship-red" strokeWidth={3} />
              <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-ship-red">Confirm Deletion</h3>
            </div>
            <p className="text-[10px] text-t-primary leading-relaxed font-bold opacity-80">
              Permanently delete all agent audit data?
            </p>
            <div className="flex justify-start gap-2">
              <DestroyButton
                size="sm"
                onClick={() => clearData.mutate()}
                disabled={clearData.isPending}
              >
                {clearData.isPending ? 'Clearing...' : 'Yes, Delete All'}
              </DestroyButton>
              <Button size="sm" variant="action" onClick={() => setShowConfirm(false)}>
                Cancel
              </Button>
            </div>
          </div>
          )
        }
      />
    </div>
  )
}
