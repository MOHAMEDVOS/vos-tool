import { useMemo, useState, useEffect } from 'react'
import { useFlaggedCalls, useAgentAudits, useLiteAudits } from '@/hooks/useDashboard'
import { useBadgeStore } from '@/store/badgeStore'
import { Button, DestroyButton } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import type { FlaggedCall } from '@/types/api'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { dashboardApi } from '@/api/dashboard'
import { RefreshCw, Search, Check, Copy, ArrowUp, ArrowDown, Trash2 } from 'lucide-react'
import { CustomSelect } from '@/components/ui/Select'
import { motion, AnimatePresence } from 'framer-motion'
import { CountUp, Metric } from '@/components/ui/Metric'
import { CallCard } from '@/components/CallCard'
import { dedupeLongCallRows, isLongCallFlagged, isFairRebuttalMiss, getCallIssues, buildAgentDeductions } from '@/utils/audit'

type FlagTypeFilter = 'All Flags' | 'Releasing' | 'Late Hello' | 'No Rebuttal' | 'Wrong Dispo' | 'Long VM/Dead'

const ALL_AGENTS = 'All Agents'

const FLAG_TYPE_OPTIONS: FlagTypeFilter[] = ['All Flags', 'Releasing', 'Late Hello', 'No Rebuttal', 'Wrong Dispo', 'Long VM/Dead']

// Mirrors callIssues() below -- one call can match more than one flag type.
function callMatchesFlagType(c: FlaggedCall, filter: FlagTypeFilter): boolean {
  switch (filter) {
    case 'All Flags': return true
    case 'Releasing': return c['Releasing Detection'] === 'Yes'
    case 'Late Hello': return c['Late Hello Detection'] === 'Yes'
    case 'No Rebuttal': return isFairRebuttalMiss(c)
    case 'Wrong Dispo': return c['Wrong Dispo Detection'] === 'Yes'
    case 'Long VM/Dead': return isLongCallFlagged(c['Long VM/Dead Detection'])
  }
}

export interface AgentDeductionRow {
  agentName: string; totalCalls: number; flaggedCalls: number
  releasing: number; lateHello: number; noRebuttals: number; longCall: number
  wrongDispo: number
  dialerNames: string[]; deduction: boolean
}


