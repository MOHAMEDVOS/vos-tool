import { api, apiUrl } from './client'

export interface GatherResult {
  run_id: string
  dialers_ok: string[]
  dialers_failed: string[]
  agent_count: number
  flagged_agent_count: number
  total_rows: number
}

export interface ScorePhone {
  phone: string
  flags: string[]
}

/** Per-point verdicts from the heavy-audit "Audit & Score" flow. Each is "Yes"/"No".
 *  Issue side: late_hello/releasing === "Yes"; rebuttal_ok/agent_intro/reason === "No". */
export interface AuditScores {
  late_hello: string
  releasing: string
  rebuttal_ok: string
  agent_intro: string
  reason: string
}

export interface ScoreRow {
  agent: string
  phones: ScorePhone[]
  note: string
  flag_types: string[]
  flagged_count?: number
  red_flag: boolean
  source: 'flagged' | 'random' | 'audited'
  dialer: string
  // present only on audited rows
  scores?: AuditScores
  sample_count?: number
  action_count?: number
}

/** Live progress for an audit run. */
export interface AuditProgress {
  agent_idx: number
  total: number
  agent: string
  phase: 'download' | 'analyze' | 'done' | 'skipped'
  downloaded?: number
  dl_total?: number
}

export interface ExportResult {
  tab: string
  rows_added: number
  start_row: number
  sheet_url: string
}

export interface GenerateResult {
  rows: ScoreRow[]
  skipped: string[]
  date?: string
}

function token(): string {
  return localStorage.getItem('vos_token') ?? ''
}

export const scoringApi = {
  /** SSE: pull all dialers + flagged calls for a date. Resolves with the final GatherResult. */
  gatherStream: async (
    date: string | undefined,
    onMessage: (event: string, data: string) => void,
    signal: AbortSignal,
  ): Promise<GatherResult> => {
    const res = await fetch(apiUrl('/api/scoring/gather'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` },
      body: JSON.stringify({ date }),
      signal,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new Error(text || `HTTP ${res.status}`)
    }
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let result: GatherResult | null = null
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()!
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const raw = line.slice(5).trim()
        if (!raw) continue
        try {
          const { event, data } = JSON.parse(raw)
          onMessage(event, data)
          if (event === 'done') result = JSON.parse(data) as GatherResult
          if (event === 'error') throw new Error(data)
        } catch (e) {
          if (e instanceof Error && e.message && !e.message.startsWith('{')) throw e
          /* ping/keep-alive */
        }
      }
    }
    if (!result) throw new Error('Gather finished without a result')
    return result
  },

  generate: (run_id: string, agent_names: string[]) =>
    api.post<GenerateResult>('/api/scoring/generate', { run_id, agent_names }),

  /** SSE: heavy-audit each agent (5 samples, 20s+) and majority-vote the 5 scoring points.
   *  Resolves with the rows scored so far — even if the run was cancelled mid-way. */
  auditStream: async (
    run_id: string,
    agent_names: string[],
    onProgress: (p: AuditProgress) => void,
    signal: AbortSignal,
  ): Promise<GenerateResult> => {
    const res = await fetch(apiUrl('/api/scoring/audit'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` },
      body: JSON.stringify({ run_id, agent_names }),
      signal,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new Error(text || `HTTP ${res.status}`)
    }
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let result: GenerateResult | null = null
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()!
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const raw = line.slice(5).trim()
        if (!raw) continue
        try {
          const { event, data } = JSON.parse(raw)
          if (event === 'progress') {
            try { onProgress(JSON.parse(data) as AuditProgress) } catch { /* ignore */ }
          } else if (event === 'done' || event === 'cancelled') {
            result = JSON.parse(data) as GenerateResult
          } else if (event === 'error') {
            throw new Error(data)
          }
        } catch (e) {
          if (e instanceof Error && e.message && !e.message.startsWith('{')) throw e
          /* ping/keep-alive */
        }
      }
    }
    if (!result) throw new Error('Audit finished without a result')
    return result
  },

  exportSheet: (rows: ScoreRow[], title?: string) =>
    api.post<ExportResult>('/api/scoring/export-sheet', { rows, title }),
}
