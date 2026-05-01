import { useMemo, useState } from 'react'
import { useCampaignAudits, useCampaigns } from '@/hooks/useDashboard'
import { dashboardApi } from '@/api/dashboard'
import { AuditTable } from '@/components/tables/AuditTable'
import { Metric } from '@/components/ui/Metric'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { isRowFlagged } from '@/utils/audit'
import type { AgentAuditRow } from '@/types/api'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { CustomDatePicker } from '@/components/ui/DatePicker'
import { CustomSelect } from '@/components/ui/Select'

export function CampaignAuditDashboard() {
  const qc = useQueryClient()
  const [showConfirm, setShowConfirm] = useState(false)
  const { data: campaigns, isLoading: loadingCampaigns } = useCampaigns()
  const [selected, setSelected] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  const effectiveCampaign = selected || campaigns?.[0] || ''
  const { data, isLoading, isError } = useCampaignAudits(
    effectiveCampaign ? { campaign: effectiveCampaign, start_date: startDate, end_date: endDate } : undefined,
  )

  const clearData = useMutation({
    mutationFn: () => dashboardApi.clearCampaignAudits(effectiveCampaign),
    onSuccess: () => {
      setShowConfirm(false)
      qc.invalidateQueries({ queryKey: ['campaign-audits'] })
      qc.invalidateQueries({ queryKey: ['flagged-calls'] })
      qc.invalidateQueries({ queryKey: ['flagged-count'] })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    }
  })

  const rows = useMemo<AgentAuditRow[]>(() =>
    (data?.records ?? []).map((r) => r.metadata as AgentAuditRow ?? {}),
  [data])

  const displayRows = useMemo(() => {
    return rows.filter((r) => {
      const auditType = r['Audit Type'] || r['audit_type']
      if (auditType === 'Lite Audit' || auditType === 'Lite') {
        return isRowFlagged(r)
      }
      return true
    })
  }, [rows])

  const summary = useMemo(() => {
    let flagged = 0, releasing = 0, lateHello = 0, noRebuttal = 0
    for (const r of displayRows) {
      if (isRowFlagged(r)) flagged++
      if (r['Releasing Detection'] === 'Yes') releasing++
      if (r['Late Hello Detection'] === 'Yes') lateHello++
      if (r['Rebuttal Detection'] === 'No') noRebuttal++
    }
    return { total: displayRows.length, flagged, releasing, lateHello, noRebuttal }
  }, [displayRows])

  if (loadingCampaigns) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (!campaigns?.length) return <p className="text-sm text-t-muted py-8">No campaign data. Run a Campaign Audit first.</p>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-6">
        <CustomSelect 
          label="Campaign"
          options={campaigns}
          value={effectiveCampaign}
          onChange={(v) => setSelected(v)}
          className="w-64"
        />
        <CustomDatePicker 
          label="Start Date"
          value={startDate}
          onChange={setStartDate}
          className="w-48"
        />

        <CustomDatePicker 
          label="End Date"
          value={endDate}
          onChange={setEndDate}
          className="w-48"
        />

        <div className="pb-0.5">
          <Button size="md" variant="secondary" onClick={() => qc.invalidateQueries({ queryKey: ['campaign-audits'] })}>
            <RefreshCw size={14} /> Refresh
          </Button>
        </div>
      </div>



      {isLoading && <div className="flex justify-center py-10"><Spinner /></div>}
      {isError   && <p className="text-sm text-ship-red">Failed to load campaign audits.</p>}

      {!isLoading && !isError && (
        <>
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-5 py-2">
            <Metric label="Flagged Calls" value={summary.flagged} />
            <Metric label="Releasing"     value={summary.releasing} />
            <Metric label="Late Hello"    value={summary.lateHello} />
            <Metric label="No Rebuttal"   value={summary.noRebuttal} />
            <Metric label="Campaign"      value={effectiveCampaign} />
          </div>

          <AuditTable 
            rows={displayRows} 
            leftActions={
              !showConfirm ? (
                <button
                  onClick={() => setShowConfirm(true)}
                  disabled={!effectiveCampaign}
                  className="group relative px-6 py-2.5 rounded-xl bg-ship-red/10 hover:bg-ship-red/20 border border-ship-red/30 hover:border-ship-red/60 text-ship-red text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-300 shadow-xl active:scale-95 flex items-center gap-3 backdrop-blur-md overflow-hidden disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-ship-red/0 via-ship-red/20 to-ship-red/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
                  <span className="relative z-10">Clear Selected Campaign Data</span>
                </button>
              ) : (
                <div className="rounded-xl border border-ship-red/30 bg-c-base p-6 max-w-lg shadow-2xl backdrop-blur-xl absolute bottom-0 left-0 z-[60] mb-12">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-1 h-6 bg-ship-red rounded-full" />
                    <h3 className="text-xs font-black uppercase tracking-[0.2em] text-ship-red">Confirm Deletion</h3>
                  </div>
                  <p className="mb-6 text-xs text-t-primary leading-relaxed font-medium">
                    This action will permanently delete all audit data for campaign <span className="text-t-primary font-black underline decoration-ship-red/50">'{effectiveCampaign}'</span>. This cannot be undone.
                  </p>
                  <div className="flex justify-start gap-3">
                    <button 
                      onClick={() => clearData.mutate()} 
                      disabled={clearData.isPending}
                      className="px-5 py-2 rounded-lg bg-ship-red hover:bg-ship-red/80 text-t-primary text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-ship-red/20"
                    >
                      {clearData.isPending ? 'Processing...' : 'Permanently Delete'}
                    </button>
                    <button 
                      onClick={() => setShowConfirm(false)}
                      className="px-5 py-2 rounded-lg bg-c-raised hover:bg-vos-50 text-t-muted hover:text-t-primary text-[10px] font-black uppercase tracking-widest transition-all"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )
            }
          />
        </>
      )}
    </div>
  )
}
