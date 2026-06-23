import { useMemo, useState, useCallback } from 'react'
import { useCampaignAudits, useCampaigns, useCampaignDisposition } from '@/hooks/useDashboard'
import { dashboardApi } from '@/api/dashboard'
import { AuditTable } from '@/components/tables/AuditTable'
import { Metric } from '@/components/ui/Metric'
import { Button, DestroyButton } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { SuccessFlash } from '@/components/ui/SuccessFlash'
import { isRowFlagged } from '@/utils/audit'
import type { AgentAuditRow, ReachabilityScan } from '@/types/api'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, FileText } from 'lucide-react'
import { CustomDatePicker } from '@/components/ui/DatePicker'
import { CustomSelect } from '@/components/ui/Select'
import { useGenerateCampaignReport } from '@/hooks/useReports'

function buildCopyText(scan: ReachabilityScan): string {
  const verdictLabel = scan.verdict === 'LOW' ? 'low' : 'good'
  const lines = [
    `This campaign shows ${verdictLabel} reachability.`,
    '',
    `Low Engagement (${scan.low_total.toLocaleString()} calls):`,
    ...Object.entries(scan.low_counts).map(([k, v]) => `• ${k}: ${v.toLocaleString()}`),
    '',
    `Good Engagement (${scan.good_total.toLocaleString()} calls):`,
    ...Object.entries(scan.good_counts).map(([k, v]) => `• ${k}: ${v.toLocaleString()}`),
    '',
    scan.verdict === 'LOW'
      ? 'Low engagement exceeds good engagement — action may be needed to improve contact rates.'
      : 'Good engagement exceeds low engagement — campaign is performing well.',
  ]
  return lines.join('\n')
}

function ReachabilityPanel({ scan }: { scan: ReachabilityScan }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(buildCopyText(scan)).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [scan])

  const isLow = scan.verdict === 'LOW'

  return (
    <div className={`rounded-xl border bg-surface-card p-5 ${isLow ? 'border-amber-500/30' : 'border-green-500/30'}`}>
      <div className="flex items-start justify-between gap-4 mb-1">
        <div className={`flex items-center gap-2 text-base font-bold ${isLow ? 'text-amber-400' : 'text-green-500'}`}>
          <span>{isLow ? '⚠️' : '✅'}</span>
          <span>This campaign shows {isLow ? 'low' : 'good'} reachability.</span>
        </div>
        <button
          onClick={handleCopy}
          className="shrink-0 rounded-md border border-b-subtle px-3 py-1 text-xs font-semibold text-t-muted hover:text-t-primary hover:border-b-medium transition-colors"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      <p className="text-xs text-t-muted mb-4">
        {scan.campaign_name} · {scan.scan_date} · {scan.total_calls.toLocaleString()} calls scanned
      </p>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className={`rounded-lg border bg-surface-soft p-4 ${isLow ? 'border-amber-500/20' : 'border-b-subtle'}`}>
          <p className="text-[10px] font-black uppercase tracking-widest text-t-muted mb-1">Low Engagement</p>
          <p className={`text-2xl font-black mb-3 ${isLow ? 'text-amber-400' : 'text-t-secondary'}`}>
            {scan.low_total.toLocaleString()}
          </p>
          <ul className="space-y-1.5">
            {Object.entries(scan.low_counts).map(([label, count]) => (
              <li key={label} className="flex justify-between text-xs text-t-muted">
                <span>{label}</span>
                <span className="font-bold text-t-primary tabular-nums">{count.toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className={`rounded-lg border bg-surface-soft p-4 ${!isLow ? 'border-green-500/20' : 'border-b-subtle'}`}>
          <p className="text-[10px] font-black uppercase tracking-widest text-t-muted mb-1">Good Engagement</p>
          <p className={`text-2xl font-black mb-3 ${!isLow ? 'text-green-500' : 'text-t-secondary'}`}>
            {scan.good_total.toLocaleString()}
          </p>
          <ul className="space-y-1.5">
            {Object.entries(scan.good_counts).map(([label, count]) => (
              <li key={label} className="flex justify-between text-xs text-t-muted">
                <span>{label}</span>
                <span className="font-bold text-t-primary tabular-nums">{count.toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className={`rounded-lg border px-4 py-3 text-xs text-t-muted leading-relaxed ${isLow ? 'border-amber-500/20 bg-amber-500/5' : 'border-green-500/20 bg-green-500/5'}`}>
        {isLow
          ? <>Low engagement exceeds good engagement — <span className={`font-bold ${isLow ? 'text-amber-400' : 'text-green-500'}`}>action may be needed to improve contact rates.</span></>
          : <>Good engagement exceeds low engagement — <span className="font-bold text-green-500">campaign is performing well.</span></>
        }
      </div>
    </div>
  )
}

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
  const { data: reachScan } = useCampaignDisposition(
    effectiveCampaign
      ? { campaign: effectiveCampaign, start_date: startDate || undefined, end_date: endDate || undefined }
      : undefined
  )

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
          {reachScan && <ReachabilityPanel scan={reachScan} />}

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
                <div className="flex flex-col gap-3 p-4 rounded-xl border border-ship-red/20 bg-ship-red/5 min-w-[300px]">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-ship-red">Confirm Deletion</h3>
                  </div>
                  <p className="text-[10px] text-t-primary leading-relaxed font-bold opacity-80">
                    Delete all audit data for campaign <span className="underline decoration-ship-red/50">'{effectiveCampaign}'</span>?
                  </p>
                  <div className="flex justify-start gap-2">
                    <DestroyButton
                      size="sm"
                      onClick={() => clearData.mutate()}
                      disabled={clearData.isPending}
                    >
                      {clearData.isPending ? 'Processing...' : 'Yes, Delete All'}
                    </DestroyButton>
                    <Button
                      size="sm"
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
