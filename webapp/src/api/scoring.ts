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

export interface ScoreRow {
  agent: string
  phones: ScorePhone[]
  note: string
  flag_types: string[]
  flagged_count: number
  red_flag: boolean
  source: 'flagged' | 'random'
  dialer: string
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

  exportSheet: (rows: ScoreRow[], title?: string) =>
    api.post<ExportResult>('/api/scoring/export-sheet', { rows, title }),
}
