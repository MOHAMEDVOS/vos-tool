import { useMemo, useState } from 'react'
import { useCampaignAudits, useCampaigns } from '@/hooks/useDashboard'
import { dashboardApi } from '@/api/dashboard'
import { AuditTable } from '@/components/tables/AuditTable'
import { Metric } from '@/components/ui/Metric'
import { Button, DestroyButton } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { SuccessFlash } from '@/components/ui/SuccessFlash'
import { isRowFlagged } from '@/utils/audit'
import type { AgentAuditRow } from '@/types/api'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, FileText } from 'lucide-react'
import { CustomDatePicker } from '@/components/ui/DatePicker'
import { CustomSelect } from '@/components/ui/Select'
import { useGenerateCampaignReport } from '@/hooks/useReports'

export function CampaignAuditDashboard() {
  const qc = useQueryClient()
  const [showConfirm, setShowConfirm] = useState(false)
  const [reportLinks, setReportLinks] = useState<{ sheet_url: string } | null>(null)
  const [reportError, setReportError] = useState<string | null>(null)
  const { data: campaigns, isLoading: loadingCampaigns } = useCampaigns()
  const [selected, setSelected] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  const generateReport = useGenerateCampaignReport()

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
          <Button size="md" variant="action" onClick={() => qc.invalidateQueries({ queryKey: ['campaign-audits'] })}>
            <RefreshCw size={14} /> Refresh
          </Button>
        </div>
      </div>



      {isLoading && <div className="flex justify-center py-10"><Spinner /></div>}
      {isError   && <p className="text-sm text-ship-red">Failed to load campaign audits.</p>}

      {!isLoading && !isError && (
        <>
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-5 py-2">
            <Metric label="Total Calls"   value={summary.total} />
            <Metric label="Releasing"     value={summary.releasing} />
            <Metric label="Late Hello"    value={summary.lateHello} />
            <Metric label="No Rebuttal"   value={summary.noRebuttal} />
            <Metric label="Campaign"      value={effectiveCampaign} />
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Button
              size="md"
              variant="action"
              disabled={!effectiveCampaign || generateReport.isPending}
              onClick={async () => {
                setReportLinks(null)
                setReportError(null)
                try {
                  const result = await generateReport.mutateAsync({
                    campaign: effectiveCampaign,
                    start_date: startDate || undefined,
                    end_date: endDate || undefined,
                  })
                  setReportLinks(result)
                } catch (err) {
                  setReportError(err instanceof Error ? err.message : 'Report generation failed')
                }
              }}
            >
              <FileText size={14} />
              {generateReport.isPending ? 'Generating…' : 'Generate Campaign Report'}
            </Button>

            <SuccessFlash show={generateReport.isSuccess} label="Report ready" />

            {reportLinks && (
              <a
                href={reportLinks.sheet_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2"
              >
                Open Sheet
              </a>
            )}

            {reportError && (
              <p className="text-xs text-ship-red">{reportError}</p>
            )}
          </div>

          <AuditTable 
            rows={displayRows} 
            excludeColumns={['Time']}
            leftActions={
              !showConfirm ? (
                <DestroyButton
                  onClick={() => setShowConfirm(true)}
                  disabled={!effectiveCampaign}
                >
                  Clear Selected Campaign Data
                </DestroyButton>
              ) : (
                <div className="rounded-xl border border-b-strong bg-c-base p-6 max-w-lg shadow-2xl absolute bottom-0 left-0 z-[60] mb-12">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-1 h-6 bg-[#c0392b] rounded-full" />
                    <h3 className="text-xs font-black uppercase tracking-[0.2em] text-[#e74c3c]">Confirm Deletion</h3>
                  </div>
                  <p className="mb-6 text-xs text-t-primary leading-relaxed font-medium">
                    Permanently delete all audit data for campaign <span className="text-t-primary font-black underline decoration-[#c0392b]/50">'{effectiveCampaign}'</span>. This cannot be undone.
                  </p>
                  <div className="flex justify-start gap-3">
                    <DestroyButton
                      onClick={() => clearData.mutate()}
                      disabled={clearData.isPending}
                    >
                      {clearData.isPending ? 'Processing...' : 'Permanently Delete'}
                    </DestroyButton>
                    <Button
                      variant="action"
                      onClick={() => setShowConfirm(false)}
                    >
                      Cancel
                    </Button>
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
