import { useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { scoringApi, type GatherResult, type ScoreRow, type AuditProgress, type AuditScores } from '@/api/scoring'
import { Copy, Check, AlertTriangle } from 'lucide-react'

const labelClass = 'text-[10px] font-black uppercase tracking-[0.1em] mb-2 block'

// The 5 scored points and which value counts as an issue (drives the red/green badge).
const SCORE_DEFS: { key: keyof AuditScores; label: string; issue: string; title: string }[] = [
  { key: 'late_hello', label: 'Hello', issue: 'Yes', title: 'Homeowner had to say "hello" first (Late Hello)' },
  { key: 'releasing', label: 'Releasing', issue: 'Yes', title: "Agent's sound is low (Releasing)" },
  { key: 'rebuttal_ok', label: 'Rebuttal', issue: 'No', title: 'Used rebuttals correctly' },
  { key: 'agent_intro', label: 'Intro', issue: 'No', title: 'Said his name (Agent Intro)' },
  { key: 'reason', label: 'Reason', issue: 'No', title: 'Stated the reason for calling' },
]

function ScoreBadges({ scores }: { scores: AuditScores }) {
  return (
    <div className="flex flex-wrap gap-1">
      {SCORE_DEFS.map(({ key, label, issue, title }) => {
        const isIssue = scores[key] === issue
        return (
          <span
            key={key}
            title={`${title}: ${scores[key]}`}
            className="rounded px-1.5 py-0.5 text-[10px] font-bold"
            style={isIssue
              ? { background: '#c0392b', color: '#fff' }
              : { background: 'rgba(39,174,96,0.15)', color: 'var(--t-muted)' }}
          >
            {label}
          </span>
        )
      })}
    </div>
  )
}

function today(): string {
  // Local date (not UTC) — toISOString() rolls to the next day in the evening for UTC+ zones.
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export function ScoringPage() {
  // ── gather phase ──
  const [date, setDate] = useState(today())
  const [gathering, setGathering] = useState(false)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [gatherResult, setGatherResult] = useState<GatherResult | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // ── generate phase ──
  const [names, setNames] = useState('')
  const [generating, setGenerating] = useState(false)
  const [rows, setRows] = useState<ScoreRow[] | null>(null)
  const [skipped, setSkipped] = useState<string[]>([])

  // ── audit-&-score phase (heavy audit per agent) ──
  const [auditing, setAuditing] = useState(false)
  const [auditProgress, setAuditProgress] = useState<AuditProgress | null>(null)
  const auditAbortRef = useRef<AbortController | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [sent, setSent] = useState(false)

  const runGather = async () => {
    setError(null); setProgress(null); setGatherResult(null)
    setRows(null); setSkipped([]); setSent(false)
    setGathering(true)
    abortRef.current = new AbortController()
    try {
      const result = await scoringApi.gatherStream(
        date,
        (event, data) => {
          if (event === 'progress') {
            try { setProgress(JSON.parse(data)) } catch { /* ignore */ }
          }
        },
        abortRef.current.signal,
      )
      setGatherResult(result)
    } catch (e: any) {
      if (e?.name !== 'AbortError') setError(e?.message || 'Gather failed')
    } finally {
      setGathering(false)
    }
  }

  const runGenerate = async () => {
    if (!gatherResult) return
    const agentNames = names.split('\n').map((s) => s.trim()).filter(Boolean)
    if (agentNames.length === 0) { setError('Paste at least one agent name'); return }
    setError(null); setGenerating(true); setSent(false)
    try {
      const res = await scoringApi.generate(gatherResult.run_id, agentNames)
      setRows(res.rows)
      setSkipped(res.skipped)
    } catch (e: any) {
      setError(e?.message || 'Generate failed')
    } finally {
      setGenerating(false)
    }
  }

  const runAudit = async () => {
    if (!gatherResult) return
    const agentNames = names.split('\n').map((s) => s.trim()).filter(Boolean)
    if (agentNames.length === 0) { setError('Paste at least one agent name'); return }
    setError(null); setRows(null); setSkipped([]); setSent(false)
    setAuditing(true); setAuditProgress(null)
    auditAbortRef.current = new AbortController()
    try {
      const res = await scoringApi.auditStream(
        gatherResult.run_id,
        agentNames,
        (p) => setAuditProgress(p),
        auditAbortRef.current.signal,
      )
      setRows(res.rows)
      setSkipped(res.skipped)
    } catch (e: any) {
      if (e?.name !== 'AbortError') setError(e?.message || 'Audit failed')
    } finally {
      setAuditing(false)
    }
  }

  const cancelAudit = () => auditAbortRef.current?.abort()

  const buildTsv = (data: ScoreRow[]): string => {
    const lines = ['Agent name\tPhone\tFlag\tNote\tRed Flag']
    for (const r of data) {
      const phones = r.phones.length ? r.phones : [{ phone: '', flags: [] as string[] }]
      phones.forEach((p, i) => {
        lines.push([
          r.agent,
          p.phone,
          p.flags.join(', '),
          i === 0 ? r.note : '',
          i === 0 ? (r.red_flag ? 'Yes' : 'No') : '',
        ].join('\t'))
      })
    }
    return lines.join('\n')
  }

  const copyTable = () => {
    if (!rows) return
    navigator.clipboard.writeText(buildTsv(rows))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const exportSheet = async () => {
    if (!rows) return
    setExporting(true); setError(null)
    try {
      await scoringApi.exportSheet(rows, `Scoring ${date}`)   // send quietly — no redirect, no message
      setSent(true)
      setTimeout(() => setSent(false), 2500)
    } catch (e: any) {
      setError(e?.message || 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const hasScores = !!rows?.some((r) => r.scores)

  return (
    <div className="mx-auto max-w-[1600px] px-6 py-6">
      <h1 className="text-2xl font-black tracking-tight mb-4" style={{ color: 'var(--t-primary)' }}>Scoring</h1>

      {/* ── Sticky toolbar: Gather + Names in one slim bar ── */}
      <div className="sticky top-0 z-20 -mx-6 mb-4 border-b border-b-subtle px-6 py-3 bg-c-base">
        <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
          {/* Gather group */}
          <div className="flex items-end gap-2">
            <div>
              <label className={labelClass} style={{ color: 'var(--t-label)' }}>Date</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={gathering}
                className="rounded-md border border-b-subtle bg-transparent px-3 py-2 text-sm"
                style={{ color: 'var(--t-primary)' }}
              />
            </div>
            <Button variant="action" onClick={runGather} disabled={gathering}>
              {gathering ? 'Gathering…' : 'Gather Data'}
            </Button>
            {gathering && progress && (
              <span className="pb-2 text-xs" style={{ color: 'var(--t-muted)' }}>{progress.done}/{progress.total}</span>
            )}
            {gathering && <span className="pb-1"><Spinner /></span>}
          </div>

          <div className="hidden w-px self-stretch bg-b-subtle md:block" />

          {/* Names group */}
          <div className="flex min-w-[260px] flex-1 items-end gap-2">
            <div className="flex-1">
              <label className={labelClass} style={{ color: 'var(--t-label)' }}>Agent names — one per line</label>
              <textarea
                value={names}
                onChange={(e) => setNames(e.target.value)}
                rows={2}
                placeholder={'Ahmed Mohamed\nSara Ali …'}
                className="w-full rounded-md border border-b-subtle bg-transparent px-3 py-2 text-sm font-mono"
                style={{ color: 'var(--t-primary)' }}
              />
            </div>
            <Button variant="action" onClick={runGenerate} disabled={!gatherResult || generating || auditing}>
              {generating ? 'Generating…' : 'Generate'}
            </Button>
            {auditing ? (
              <Button variant="secondary" onClick={cancelAudit}>Cancel</Button>
            ) : (
              <Button variant="action" onClick={runAudit} disabled={!gatherResult || generating}>
                Audit &amp; Score
              </Button>
            )}
          </div>
        </div>

        {/* audit progress */}
        {auditing && (
          <div className="mt-2 flex items-center gap-2 text-xs" style={{ color: 'var(--t-primary)' }}>
            <Spinner />
            {auditProgress ? (
              <span>
                Agent <strong>{auditProgress.agent_idx}/{auditProgress.total}</strong> — {auditProgress.agent}
                {' · '}{auditProgress.phase}
                {auditProgress.phase === 'download' && auditProgress.dl_total
                  ? ` ${auditProgress.downloaded ?? 0}/${auditProgress.dl_total}` : ''}
              </span>
            ) : (
              <span>Starting audit… (downloads + transcription — this can take a while for many agents)</span>
            )}
          </div>
        )}

        {/* status / hint line */}
        {gatherResult ? (
          <div className="mt-2 text-xs" style={{ color: 'var(--t-primary)' }}>
            ✓ <strong>{gatherResult.agent_count}</strong> agents ({gatherResult.flagged_agent_count} flagged, {gatherResult.total_rows} calls)
            {gatherResult.dialers_failed.length > 0 && (
              <span style={{ color: 'var(--semantic-error)' }}> · Failed: {gatherResult.dialers_failed.join(', ')}</span>
            )}
          </div>
        ) : (
          !gathering && <div className="mt-2 text-xs" style={{ color: 'var(--t-muted)' }}>Gather data first, then paste agent names and Generate.</div>
        )}
      </div>

      {error && (
        <div className="mb-6 rounded-md p-3 text-sm" style={{ background: 'rgba(192,57,43,0.1)', color: 'var(--semantic-error)' }}>
          {error}
        </div>
      )}

      {/* ── Results ── */}
      {rows && (
        <section className="rounded-lg border border-b-subtle bg-c-base">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-b-subtle p-4">
            <h2 className="text-lg font-black tracking-tight" style={{ color: 'var(--t-primary)' }}>
              Results ({rows.length})
            </h2>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={copyTable}>
                {copied ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}
              </Button>
              <Button variant="action" onClick={exportSheet} disabled={exporting || sent || rows.length === 0}>
                {exporting ? 'Sending…' : sent ? <><Check size={14} /> Sent</> : <>Send to Google Sheet</>}
              </Button>
            </div>
          </div>

          <div className="max-h-[calc(100vh-260px)] overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left" style={{ color: 'var(--t-label)' }}>
                  {(hasScores ? ['Agent', 'Numbers', 'Scores', 'Note', 'Red Flag'] : ['Agent', 'Numbers', 'Note', 'Red Flag']).map((h) => (
                    <th key={h} className="sticky top-0 z-10 px-4 py-2.5 font-black uppercase text-[10px] tracking-wider"
                        style={{ background: 'var(--surface-card)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-b-subtle align-top">
                    <td className="whitespace-nowrap px-4 py-2.5 font-medium" style={{ color: 'var(--t-primary)' }}>{r.agent}</td>
                    <td className="px-4 py-2.5 font-mono">
                      {r.phones.map((p, j) => (
                        <div key={j} style={{ color: 'var(--t-primary)' }}>
                          {p.phone}
                          {p.flags.length > 0 && (
                            <span className="ml-2 text-[10px] font-sans font-bold" style={{ color: 'var(--semantic-error)' }}>
                              {p.flags.join(', ')}
                            </span>
                          )}
                        </div>
                      ))}
                      {r.phones.length === 0 && <span style={{ color: 'var(--t-muted)' }}>—</span>}
                    </td>
                    {hasScores && (
                      <td className="px-4 py-2.5">
                        {r.scores ? <ScoreBadges scores={r.scores} /> : <span style={{ color: 'var(--t-muted)' }}>—</span>}
                      </td>
                    )}
                    <td className="px-4 py-2.5" style={{ color: r.source === 'flagged' || r.source === 'audited' ? 'var(--semantic-error)' : 'var(--t-muted)' }}>
                      {r.note}
                    </td>
                    <td className="px-4 py-2.5">
                      {r.red_flag ? (
                        <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-bold text-white" style={{ background: '#c0392b' }}>
                          <AlertTriangle size={11} /> {r.flagged_count}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--t-muted)' }}>{r.flagged_count || '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {skipped.length > 0 && (
            <p className="border-t border-b-subtle p-4 text-xs" style={{ color: 'var(--t-muted)' }}>
              Skipped (no data found): {skipped.join(', ')}
            </p>
          )}
        </section>
      )}
    </div>
  )
}
