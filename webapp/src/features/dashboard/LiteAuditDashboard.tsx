import { useMemo, useState } from 'react'
import { useLiteAudits } from '@/hooks/useDashboard'
import { AuditTable } from '@/components/tables/AuditTable'
import { Metric } from '@/components/ui/Metric'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { isRowFlagged } from '@/utils/audit'
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
    (data?.records ?? []).map((r) => r.metadata as AgentAuditRow ?? {}),
  [data])

  const metrics = useMemo(() => {
    let flagged = 0, releasing = 0, lateHello = 0
    for (const r of rows) {
      if (isRowFlagged(r)) flagged++
      if (r['Releasing Detection'] === 'Yes') releasing++
      if (r['Late Hello Detection'] === 'Yes') lateHello++
    }
    return { total: rows.length, flagged, releasing, lateHello }
  }, [rows])

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (isError)   return <p className="text-sm text-ship-red">Failed to load lite audits.</p>
  if (!rows.length) return <p className="text-sm text-t-muted py-8">No lite audit data. Run audits first.</p>

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-black uppercase tracking-tight text-t-primary">Lite Audit</h2>
        <Button size="sm" variant="secondary" onClick={() => qc.invalidateQueries({ queryKey: ['lite-audits'] })}>
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-8 sm:grid-cols-4 py-2">
        <Metric label="Flagged Calls" value={metrics.flagged} />
        <Metric label="Releasing"     value={metrics.releasing} />
        <Metric label="Late Hello"    value={metrics.lateHello} />
        <Metric label="Total Calls"    value={metrics.total} />
      </div>

      <AuditTable rows={rows.filter(isRowFlagged)} />

      <div className="mt-2 flex flex-col items-start gap-4">
        <Button variant="secondary" onClick={() => alert('CSV download coming soon.')}>
          Download CSV
        </Button>

        {!showConfirm ? (
          <Button variant="danger" onClick={() => setShowConfirm(true)}>
            Clear Lite Audit Data
          </Button>
        ) : (
          <div className="rounded-xl border border-ship-red/30 bg-ship-red/10 p-4 max-w-lg shadow-2xl">
            <p className="mb-4 text-sm text-t-primary">
              <strong className="text-ship-red uppercase tracking-widest font-black mr-2">Warning:</strong> Permanently deletes all lite audit data. Cannot be undone.
            </p>
            <div className="flex gap-3">
              <Button variant="danger" onClick={() => clearData.mutate()} disabled={clearData.isPending}>
                {clearData.isPending ? 'Clearing...' : 'Confirm Delete'}
              </Button>
              <Button variant="secondary" onClick={() => setShowConfirm(false)} disabled={clearData.isPending}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