export function AgentDeductionsTable({
  rows,
  onDeleteAgent,
  deletingAgent,
  deletableAgents,
  onSelectAgent,
  selectedAgent,
}: {
  rows: AgentDeductionRow[]
  onDeleteAgent?: (agentName: string) => void
  deletingAgent?: string | null
  deletableAgents?: Set<string>
  onSelectAgent?: (agentName: string) => void
  selectedAgent?: string | null
}) {
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [sortCol, setSortCol] = useState<keyof AgentDeductionRow | null>('flaggedCalls')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const headers: { key: keyof AgentDeductionRow; label: string; cls: string }[] = [
    { key: 'agentName',    label: 'Agent Name',     cls: 'w-[22%]' },
    { key: 'totalCalls',   label: 'Total',          cls: 'text-right' },
    { key: 'flaggedCalls', label: 'Flagged',        cls: 'text-right' },
    { key: 'releasing',    label: 'Releasing',      cls: 'text-right' },
    { key: 'lateHello',    label: 'Late Hello',     cls: 'text-right' },
    { key: 'noRebuttals',  label: 'No Rebuttals',   cls: 'text-right' },
    { key: 'longCall',     label: 'Long VM/Dead',   cls: 'text-right' },
    { key: 'wrongDispo',   label: 'Wrong Dispo',    cls: 'text-right' },
    { key: 'dialerNames',  label: 'Dialer(s)',      cls: '' },
    { key: 'deduction',    label: 'Deduction',      cls: '' },
  ]
  if (onDeleteAgent) headers.push({ key: 'agentName', label: 'Delete', cls: 'w-16' })

  const sortedRows = useMemo(() => {
    if (!sortCol) return rows
    return [...rows].sort((a, b) => {
      let va = a[sortCol]
      let vb = b[sortCol]
      
      if (Array.isArray(va)) va = va.join(', ')
      if (Array.isArray(vb)) vb = vb.join(', ')

      const sa = String(va ?? '').toLowerCase()
      const sb = String(vb ?? '').toLowerCase()

      if (typeof va === 'number' && typeof vb === 'number') {
        return sortDir === 'asc' ? va - vb : vb - va
      }
      
      return sortDir === 'asc' ? sa.localeCompare(sb) : sb.localeCompare(sa)
    })
  }, [rows, sortCol, sortDir])

  const toggleSort = (key: keyof AgentDeductionRow) => {
    if (sortCol === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(key)
      setSortDir('desc')
    }
  }

  return (
    <div className="rounded-lg shadow-card border border-b-subtle overflow-hidden bg-c-base">
      <div className="overflow-auto max-h-[380px] resize-y min-h-[200px] custom-scrollbar">
        <table className="w-full table-fixed border-collapse text-sm relative">
          <thead className="sticky top-0 z-20 bg-c-base shadow-[inset_0_-1px_0_rgba(255,255,255,0.05)]">
            <tr>
              {headers.map((h) => {
                const isSorted = sortCol === h.key
                return (
                  <th 
                    key={`${h.label}-${h.key}`}
                    onClick={() => { if (h.label !== 'Delete') toggleSort(h.key) }}
                    className={`${h.cls} border-r border-b-subtle px-2.5 py-2.5 text-left text-[10px] font-black uppercase tracking-[0.12em] text-vos-500 leading-tight last:border-r-0 ${h.label !== 'Delete' ? 'cursor-pointer hover:bg-c-raised/30' : ''} transition-colors select-none`}
                  >
                    <div className={`flex items-center gap-2 ${h.cls.includes('text-right') ? 'justify-end' : 'justify-start'}`}>
                      {h.label}
                      {h.label !== 'Delete' && <span className={`transition-opacity duration-200 ${isSorted ? 'opacity-100' : 'opacity-0'}`}>
                        {sortDir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
                      </span>}
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>
        <tbody className="divide-y divide-b-subtle">
          {sortedRows.map((row, idx) => {
            const flagBg = row.flaggedCalls >= 5 
              ? 'bg-[var(--semantic-error-bg)] text-semantic-error' 
              : row.flaggedCalls === 4 
                ? 'bg-[var(--semantic-warning-bg)] text-semantic-warning' 
                : ''
            const deductionBg = row.flaggedCalls >= 5 
              ? 'bg-[var(--semantic-error-bg)] text-semantic-error' 
              : row.flaggedCalls === 4
                ? 'bg-[var(--semantic-warning-bg)] text-semantic-warning'
                : 'bg-[var(--semantic-success-bg)] text-semantic-success'
            const flagText = 'font-black'
            const deductionText = 'text-t-primary font-black'
            const copyId = `action-${idx}`
            
            return (
              <tr
                key={row.agentName}
                onClick={() => onSelectAgent?.(row.agentName)}
                className={`hover:bg-c-raised/50 transition-colors group/row ${onSelectAgent ? 'cursor-pointer' : ''} ${selectedAgent === row.agentName ? 'bg-c-raised/50' : ''}`}
              >
                <td className="border-r border-b-subtle px-2.5 py-2.5 text-t-primary font-medium group/cell relative">
                  <div className="flex items-center justify-start gap-2">
                    <span className="block break-words">{row.agentName}</span>
                    <button 
                      onClick={(e) => { e.stopPropagation(); copyToClipboard(row.agentName, copyId) }}
                      className="opacity-0 group-hover/cell:opacity-100 p-1 rounded hover:bg-c-raised transition-all text-vos-500 hover:text-t-primary shrink-0"
                    >
                      <AnimatePresence mode="wait">
                        {copiedId === copyId ? (
                          <motion.div key="check" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                            <Check size={12} className="text-green-500" />
                          </motion.div>
                        ) : (
                          <motion.div key="copy" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                            <Copy size={12} />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </button>
                  </div>
                </td>
                <td className="border-r border-b-subtle px-2.5 py-2.5 whitespace-nowrap text-right text-t-primary tabular-nums font-medium">
                  <CountUp value={row.totalCalls} />
                </td>
                <td className={`border-r border-b-subtle px-2.5 py-2.5 whitespace-nowrap text-right tabular-nums font-bold ${flagBg} ${flagText}`}>
                  <CountUp value={row.flaggedCalls} />
                </td>
                <td className="border-r border-b-subtle px-2.5 py-2.5 whitespace-nowrap text-right text-t-primary tabular-nums font-medium">
                  <CountUp value={row.releasing} />
                </td>
                <td className="border-r border-b-subtle px-2.5 py-2.5 whitespace-nowrap text-right text-t-primary tabular-nums font-medium">
                  <CountUp value={row.lateHello} />
                </td>
                <td className="border-r border-b-subtle px-2.5 py-2.5 whitespace-nowrap text-right text-t-primary tabular-nums font-medium">
                  <CountUp value={row.noRebuttals} />
                </td>
                <td className="border-r border-b-subtle px-2.5 py-2.5 whitespace-nowrap text-right text-t-primary tabular-nums font-medium">
                  <CountUp value={row.longCall} />
                </td>
                <td className="border-r border-b-subtle px-2.5 py-2.5 whitespace-nowrap text-right text-t-primary tabular-nums font-medium">
                  <CountUp value={row.wrongDispo} />
                </td>
                <td className="border-r border-b-subtle px-2.5 py-2.5 text-t-primary font-medium">
                  <span className="block break-words">{row.dialerNames.length ? row.dialerNames.join(' & ') : '—'}</span>
                </td>
                <td className={`px-2.5 py-2.5 whitespace-nowrap font-black uppercase tracking-widest text-[10px] ${deductionBg} ${deductionText}`}>{row.deduction ? 'Yes' : 'No'}</td>
                {onDeleteAgent && (
                  <td className="px-2 py-2.5 text-center">
                    {(!deletableAgents || deletableAgents.has(row.agentName)) ? <button
                      type="button"
                      aria-label={`Delete audit results for ${row.agentName}`}
                      title={`Delete Agent and Lite Audit results for ${row.agentName}`}
                      disabled={Boolean(deletingAgent)}
                      onClick={(e) => {
                        e.stopPropagation()
                        const confirmed = window.confirm(
                          `Permanently delete Agent Audit and Lite Audit results for ${row.agentName} from your shared dashboard? This removes matching calls from Agent Audit, Lite Audit, and Actions. Separate Campaign Audit results are not deleted.`,
                        )
                        if (confirmed) onDeleteAgent(row.agentName)
                      }}
                      className="rounded p-1.5 text-vos-500 transition-colors hover:bg-ship-red/10 hover:text-ship-red disabled:cursor-wait disabled:opacity-50"
                    >
                      <Trash2 size={14} />
                    </button> : <span className="text-vos-600" title="No Agent or Lite Audit results to delete">—</span>}
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
        </table>
      </div>
    </div>
  )
}


export function ActionsPage() {
  const qc = useQueryClient()
  const { data: flaggedCalls, isLoading: flaggedLoading, isError: flaggedError } = useFlaggedCalls()
  const { data: allAuditsData, isLoading: auditsLoading } = useAgentAudits()
  const { data: liteAuditsData, isLoading: liteLoading } = useLiteAudits()
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [flagTypeFilter, setFlagTypeFilter] = useState<FlagTypeFilter>('All Flags')
  const [search, setSearch] = useState('')
  const [expandedList, setExpandedList] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleteNotice, setDeleteNotice] = useState<string | null>(null)
  const markAsSeen = useBadgeStore(s => s.markAsSeen)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const deleteAgentAudits = useMutation({
    mutationFn: (agentName: string) => dashboardApi.deleteAgentAudits(agentName),
    onSuccess: (result, agentName) => {
      setDeleteError(null)
      setDeleteNotice(`${result.deleted_agent_audit_count} Agent Audit and ${result.deleted_lite_audit_count} Lite Audit result${result.deleted_lite_audit_count === 1 ? '' : 's'} deleted for ${agentName}.`)
      qc.invalidateQueries({ queryKey: ['agent-audits'] })
      qc.invalidateQueries({ queryKey: ['lite-audits'] })
      qc.invalidateQueries({ queryKey: ['flagged-calls'] })
      qc.invalidateQueries({ queryKey: ['flagged-count'] })
    },
    onError: () => setDeleteError('Could not delete this agent’s audit results. Please try again.'),
  })

  // Normalize a phone to (xxx) xxx-xxxx. Idempotent: already-formatted values re-format the
  // same; non-10-digit values (and 'Unknown') pass through untouched.
  const formatPhone = (raw: unknown): string => {
    const s = String(raw ?? '').trim()
    if (!s) return 'Unknown'
    let d = s.replace(/\D/g, '')
    if (d.length === 11 && d.startsWith('1')) d = d.slice(1)
    if (d.length !== 10) return s
    return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`
  }

  // Build the human issue labels for one flagged call (shared by the list + Copy All).
  const callIssues = getCallIssues

  const isLoading = flaggedLoading || auditsLoading || liteLoading
  const isError = flaggedError

  const allAuditRecords = useMemo(() => {
    const agentRecords = allAuditsData?.records?.map((r) => r.metadata ?? r) ?? []
    const liteRecords = liteAuditsData?.records?.map((r) => r.metadata ?? r) ?? []
    return [...agentRecords, ...liteRecords]
  }, [allAuditsData, liteAuditsData])

  const totalCallsMap = useMemo(() => {
    const map = new Map<string, number>()
    for (const row of allAuditRecords) {
      const name = ((row as Record<string, unknown>)['Agent Name'] as string | undefined)?.trim()
      if (name) map.set(name, (map.get(name) ?? 0) + 1)
    }
    return map
  }, [allAuditRecords])

  const deletableAgents = useMemo(() => new Set(
    [...(allAuditsData?.records ?? []), ...(liteAuditsData?.records ?? [])]
      .map((record) => String(((record.metadata ?? record) as Record<string, unknown>)['Agent Name'] ?? '').trim())
      .filter(Boolean),
  ), [allAuditsData, liteAuditsData])

  const auditedDialers = useMemo(() => {
    const map = new Map<string, number>()
    for (const row of allAuditRecords) {
      const r = row as Record<string, unknown>
      const dialer = (r['Dialer Name'] || r['dialer_name'] || r['Dialer']) as string | undefined
      if (dialer && dialer !== 'N/A' && dialer !== 'Unknown') map.set(dialer, (map.get(dialer) ?? 0) + 1)
    }
    return Array.from(map.entries()).map(([dialer, count]) => ({ dialer, count })).sort((a, b) => b.count - a.count)
  }, [allAuditRecords])

  // Long VM/Dead rows duplicate on repeat audits (deterministic from CSV) — dedupe before use.
  const dedupedCalls = useMemo<FlaggedCall[]>(() => dedupeLongCallRows(flaggedCalls ?? []), [flaggedCalls])

  const agentDeductions = useMemo<AgentDeductionRow[]>(
    () => buildAgentDeductions(dedupedCalls, totalCallsMap),
    [dedupedCalls, totalCallsMap],
  )

  const summary = useMemo(() => {
    const all = dedupedCalls
    return { total: all.length, releasing: all.filter((r) => r['Releasing Detection'] === 'Yes').length,
      lateHello: all.filter((r) => r['Late Hello Detection'] === 'Yes').length,
      noRebuttal: all.filter(isFairRebuttalMiss).length,
      wrongDispo: all.filter((r) => r['Wrong Dispo Detection'] === 'Yes').length }
  }, [dedupedCalls])

  // A deleted/cleared agent can still be the remembered pick -- fall back to the first row.
  const activeAgent = selectedAgent === ALL_AGENTS || agentDeductions.some((r) => r.agentName === selectedAgent)
    ? selectedAgent
    : agentDeductions[0]?.agentName ?? null
  const selectedAgentCalls = useMemo<FlaggedCall[]>(() => {
    if (!activeAgent) return []
    if (activeAgent === ALL_AGENTS) return dedupedCalls
    return dedupedCalls.filter((c) => (c['Agent Name'] || 'Unknown').trim() === activeAgent)
  }, [dedupedCalls, activeAgent])

  const filteredAgentCalls = useMemo<FlaggedCall[]>(
    () => {
      const q = search.trim().toLowerCase()
      return selectedAgentCalls.filter((c) =>
        callMatchesFlagType(c, flagTypeFilter) && (!q || JSON.stringify(c).toLowerCase().includes(q)))
    },
    [selectedAgentCalls, flagTypeFilter, search],
  )

  // Each card downloads its recording on mount, so only the first 20 render until asked.
  // Keyed on the current filters, so changing any of them collapses the list again.
  const listKey = `${activeAgent}|${flagTypeFilter}|${search}`
  const visibleCalls = expandedList === listKey ? filteredAgentCalls : filteredAgentCalls.slice(0, 20)

  useEffect(() => { if (!flaggedLoading) markAsSeen() }, [markAsSeen, flaggedCalls, flaggedLoading])

  const clearData = useMutation({
    mutationFn: async () => {
      await dashboardApi.clearAgentAudits()
      await dashboardApi.clearLiteAudits()
    },
    onSuccess: () => {
      setShowConfirm(false)
      qc.invalidateQueries({ queryKey: ['flagged-calls'] })
      qc.invalidateQueries({ queryKey: ['agent-audits'] })
      qc.invalidateQueries({ queryKey: ['lite-audits'] })
      qc.invalidateQueries({ queryKey: ['badge-count'] })
    },
  })

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (isError) return <p className="text-sm text-ship-red">Failed to load flagged calls.</p>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-t-primary tracking-tight">Actions</h1>
          <p className="text-vos-500 text-sm">Flagged calls requiring attention. Pick an agent to listen.</p>
        </div>
        <Button size="sm" variant="action" onClick={() => { qc.invalidateQueries({ queryKey: ['flagged-calls'] }); qc.invalidateQueries({ queryKey: ['agent-audits'] }) }}>
          <RefreshCw size={14} className="mr-2" /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-8 sm:grid-cols-4 lg:flex lg:gap-32 py-10 border-b border-b-subtle mb-4 pb-12">
        <Metric label="Total Action Items" value={summary.total} />
        <Metric label="Releasing Issues" value={summary.releasing} />
        <Metric label="Late Hello Issues" value={summary.lateHello} />
        <Metric label="Rebuttal Issues" value={summary.noRebuttal} />
        <Metric label="Wrong Dispo Issues" value={summary.wrongDispo} />
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-[10px] font-black uppercase tracking-widest text-vos-500 ml-1">Agent Deductions</h2>
        {agentDeductions.length === 0 ? (
          <p className="py-4 text-sm text-vos-500">No flagged calls found.</p>
        ) : (
          <>
            {deleteError && <p role="alert" className="text-sm text-ship-red">{deleteError}</p>}
            {deleteNotice && <p role="status" className="text-sm text-t-muted">{deleteNotice}</p>}
            <AgentDeductionsTable
              rows={agentDeductions}
              deletableAgents={deletableAgents}
              selectedAgent={activeAgent}
              onSelectAgent={setSelectedAgent}
              onDeleteAgent={(agentName) => {
                setDeleteError(null)
                setDeleteNotice(null)
                deleteAgentAudits.mutate(agentName)
              }}
              deletingAgent={deleteAgentAudits.isPending ? deleteAgentAudits.variables : null}
            />
            <div className="flex justify-end relative mt-1">
              {!showConfirm ? (
                <DestroyButton size="sm" onClick={() => setShowConfirm(true)}>Clear All Data</DestroyButton>
              ) : (
                <div className="rounded-xl border border-b-strong bg-c-base p-6 max-w-lg shadow-2xl absolute bottom-0 right-0 z-[60] mb-12">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-1 h-6 bg-[#c0392b] rounded-full" />
                    <h3 className="text-xs font-black uppercase tracking-[0.2em] text-[#e74c3c]">Confirm Deletion</h3>
                  </div>
                  <p className="mb-6 text-xs text-t-primary leading-relaxed font-medium">
                    Permanently delete all agent and lite audit data. Campaign data is not affected. This cannot be undone.
                  </p>
                  <div className="flex justify-start gap-3">
                    <DestroyButton
                      onClick={() => clearData.mutate()}
                      disabled={clearData.isPending}
                    >
                      {clearData.isPending ? 'Clearing...' : 'Permanently Delete'}
                    </DestroyButton>
                    <Button variant="action" onClick={() => setShowConfirm(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-[10px] font-black uppercase tracking-widest text-vos-500 ml-1">Agent — or click a row above</label>
        <CustomSelect 
          options={[ALL_AGENTS, ...agentDeductions.map(row => row.agentName)]}
          value={activeAgent || ''}
          onChange={(v) => setSelectedAgent(v)}
          placeholder="Select an agent..."
          className="max-w-sm"
        />
      </div>

      {activeAgent && (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-8">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 ml-1">
                <div className="w-1 h-4 bg-ship-red rounded-full" />
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-vos-500">Detailed flagged calls — {activeAgent}</h3>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative w-56">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-vos-600" size={14} />
                  <input
                    type="text"
                    placeholder="Search phone / filename..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full h-[38px] bg-c-base border border-b-subtle rounded-md pl-9 pr-3 py-1.5 text-sm text-t-primary placeholder:text-vos-600 focus:outline-none focus:border-b-strong focus:ring-2 focus:ring-c-raised/50 transition-all"
                  />
                </div>
                <CustomSelect
                  options={FLAG_TYPE_OPTIONS}
                  value={flagTypeFilter}
                  onChange={(v) => setFlagTypeFilter(v as FlagTypeFilter)}
                  className="w-44"
                />
              </div>
            </div>

            {filteredAgentCalls.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 opacity-30">
                <Search size={40} strokeWidth={1} className="mb-4" />
                <span className="text-[10px] font-black uppercase tracking-widest">No detailed calls found</span>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between px-1">
                  <span className="text-[10px] font-black uppercase tracking-widest text-vos-500">{filteredAgentCalls.length} calls</span>
                </div>
                {visibleCalls.map((c, i) => (
                  <CallCard key={`${c['File Path'] ?? c['Phone Number'] ?? ''}-${i}`} call={c} />
                ))}
                {visibleCalls.length < filteredAgentCalls.length && (
                  <Button variant="action" size="sm" className="self-center" onClick={() => setExpandedList(listKey)}>
                    Show all {filteredAgentCalls.length} calls
                  </Button>
                )}
              </>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 ml-1">
              <div className="w-1 h-4 bg-dev-blue rounded-full" />
              <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-vos-500">Audited Dialers</h3>
            </div>
            
            <div className="rounded-2xl bg-surface-card border border-b-strong shadow-2xl overflow-hidden backdrop-blur-xl">
              <table className="w-full text-sm text-left border-collapse">
                <thead className="bg-c-base border-b border-b-subtle">
                  <tr>
                    <th className="px-5 py-4 text-[10px] font-black uppercase tracking-[0.2em] text-vos-500">Dialer</th>
                    <th className="px-5 py-4 text-[10px] font-black uppercase tracking-[0.2em] text-vos-500 text-right">Audited Calls</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-b-subtle">
                  {auditedDialers.length === 0 ? (
                    <tr><td colSpan={2} className="px-5 py-10 text-center text-vos-600 text-[10px] font-black uppercase tracking-widest">No dialer data</td></tr>
                  ) : auditedDialers.map((d) => (
                    <tr key={d.dialer} className="hover:bg-c-raised/50 transition-colors group">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="w-1.5 h-1.5 rounded-full bg-dev-blue/40 group-hover:bg-dev-blue transition-colors" />
                          <span className="text-xs font-bold text-t-primary group-hover:text-dev-blue transition-colors">{d.dialer}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right tabular-nums text-sm font-black text-t-primary">
                        <CountUp value={d.count} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredAgentCalls.length > 0 && (
              <>
              <div className="rounded-2xl bg-surface-card border border-b-strong shadow-2xl backdrop-blur-xl p-4 max-h-[600px] overflow-auto custom-scrollbar font-mono text-xs leading-6 text-t-label whitespace-pre select-text">
                {filteredAgentCalls.map((c, i) => (
                  <div key={i} className="hover:text-t-primary transition-colors">
                    {formatPhone(c['Phone Number'])} - {callIssues(c).join(', ') || 'Flagged'} - {c['Dialer Name'] || 'Unknown'}
                  </div>
                ))}
              </div>
                  <Button
                    className="self-end"
                    variant="action"
                    size="sm"
                    onClick={() => {
                      const text = filteredAgentCalls.map(c => {
                        const issues = callIssues(c)
                        return `${formatPhone(c['Phone Number'])} - ${issues.join(', ') || 'Flagged'} - ${c['Dialer Name'] || 'Unknown'}`
                      }).join('\n')
                      copyToClipboard(text, 'all')
                    }}
                  >
                    {copiedId === 'all' ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
                    Copy All
                  </Button>
              </>
            )}
          </div>
        </div>
      )}

    </div>
  )
}
