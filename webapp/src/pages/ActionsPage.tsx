import { useMemo, useState, useEffect } from 'react'
import { useFlaggedCalls, useAgentAudits, useLiteAudits } from '@/hooks/useDashboard'
import { useBadgeStore } from '@/store/badgeStore'
import { Button, DestroyButton } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import type { FlaggedCall } from '@/types/api'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { dashboardApi } from '@/api/dashboard'
import { RefreshCw, Search, ChevronDown, Check, Copy, ArrowUp, ArrowDown } from 'lucide-react'
import { CustomSelect } from '@/components/ui/Select'
import { motion, AnimatePresence } from 'framer-motion'
import { CountUp, Metric } from '@/components/ui/Metric'
import { dedupeLongCallRows, isLongCallFlagged } from '@/utils/audit'

export interface AgentDeductionRow {
  agentName: string; totalCalls: number; flaggedCalls: number
  releasing: number; lateHello: number; noRebuttals: number; longCall: number
  dialerNames: string[]; deduction: boolean
}


export function AgentDeductionsTable({ rows }: { rows: AgentDeductionRow[] }) {
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
    { key: 'dialerNames',  label: 'Dialer(s)',      cls: '' },
    { key: 'deduction',    label: 'Deduction',      cls: '' },
  ]

  const sortedRows = useMemo(() => {
    if (!sortCol) return rows
    return [...rows].sort((a, b) => {
      let va = a[sortCol]
      let vb = b[sortCol]
      
      // Handle array/boolean types for sorting
      if (Array.isArray(va)) va = va.join(', ')
      if (Array.isArray(vb)) vb = vb.join(', ')
      
      const sa = String(va ?? '').toLowerCase()
      const sb = String(vb ?? '').toLowerCase()
      
      // Try numeric sort for numeric fields
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
                    key={h.key} 
                    onClick={() => toggleSort(h.key)}
                    className={`${h.cls} border-r border-b-subtle px-2.5 py-2.5 text-left text-[10px] font-black uppercase tracking-[0.12em] text-vos-500 leading-tight last:border-r-0 cursor-pointer hover:bg-c-raised/30 transition-colors select-none`}
                  >
                    <div className={`flex items-center gap-2 ${h.cls.includes('text-right') ? 'justify-end' : 'justify-start'}`}>
                      {h.label}
                      <span className={`transition-opacity duration-200 ${isSorted ? 'opacity-100' : 'opacity-0'}`}>
                        {sortDir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
                      </span>
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
              <tr key={row.agentName} className="hover:bg-c-raised/50 transition-colors group/row">
                <td className="border-r border-b-subtle px-2.5 py-2.5 text-t-primary font-medium group/cell relative">
                  <div className="flex items-center justify-start gap-2">
                    <span className="block break-words">{row.agentName}</span>
                    <button 
                      onClick={() => copyToClipboard(row.agentName, copyId)}
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
                <td className="border-r border-b-subtle px-2.5 py-2.5 text-t-primary font-medium">
                  <span className="block break-words">{row.dialerNames.length ? row.dialerNames.join(' & ') : '—'}</span>
                </td>
                <td className={`px-2.5 py-2.5 whitespace-nowrap font-black uppercase tracking-widest text-[10px] ${deductionBg} ${deductionText}`}>{row.deduction ? 'Yes' : 'No'}</td>
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
  const [showConfirm, setShowConfirm] = useState(false)
  const markAsSeen = useBadgeStore(s => s.markAsSeen)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

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
  const callIssues = (c: FlaggedCall): string[] => {
    const issues: string[] = []
    if (c['Releasing Detection'] === 'Yes') issues.push('Releasing')
    if (c['Late Hello Detection'] === 'Yes') issues.push('Late Hello')
    if (c['Rebuttal Detection'] === 'No') issues.push('No Rebuttal')
    const lc = c['Long VM/Dead Detection']
    if (isLongCallFlagged(lc)) {
      const s = String(lc).toLowerCase()
      if (s.startsWith('voicemail')) issues.push('voicemail above 15 sec')
      else if (s.startsWith('dead call')) issues.push('Dead call above 15 sec')
      else issues.push('Long VM/Dead')
    }
    return issues
  }

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

  const agentDeductions = useMemo<AgentDeductionRow[]>(() => {
    const calls: FlaggedCall[] = dedupedCalls
    const agentMap = new Map<string, { flagged: FlaggedCall[]; releasing: number; lateHello: number; noRebuttals: number; longCall: number; dialerNames: Set<string> }>()
    for (const call of calls) {
      const name = (call['Agent Name'] ?? 'Unknown').trim()
      if (!agentMap.has(name)) agentMap.set(name, { flagged: [], releasing: 0, lateHello: 0, noRebuttals: 0, longCall: 0, dialerNames: new Set() })
      const entry = agentMap.get(name)!
      entry.flagged.push(call)
      if (call['Releasing Detection'] === 'Yes') entry.releasing++
      if (call['Late Hello Detection'] === 'Yes') entry.lateHello++
      if (call['Rebuttal Detection'] === 'No') entry.noRebuttals++
      if (isLongCallFlagged(call['Long VM/Dead Detection'])) entry.longCall++
      const dialer = call['Dialer Name'] as string | undefined
      if (dialer) entry.dialerNames.add(dialer)
    }
    return [...agentMap.entries()].map(([agentName, data]) => ({
      agentName, totalCalls: totalCallsMap.get(agentName) ?? data.flagged.length,
      flaggedCalls: data.flagged.length, releasing: data.releasing, lateHello: data.lateHello,
      noRebuttals: data.noRebuttals, longCall: data.longCall,
      dialerNames: [...data.dialerNames].sort(), deduction: data.flagged.length >= 5,
    })).sort((a, b) => b.flaggedCalls - a.flaggedCalls)
  }, [dedupedCalls, totalCallsMap])

  const summary = useMemo(() => {
    const all = dedupedCalls
    return { total: all.length, releasing: all.filter((r) => r['Releasing Detection'] === 'Yes').length,
      lateHello: all.filter((r) => r['Late Hello Detection'] === 'Yes').length,
      noRebuttal: all.filter((r) => r['Rebuttal Detection'] === 'No').length }
  }, [dedupedCalls])

  const selectedAgentCalls = useMemo<FlaggedCall[]>(() => {
    if (!selectedAgent) return []
    return dedupedCalls.filter((c) => (c['Agent Name'] || 'Unknown').trim() === selectedAgent)
  }, [dedupedCalls, selectedAgent])

  useEffect(() => { if (!flaggedLoading) markAsSeen() }, [markAsSeen, flaggedCalls, flaggedLoading])
  useEffect(() => { if (!selectedAgent && agentDeductions.length > 0) setSelectedAgent(agentDeductions[0].agentName) }, [agentDeductions, selectedAgent])

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
          <p className="text-vos-500 text-sm">Flagged calls requiring attention.</p>
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
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-[10px] font-black uppercase tracking-widest text-vos-500 ml-1">Agent Deductions</h2>
        {agentDeductions.length === 0 ? (
          <p className="py-4 text-sm text-vos-500">No flagged calls found.</p>
        ) : (
          <>
            <AgentDeductionsTable rows={agentDeductions} />
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
        <label className="text-[10px] font-black uppercase tracking-widest text-vos-500 ml-1">Select agent to view detailed flagged calls</label>
        <CustomSelect 
          options={agentDeductions.map(row => row.agentName)}
          value={selectedAgent || ''}
          onChange={(v) => setSelectedAgent(v)}
          placeholder="Select an agent..."
          className="max-w-sm"
        />
      </div>

      {selectedAgent && (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-8">
          {/* Detailed Flagged Calls */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 ml-1">
              <div className="w-1 h-4 bg-ship-red rounded-full" />
              <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-vos-500">Detailed flagged calls — {selectedAgent}</h3>
            </div>
            
            <div className="rounded-2xl bg-surface-card border border-b-strong shadow-2xl overflow-hidden flex flex-col backdrop-blur-xl">
              {/* Copy-all header */}
              {selectedAgentCalls.length > 0 && (
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-b-subtle bg-c-raised/50">
                  <span className="text-[10px] font-black uppercase tracking-widest text-vos-500">{selectedAgentCalls.length} calls</span>
                  <Button
                    variant="action"
                    size="sm"
                    onClick={() => {
                      const text = selectedAgentCalls.map(c => {
                        const issues = callIssues(c)
                        return `${formatPhone(c['Phone Number'])} - ${issues.join(', ') || 'Flagged'} - ${c['Dialer Name'] || 'Unknown'}`
                      }).join('\n')
                      copyToClipboard(text, 'all')
                    }}
                  >
                    <AnimatePresence mode="wait">
                      {copiedId === 'all'
                        ? <Check size={12} className="text-green-500" />
                        : <Copy size={12} />}
                    </AnimatePresence>
                    Copy All
                  </Button>
                </div>
              )}

              <div className="overflow-y-auto custom-scrollbar flex-1 min-h-[400px] max-h-[600px]">
                {selectedAgentCalls.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-20 opacity-30">
                    <Search size={40} strokeWidth={1} className="mb-4" />
                    <span className="text-[10px] font-black uppercase tracking-widest">No detailed calls found</span>
                  </div>
                ) : (
                  <div className="p-4 font-mono text-sm leading-7 text-t-label whitespace-pre select-text">
                    {selectedAgentCalls.map((c, i) => {
                      const issues = callIssues(c)
                      return (
                        <div key={i} className="hover:text-t-primary transition-colors">
                          {formatPhone(c['Phone Number'])} - {issues.join(', ') || 'Flagged'} - {c['Dialer Name'] || 'Unknown'}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Audited Dialers */}
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
          </div>
        </div>
      )}

    </div>
  )
}
