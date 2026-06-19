import { useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { scoringApi, type GatherResult, type ScoreRow } from '@/api/scoring'
import { Copy, Check, ExternalLink, AlertTriangle } from 'lucide-react'

const labelClass = 'text-[10px] font-black uppercase tracking-[0.1em] mb-2 block'
const sectionHeaderClass = 'text-xl font-black mb-4 tracking-tight'

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export function ScoringPage() {
  // ── gather phase ──
  const [date, setDate] = useState(today())
  const [gathering, setGathering] = useState(false)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [gatherResult, setGatherResult] = useState<GatherResult | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // ── generate phase ──
  const [names, setNames] = useState('')
  const [generating, setGenerating] = useState(false)
  const [rows, setRows] = useState<ScoreRow[] | null>(null)
  const [skipped, setSkipped] = useState<string[]>([])

  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [sheetUrl, setSheetUrl] = useState<string | null>(null)
  const [exportMsg, setExportMsg] = useState<string | null>(null)

  const runGather = async () => {
    setError(null); setLogs([]); setProgress(null); setGatherResult(null)
    setRows(null); setSkipped([]); setSheetUrl(null)
    setGathering(true)
    abortRef.current = new AbortController()
    try {
      const result = await scoringApi.gatherStream(
        date,
        (event, data) => {
          if (event === 'log') setLogs((l) => [...l, data])
          else if (event === 'progress') {
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
    setError(null); setGenerating(true); setSheetUrl(null)
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
    setExporting(true); setError(null); setExportMsg(null)
    try {
      const res = await scoringApi.exportSheet(rows, `Scoring ${date}`)
      setSheetUrl(res.sheet_url)
      setExportMsg(`Added ${res.rows_added} rows to "${res.tab}" tab (from row ${res.start_row}).`)
      window.open(res.sheet_url, '_blank')
    } catch (e: any) {
      setError(e?.message || 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-black tracking-tight mb-1" style={{ color: 'var(--t-primary)' }}>Scoring</h1>
      <p className="text-sm mb-8" style={{ color: 'var(--t-muted)' }}>
        Pull phone + agent data from all dialers (Wrong Number &amp; Decision Maker - NYI only), then
        paste agent names to get their sampling list — flagged calls first, otherwise 5 random.
      </p>

      {/* ── Step 1: Gather ── */}
      <section className="rounded-lg border border-b-subtle bg-c-base p-6 mb-6">
        <h2 className={sectionHeaderClass} style={{ color: 'var(--t-primary)' }}>1 · Gather data</h2>
        <div className="flex items-end gap-4 flex-wrap">
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
            <span className="text-xs" style={{ color: 'var(--t-muted)' }}>
              {progress.done}/{progress.total} dialers
            </span>
          )}
          {gathering && <Spinner />}
        </div>

        {logs.length > 0 && (
          <div className="mt-4 max-h-32 overflow-y-auto rounded-md bg-black/5 p-3 text-xs font-mono" style={{ color: 'var(--t-muted)' }}>
            {logs.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        )}

        {gatherResult && (
          <div className="mt-4 text-sm" style={{ color: 'var(--t-primary)' }}>
            ✓ <strong>{gatherResult.agent_count}</strong> agents found
            ({gatherResult.flagged_agent_count} with flagged calls, {gatherResult.total_rows} calls).
            {' '}Dialers OK: {gatherResult.dialers_ok.join(', ') || 'none'}.
            {gatherResult.dialers_failed.length > 0 && (
              <span style={{ color: 'var(--semantic-error)' }}> Failed: {gatherResult.dialers_failed.join(', ')}.</span>
            )}
          </div>
        )}
      </section>

      {/* ── Step 2: Names → Generate ── */}
      <section className="rounded-lg border border-b-subtle bg-c-base p-6 mb-6">
        <h2 className={sectionHeaderClass} style={{ color: 'var(--t-primary)' }}>2 · Agent names</h2>
        <label className={labelClass} style={{ color: 'var(--t-label)' }}>One agent name per line</label>
        <textarea
          value={names}
          onChange={(e) => setNames(e.target.value)}
          rows={6}
          placeholder={'Ahmed Mohamed\nSara Ali\n…'}
          className="w-full rounded-md border border-b-subtle bg-transparent px-3 py-2 text-sm font-mono"
          style={{ color: 'var(--t-primary)' }}
        />
        <div className="mt-3">
          <Button variant="action" onClick={runGenerate} disabled={!gatherResult || generating}>
            {generating ? 'Generating…' : 'Generate'}
          </Button>
          {!gatherResult && <span className="ml-3 text-xs" style={{ color: 'var(--t-muted)' }}>Gather data first.</span>}
        </div>
      </section>

      {error && (
        <div className="mb-6 rounded-md p-3 text-sm" style={{ background: 'rgba(192,57,43,0.1)', color: 'var(--semantic-error)' }}>
          {error}
        </div>
      )}

      {/* ── Step 3: Results ── */}
      {rows && (
        <section className="rounded-lg border border-b-subtle bg-c-base p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className={`${sectionHeaderClass} mb-0`} style={{ color: 'var(--t-primary)' }}>
              3 · Results ({rows.length})
            </h2>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={copyTable}>
                {copied ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}
              </Button>
              <Button variant="action" onClick={exportSheet} disabled={exporting || rows.length === 0}>
                {exporting ? 'Sending…' : <>Send to Google Sheet</>}
              </Button>
            </div>
          </div>

          {sheetUrl && (
            <div className="mb-4 text-sm">
              {exportMsg && <span style={{ color: 'var(--semantic-success, var(--t-primary))' }}>{exportMsg} </span>}
              <a href={sheetUrl} target="_blank" rel="noreferrer"
                 className="inline-flex items-center gap-1" style={{ color: 'var(--b-focus)' }}>
                Open sheet <ExternalLink size={13} />
              </a>
            </div>
          )}

          <div className="overflow-x-auto rounded-md border border-b-subtle">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left" style={{ background: 'var(--surface-card)', color: 'var(--t-label)' }}>
                  <th className="px-3 py-2 font-black uppercase text-[10px] tracking-wider">Agent</th>
                  <th className="px-3 py-2 font-black uppercase text-[10px] tracking-wider">Numbers</th>
                  <th className="px-3 py-2 font-black uppercase text-[10px] tracking-wider">Note</th>
                  <th className="px-3 py-2 font-black uppercase text-[10px] tracking-wider">Red Flag</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-b-subtle align-top">
                    <td className="px-3 py-2 font-medium" style={{ color: 'var(--t-primary)' }}>{r.agent}</td>
                    <td className="px-3 py-2 font-mono">
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
                    <td className="px-3 py-2" style={{ color: r.source === 'flagged' ? 'var(--semantic-error)' : 'var(--t-muted)' }}>
                      {r.note}
                    </td>
                    <td className="px-3 py-2">
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
            <p className="mt-4 text-xs" style={{ color: 'var(--t-muted)' }}>
              Skipped (no data found): {skipped.join(', ')}
            </p>
          )}
        </section>
      )}
    </div>
  )
}
