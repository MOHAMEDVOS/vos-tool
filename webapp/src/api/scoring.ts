import { api, apiUrl } from './client'
import { readSSEStream } from '@/utils/sseStream'

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
  /** true = random filler number from the agent's CSV (not audited/scored). */
  padded?: boolean
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

export const scoringApi = {
  /** SSE: pull all dialers + flagged calls for a date. Resolves with the final GatherResult. */
  gatherStream: async (
    date: string | undefined,
    onMessage: (event: string, data: string) => void,
    signal: AbortSignal,
  ): Promise<GatherResult> => {
    let result: GatherResult | null = null
    await readSSEStream(apiUrl('/api/scoring/gather'), {
      body: { date },
      signal,
      checkOk: true,
      onEvent: (event, data) => {
        onMessage(event, data as string)
        if (event === 'done') result = JSON.parse(data as string) as GatherResult
        if (event === 'error') throw new Error(data as string)
      },
      onParseError: (e) => {
        if (e instanceof Error && e.message && !e.message.startsWith('{')) throw e
        /* ping/keep-alive */
      },
    })
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
    let result: GenerateResult | null = null
    await readSSEStream(apiUrl('/api/scoring/audit'), {
      body: { run_id, agent_names },
      signal,
      checkOk: true,
      onEvent: (event, data) => {
        if (event === 'progress') {
          try { onProgress(JSON.parse(data as string) as AuditProgress) } catch { /* ignore */ }
        } else if (event === 'done' || event === 'cancelled') {
          result = JSON.parse(data as string) as GenerateResult
        } else if (event === 'error') {
          throw new Error(data as string)
        }
      },
      onParseError: (e) => {
        if (e instanceof Error && e.message && !e.message.startsWith('{')) throw e
        /* ping/keep-alive */
      },
    })
    if (!result) throw new Error('Audit finished without a result')
    return result
  },

  exportSheet: (rows: ScoreRow[], title?: string) =>
    api.post<ExportResult>('/api/scoring/export-sheet', { rows, title }),
}
