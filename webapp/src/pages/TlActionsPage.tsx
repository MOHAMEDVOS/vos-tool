import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, AlertTriangle, Check, CheckCircle2, ClipboardCheck, Copy, ExternalLink, RefreshCw, Search } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { DateRangePicker } from '@/components/ui/DateRangePicker'
import { Spinner } from '@/components/ui/Spinner'
import { useAuthStore } from '@/store/authStore'
import { tlActionsApi, type TlActionsReconciliation, type TlActionResult } from '@/api/tlActions'

interface LeaderCount {
  name: string
  count: number
}

const FIELD_NAMES = [
  'Team Leader',
  'Agent Name',
  'Type of Issue',
  'Details about incident',
  'Reported by TL',
  'Action Given',
] as const

type ActionFields = Partial<Record<(typeof FIELD_NAMES)[number], string>>

function localDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseActionDetails(details: string): ActionFields {
  const pattern = /\b(Team Leader|Agent Name|Type of Issue|Details about incident|Reported by TL|Action Given)\s*:\s*/gi
  const matches = [...details.matchAll(pattern)]
  const fields: ActionFields = {}
  matches.forEach((match, index) => {
    const label = match[1] as (typeof FIELD_NAMES)[number]
    const start = (match.index ?? 0) + match[0].length
    const end = matches[index + 1]?.index ?? details.length
    fields[label] = details.slice(start, end)
      .replace(/<br\s*\/?\s*>/gi, '\n')
      .replace(/<[^>]*>/g, ' ')
      .replace(/&nbsp;/gi, ' ')
      .trim()
  })
  return fields
}

function displayDate(value?: string): string {
  if (!value) return 'Date unavailable'
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(parsed)
}

function displayDateRange(start: string, end: string): string {
  const startDate = new Date(`${start}T00:00:00`)
  const endDate = new Date(`${end}T00:00:00`)
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return `${start} to ${end}`
  const format = (date: Date, includeYear: boolean) => new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', ...(includeYear ? { year: 'numeric' as const } : {}),
  }).format(date)
  if (start === end) return format(startDate, true)
  if (startDate.getFullYear() === endDate.getFullYear()) {
    return `${format(startDate, false)} to ${format(endDate, true)}`
  }
  return `${format(startDate, true)} to ${format(endDate, true)}`
}

