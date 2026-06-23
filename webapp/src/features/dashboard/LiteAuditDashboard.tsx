import { useMemo, useState } from 'react'
import { useLiteAudits } from '@/hooks/useDashboard'
import { AuditTable } from '@/components/tables/AuditTable'
import { Metric } from '@/components/ui/Metric'
import { Button, DestroyButton } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { isRowFlagged, isLongCallFlagged, dedupeLongCallRows } from '@/utils/audit'
import type { AgentAuditRow } from '@/types/api'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { dashboardApi } from '@/api/dashboard'
import { RefreshCw } from 'lucide-react'

export function LiteAuditDashboard() {
  const qc = useQueryClient()
  const [showConfirm, setShowConfirm] = useState(false)
  const { data, isLoading, isError } = useLiteAudits()

  const clearData = useMutation({
    mutationFn: () => dashboardApi.clearLiteAudits(),
    onSuccess: () => {
      setShowConfirm(false)
      qc.invalidateQueries({ queryKey: ['lite-audits'] })
      qc.invalidateQueries({ queryKey: ['flagged-calls'] })
      qc.invalidateQueries({ queryKey: ['flagged-count'] })
    },
  })

  const rows = useMemo<AgentAuditRow[]>(() =>
    dedupeLongCallRows((data?.records ?? []).map((r) => r.metadata as AgentAuditRow ?? {})),
  [data])

  const metrics = useMemo(() => {
    let flagged = 0, releasing = 0, lateHello = 0, longCall = 0
    for (const r of rows) {
      if (isRowFlagged(r)) flagged++
      if (r['Releasing Detection'] === 'Yes') releasing++
      if (r['Late Hello Detection'] === 'Yes') lateHello++
      if (isLongCallFlagged(r['Long VM/Dead Detection'])) longCall++
    }
    return { total: rows.length, flagged, releasing, lateHello, longCall }
  }, [rows])

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (isError)   return <p className="text-sm text-ship-red">Failed to load lite audits.</p>
  if (!rows.length) return <p className="text-sm text-t-muted py-8">No lite audit data. Run audits first.</p>

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-black uppercase tracking-tight text-t-primary">Lite Audit</h2>
        <Button size="sm" variant="action" onClick={() => qc.invalidateQueries({ queryKey: ['lite-audits'] })}>
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-8 sm:grid-cols-5 py-2">
        <Metric label="Flagged Calls" value={metrics.flagged} />
        <Metric label="Releasing"     value={metrics.releasing} />
        <Metric label="Late Hello"    value={metrics.lateHello} />
        <Metric label="Long VM/Dead"  value={metrics.longCall} />
        <Metric label="Total Calls"    value={metrics.total} />
      </div>

      <AuditTable 
        rows={rows.filter(isRowFlagged)} 
        leftActions={
          <div className="flex gap-4 items-center">
            <Button variant="action" onClick={() => alert('CSV download coming soon.')}>
              Download CSV
            </Button>

            {!showConfirm ? (
              <DestroyButton onClick={() => setShowConfirm(true)}>
                Clear Lite Audit Data
              </DestroyButton>
            ) : (
              <div className="flex flex-col gap-3 p-4 rounded-xl border border-ship-red/20 bg-ship-red/5 min-w-[300px]">
                <div className="flex items-center gap-2">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-ship-red text-center">Confirm Deletion</h3>
                </div>
                <p className="text-[10px] text-t-primary leading-relaxed font-bold opacity-80">
                  Permanently delete all lite audit data?
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
            )}
          </div>
        }
      />
    </div>
  )
}