function formatOriginalAction(fields: ActionFields): string {
  const incidents = fields['Details about incident'] ?? ''
  const incidentLines = incidents
    .replace(/\s*(?=\(\d{3}\)\s*\d{3}[-.\s]\d{4})/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  const lines = [
    fields['Team Leader'] && `Team Leader: ${fields['Team Leader']}`,
    fields['Agent Name'] && `Agent Name: ${fields['Agent Name']}`,
    fields['Type of Issue'] && `Type of Issue: ${fields['Type of Issue']}`,
    'Details about incident:',
    '',
    ...incidentLines,
    '',
    fields['Reported by TL'] && `Reported by TL: ${fields['Reported by TL']}`,
    fields['Action Given'] && `Action Given: ${fields['Action Given']}`,
  ]
  return lines.filter((line): line is string => line !== undefined).join('\n')
}

function actionStatusKey(row: TlActionResult): string {
  const value = `${row.action_date}|${row.sheet_row}|${row.details}`
  let hash = 2166136261
  for (let index = 0; index < value.length; index++) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return `${row.action_date}-${row.sheet_row}-${(hash >>> 0).toString(36)}`
}

function MissingActionCard({
  row,
  preparing,
  prepareError,
  prepareWarning,
  podioConfirmed,
  submissionStarted,
  onOpenForms,
}: {
  row: TlActionResult
  preparing: boolean
  prepareError?: string
  prepareWarning?: string
  podioConfirmed: boolean
  submissionStarted: boolean
  onOpenForms: () => void
}) {
  const fields = parseActionDetails(row.details)
  const actionTemplate = formatOriginalAction(fields)

  return (
    <article className="overflow-hidden rounded-xl border border-b-strong bg-surface-card shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-b-divider bg-surface-soft/40 px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="rounded-md bg-surface-page px-2.5 py-1 text-sm font-semibold text-t-primary">{displayDate(row.action_date)}</span>
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-bold ${podioConfirmed ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600' : submissionStarted ? 'border-amber-500/30 bg-amber-500/10 text-amber-600' : 'border-red-500/30 bg-red-500/10 text-red-500'}`}>
            {podioConfirmed ? <><CheckCircle2 size={13} /> Confirmed in Podio</> : submissionStarted ? <><AlertTriangle size={13} /> Waiting for Podio</> : <><AlertTriangle size={13} /> Not confirmed in Podio</>}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={onOpenForms} disabled={preparing} className="min-h-9 px-3 text-sm">
            {preparing ? <><Spinner size="sm" /> Preparing…</> : <><ExternalLink size={14} /> {podioConfirmed ? 'Open Google Form' : submissionStarted ? 'Reopen forms' : 'Send action'}</>}
          </Button>
        </div>
      </div>

      <div className="px-5 py-4">
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-t-primary">{actionTemplate}</pre>
        <p className="mt-3 text-xs text-t-secondary">{podioConfirmed ? 'VOS found this action in Podio. Submit the Google Form separately if it is not submitted yet.' : submissionStarted ? 'Submit the Podio form to finish. VOS is checking Podio automatically; submit the Google Form separately.' : 'Open both forms and submit them. VOS will confirm the Podio submission automatically.'}</p>
        {prepareWarning && <p role="alert" className="mt-3 flex items-start gap-2 text-sm font-medium text-amber-600"><AlertTriangle size={16} className="mt-0.5 shrink-0" />{prepareWarning}</p>}
        {prepareError && <p role="alert" className="mt-3 flex items-start gap-2 text-sm font-medium text-red-500"><AlertCircle size={16} className="mt-0.5 shrink-0" />{prepareError}</p>}
      </div>
    </article>
  )
}

export function TlActionsPage() {
  const role = useAuthStore((state) => state.role)
  const isOwner = role === 'Owner'
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  const [startDate, setStartDate] = useState(localDate(yesterday))
  const [endDate, setEndDate] = useState(localDate(yesterday))
  const [result, setResult] = useState<TlActionsReconciliation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [copyFeedback, setCopyFeedback] = useState('')
  const [preparingKey, setPreparingKey] = useState<string | null>(null)
  const [prepareErrors, setPrepareErrors] = useState<Record<string, string>>({})
  const [prepareWarnings, setPrepareWarnings] = useState<Record<string, string>>({})
  const [podioConfirmedKeys, setPodioConfirmedKeys] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('vos-tl-actions-podio-confirmed-v1') || '[]')
      return Array.isArray(saved) ? saved.filter((key): key is string => typeof key === 'string') : []
    } catch {
      return []
    }
  })
  const [startedKeys, setStartedKeys] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('vos-tl-actions-started-v1') || '[]')
      return Array.isArray(saved) ? saved.filter((key): key is string => typeof key === 'string') : []
    } catch {
      return []
    }
  })
  const [podioStatus, setPodioStatus] = useState<{ configured: boolean; connected: boolean } | null>(null)
  const [podioStatusError, setPodioStatusError] = useState('')
  const [podioSaveError, setPodioSaveError] = useState('')
  const [podioConnectBusy, setPodioConnectBusy] = useState(false)
  const podioCheckInFlight = useRef(false)
  const startedKeysRef = useRef(startedKeys)
  const podioConfirmedKeysRef = useRef(podioConfirmedKeys)
  const [podioCheckNotice, setPodioCheckNotice] = useState('')
  useEffect(() => { startedKeysRef.current = startedKeys }, [startedKeys])
  useEffect(() => { podioConfirmedKeysRef.current = podioConfirmedKeys }, [podioConfirmedKeys])
  const leaderCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const action of result?.results ?? []) {
      const leader = action.team_leader?.trim() || 'Unknown team leader'
      counts.set(leader, (counts.get(leader) ?? 0) + 1)
    }
    return [...counts.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
  }, [result])
  const maxLeaderCount = leaderCounts[0]?.count ?? 1

  const refreshPodioStatus = async () => {
    try {
      setPodioStatus(await tlActionsApi.podioStatus())
      setPodioStatusError('')
    } catch (err) {
      setPodioStatusError(err instanceof Error ? err.message : 'Could not read Podio connection status.')
    }
  }

  useEffect(() => {
    if (role === 'Owner' || role === 'Admin') void refreshPodioStatus()
  }, [role])

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.data?.type !== 'vos-podio-connected') return
      void refreshPodioStatus()
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  useEffect(() => {
    if (!podioStatus?.connected || !result) return
    let cancelled = false
    const checkStartedActions = async () => {
      if (podioCheckInFlight.current) return
      podioCheckInFlight.current = true
      try {
        for (const row of result.results) {
          const key = actionStatusKey(row)
          if (cancelled || !startedKeysRef.current.includes(key) || podioConfirmedKeysRef.current.includes(key)) continue
          const match = await tlActionsApi.checkPodio(row)
          if (cancelled || !match.confirmed) continue
          setPodioConfirmedKeys((current) => {
            const next = [...new Set([...current, key])]
            podioConfirmedKeysRef.current = next
            try {
              localStorage.setItem('vos-tl-actions-podio-confirmed-v1', JSON.stringify(next))
              setPodioSaveError('')
            } catch {
              setPodioSaveError('Podio confirmed the action, but this browser could not save the green confirmation.')
            }
            return next
          })
          setStartedKeys((current) => {
            const next = current.filter((item) => item !== key)
            startedKeysRef.current = next
            try { localStorage.setItem('vos-tl-actions-started-v1', JSON.stringify(next)) } catch { /* confirmation is already saved above */ }
            return next
          })
        }
      } catch (err) {
        if (!cancelled) setPodioCheckNotice(err instanceof Error ? `Podio check will retry: ${err.message}` : 'Podio check will retry.')
      } finally {
        podioCheckInFlight.current = false
      }
    }
    void checkStartedActions()
    const timer = window.setInterval(() => { void checkStartedActions() }, 15000)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [podioStatus?.connected, result])

  const copyBriefReport = async () => {
    if (!result) return
    const dateRange = displayDateRange(result.start_date, result.end_date)
    const leaderLines = leaderCounts.length
      ? leaderCounts.map(({ name, count }) => `- ${name} — ${count}`).join('\n')
      : 'No missing actions.'
    const summary = [
      'Missing Payroll Actions',
      `Date range: ${dateRange}`,
      '',
      leaderLines,
      '',
      `Total: ${result.missing_count} missing ${result.missing_count === 1 ? 'action' : 'actions'} across ${leaderCounts.length} team ${leaderCounts.length === 1 ? 'leader' : 'leaders'}.`,
    ].join('\n')
    try {
      await navigator.clipboard.writeText(summary)
      setCopyFeedback('Copied brief report.')
    } catch {
      setCopyFeedback('Could not copy. Check clipboard access.')
    }
    window.setTimeout(() => setCopyFeedback(''), 2500)
  }

  const rowKey = (row: TlActionResult) => `${row.sheet_row ?? 'row'}-${row.action_date ?? 'date'}`

  const saveStartedStatus = (key: string) => {
    const next = [...new Set([...startedKeys, key])]
    try {
      localStorage.setItem('vos-tl-actions-started-v1', JSON.stringify(next))
      startedKeysRef.current = next
      setStartedKeys(next)
      setPodioSaveError('')
    } catch {
      setPodioSaveError('Could not save submission progress in this browser.')
    }
  }

  const connectPodio = async () => {
    const popup = window.open('about:blank', '_blank')
    if (!popup) {
      setPodioStatusError('Allow pop-ups for VOS to connect Podio.')
      return
    }
    setPodioConnectBusy(true)
    setPodioStatusError('')
    try {
      const { auth_url } = await tlActionsApi.podioConnect()
      popup.location.href = auth_url
    } catch (err) {
      popup.close()
      setPodioStatusError(err instanceof Error ? err.message : 'Could not start Podio connection.')
    } finally {
      setPodioConnectBusy(false)
    }
  }

  const rows = useMemo(() => {
    if (!result) return []
    const query = search.trim().toLocaleLowerCase()
    return result.results.filter((row) => !query || row.details.toLocaleLowerCase().includes(query))
  }, [result, search])

  const reconcile = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    setPrepareErrors({})
    setPrepareWarnings({})
    try {
      setResult(await tlActionsApi.reconcile(startDate, endDate))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reconciliation failed')
    } finally {
      setLoading(false)
    }
  }

  const openActionForms = async (row: TlActionResult) => {
    const key = rowKey(row)
    const isPodioConfirmed = podioConfirmedKeys.includes(actionStatusKey(row))
    const podioTab = isPodioConfirmed ? null : window.open('about:blank', '_blank')
    const googleTab = window.open('about:blank', '_blank')
    if ((!isPodioConfirmed && !podioTab) || !googleTab) {
      podioTab?.close()
      googleTab?.close()
      setPrepareErrors((current) => ({ ...current, [key]: 'Allow pop-ups for VOS, then try again.' }))
      return
    }

    setPreparingKey(key)
    setPrepareErrors((current) => ({ ...current, [key]: '' }))
    setPrepareWarnings((current) => ({ ...current, [key]: '' }))
    try {
      const forms = await tlActionsApi.prepare(row)
      if (podioTab) podioTab.location.href = forms.podio_url
      googleTab.location.href = forms.google_form_url
      if (!isPodioConfirmed) saveStartedStatus(actionStatusKey(row))
      if (!isPodioConfirmed && forms.agent_warning) {
        setPrepareWarnings((current) => ({ ...current, [key]: forms.agent_warning ?? '' }))
        window.alert(`Both forms are open. ${forms.agent_warning}`)
      }
    } catch (err) {
      podioTab?.close()
      googleTab.close()
      setPrepareErrors((current) => ({ ...current, [key]: err instanceof Error ? err.message : 'Could not prepare the forms.' }))
    } finally {
      setPreparingKey(null)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-6 pb-8">
      <header className="flex items-start gap-3">
        <div className="rounded-lg bg-vos-500/10 p-2.5 text-t-primary"><ClipboardCheck size={21} /></div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-t-primary">TL Actions</h1>
          <p className="mt-1 text-sm leading-6 text-t-secondary">Review team-leader actions that have not been submitted to Payroll.</p>
        </div>
      </header>

      <section aria-label="Reconciliation date range" className="flex flex-wrap items-end gap-4 rounded-xl border border-b-medium bg-surface-card p-5 shadow-card">
        <div className="min-w-0 flex-1">
          <label className="mb-2 block px-1 text-[10px] font-black uppercase tracking-[0.15em] text-t-label">Date range</label>
          <DateRangePicker startDate={startDate} endDate={endDate} onChange={(start, end) => { setStartDate(start); setEndDate(end) }} />
        </div>
        <Button onClick={reconcile} disabled={loading || !startDate || !endDate} className="min-h-10 px-5 text-sm">
          {loading ? <><Spinner size="sm" /> Checking…</> : <><RefreshCw size={15} /> Find missing actions</>}
        </Button>
      </section>

      {(isOwner || role === 'Admin') && !podioStatus?.connected && <section aria-label="Podio confirmation setup" className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-b-medium bg-surface-card px-5 py-4 shadow-card">
        <div>
          <h2 className="text-sm font-bold text-t-primary">Podio submission confirmation</h2>
          <p className="mt-1 text-sm text-t-secondary">
            {podioStatus?.connected ? 'Connected. VOS checks submitted actions automatically.' : podioStatus?.configured ? 'Connect Podio once to enable automatic green confirmations.' : 'Podio API credentials need to be configured on the backend.'}
          </p>
          {podioCheckNotice && <p role="status" className="mt-1 text-xs text-t-secondary">{podioCheckNotice}</p>}
          {podioStatusError && <p role="alert" className="mt-1 text-xs text-red-500">{podioStatusError}</p>}
          {!podioStatus?.configured && isOwner && <p className="mt-1 text-xs text-t-secondary">Set PODIO_CLIENT_ID and PODIO_CLIENT_SECRET in Railway’s backend variables, then redeploy.</p>}
        </div>
        {isOwner && podioStatus?.configured && !podioStatus.connected && <Button type="button" onClick={connectPodio} disabled={podioConnectBusy} className="min-h-9 px-3 text-sm">
          {podioConnectBusy ? <><Spinner size="sm" /> Connecting…</> : <><ExternalLink size={14} /> Connect Podio</>}
        </Button>}
      </section>}

      {error && <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm font-medium text-red-500"><AlertCircle size={18} className="mt-0.5 shrink-0" />{error}</div>}
      {podioSaveError && <div role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700">{podioSaveError}</div>}

      {result && <>
        <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-b-medium bg-surface-card px-5 py-4 shadow-card">
          <div>
            <h2 className="text-lg font-bold text-t-primary">{result.missing_count} missing {result.missing_count === 1 ? 'action' : 'actions'}</h2>
            <p className="mt-1 text-sm text-t-secondary">From {displayDate(result.start_date)} to {displayDate(result.end_date)} · {result.sheet_count} sheet actions checked</p>
          </div>
          <label className="relative w-full sm:w-72">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-t-secondary" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search agent, team leader, issue…"
              className="min-h-10 w-full rounded-md border border-b-strong bg-surface-input py-2 pl-9 pr-3 text-sm text-t-primary placeholder:text-t-placeholder outline-none focus:border-b-focus focus:ring-2 focus:ring-b-focus/20" />
          </label>
        </section>

        {isOwner && <section aria-labelledby="tl-action-tracking-title" className="rounded-xl border border-b-medium bg-surface-card p-5 shadow-card">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 id="tl-action-tracking-title" className="text-lg font-bold text-t-primary">Missing actions by team leader</h2>
              <p className="mt-1 text-sm text-t-secondary">Exact date range: {displayDate(result.start_date)} to {displayDate(result.end_date)} · {result.missing_count} missing {result.missing_count === 1 ? 'action' : 'actions'}</p>
            </div>
            <Button type="button" variant="secondary" onClick={copyBriefReport} className="min-h-9 px-3 text-sm">
              {copyFeedback === 'Copied brief report.' ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy brief report</>}
            </Button>
          </div>
          {copyFeedback && <p role="status" className="-mt-3 mb-3 text-xs text-t-secondary">{copyFeedback}</p>}
          {leaderCounts.length === 0 ? (
            <p className="rounded-lg bg-surface-soft px-4 py-6 text-center text-sm text-t-secondary">No missing actions in this date range.</p>
          ) : (
            <div className="max-h-[420px] space-y-3 overflow-y-auto pr-2">
              {leaderCounts.map(({ name, count }, index) => (
                <div key={name} className="grid grid-cols-[minmax(0,1fr)_minmax(80px,2fr)_3rem] items-center gap-3 text-sm">
                  <span className="truncate text-t-primary" title={name}>{index + 1}. {name}</span>
                  <div role="meter" aria-label={`${name}: ${count} missing actions`} aria-valuemin={0} aria-valuemax={maxLeaderCount} aria-valuenow={count}
                    className="h-2 overflow-hidden rounded-full bg-surface-soft">
                    <div className="h-full rounded-full bg-vos-500" style={{ width: `${(count / maxLeaderCount) * 100}%` }} />
                  </div>
                  <span className="text-right font-bold tabular-nums text-t-primary">{count}</span>
                </div>
              ))}
            </div>
          )}
        </section>}

        {rows.length > 0
          ? <section aria-label="Missing actions" className="grid gap-4">
              {rows.map((row, index) => {
                const key = rowKey(row)
                const statusKey = actionStatusKey(row)
                return <MissingActionCard key={`${key}-${index}`} row={row} preparing={preparingKey === key} prepareError={prepareErrors[key]} prepareWarning={prepareWarnings[key]} podioConfirmed={podioConfirmedKeys.includes(statusKey)} submissionStarted={startedKeys.includes(statusKey)} onOpenForms={() => openActionForms(row)} />
              })}
            </section>
          : <div className="rounded-xl border border-b-medium bg-surface-card px-5 py-12 text-center shadow-card">
              <ClipboardCheck size={28} className="mx-auto text-emerald-600" />
              <h3 className="mt-3 text-base font-bold text-t-primary">{result.missing_count === 0 ? 'You’re all caught up' : 'No matching actions'}</h3>
              <p className="mt-1 text-sm text-t-secondary">{result.missing_count === 0 ? 'Every sheet action in this date range was found in Payroll.' : 'Try a different search term.'}</p>
            </div>}
      </>}
    </div>
  )
}
