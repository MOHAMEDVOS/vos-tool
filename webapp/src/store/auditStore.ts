import { create } from 'zustand'
import { readymodeApi, type DownloadRequest } from '@/api/readymode'
import { useAuthStore } from './authStore'
import { getErrorMessage, isAbortError } from '@/utils/errors'

export type LogStage = 'WAIT' | 'SUCCESS' | 'DATE' | 'SEARCH' | 'DOWNLOAD' | 'PAGE' | 'NEXT' | 'CANCELLED' | 'FAILED' | 'INFO'

export interface LogLine {
  id: number
  stage: LogStage
  text: string
}

export type StreamStatus = 'idle' | 'running' | 'done' | 'cancelled' | 'error'

export interface DoneResult {
  downloaded: number
  analyzed: number
  skipped?: number
  message: string
}

export interface ProgressState {
  downloaded: number
  total: number
}

export interface AnalysisProgress {
  completed: number
  total: number
}

// Infer phase strictly by what has been seen — never jumps ahead or falls back randomly.
// Phases are strictly ordered: idle → login → collecting → analyzing
// DOWNLOAD stage = files being downloaded (collecting, not analyzing)
// Analyzing only starts after DOWNLOAD_COMPLETE log line appears
export function inferPhase(logs: LogLine[]): 'login' | 'collecting' | 'analyzing' | 'idle' {
  if (logs.length === 0) return 'idle'
  const hasDownloadComplete = logs.some(l => l.text.includes('DOWNLOAD_COMPLETE') || l.text.includes('files downloaded'))
  if (hasDownloadComplete) return 'analyzing'
  const stages = new Set(logs.map(l => l.stage))
  if (stages.has('DOWNLOAD') || stages.has('SEARCH')) return 'collecting'
  if (stages.has('WAIT') || stages.has('DATE') || stages.has('PAGE') || stages.has('NEXT') || stages.has('SUCCESS')) return 'login'
  return 'idle'
}

interface AuditState {
  status: StreamStatus
  logs: LogLine[]
  result: DoneResult | null
  error: string | null
  progress: ProgressState | null
  analysisProgress: AnalysisProgress | null
  abortController: AbortController | null

  start: (body: DownloadRequest) => Promise<void>
  cancel: () => void
  reset: () => void
}

let _idCounter = 0

function parseStage(line: string): { stage: LogStage; text: string } {
  const prefixes: [string, LogStage][] = [
    ['WAIT', 'WAIT'],
    ['SUCCESS', 'SUCCESS'],
    ['DATE', 'DATE'],
    ['SEARCH', 'SEARCH'],
    ['DOWNLOAD', 'DOWNLOAD'],
    ['PAGE', 'PAGE'],
    ['NEXT', 'NEXT'],
    ['CANCELLED', 'CANCELLED'],
    ['FAILED', 'FAILED'],
  ]
  for (const [prefix, stage] of prefixes) {
    if (line.startsWith(prefix + ' ') || line.startsWith(prefix + ':')) {
      return { stage, text: line.slice(prefix.length + 1).trim() }
    }
  }
  return { stage: 'INFO', text: line }
}

export const useAuditStore = create<AuditState>((set, get) => ({
  status: 'idle',
  logs: [],
  result: null,
  error: null,
  progress: null,
  analysisProgress: null,
  abortController: null,

  start: async (body) => {
    const token = useAuthStore.getState().token
    if (!token) {
      set({ error: 'Auth token missing', status: 'error' })
      return
    }

    const { abortController } = get()
    abortController?.abort()

    const newController = new AbortController()
    set({
      logs: [],
      result: null,
      error: null,
      progress: null,
      analysisProgress: null,
      status: 'running',
      abortController: newController,
    })

    try {
      await readymodeApi.streamFetch(
        body,
        (event, data) => {
          if (event === 'log') {
            const { stage, text } = parseStage(data)
            set((state) => ({
              logs: [...state.logs, { id: _idCounter++, stage, text }]
            }))

            const analysisMatch = text.match(/(?:Async|Lite) Progress: (\d+)\/(\d+)/)
            if (analysisMatch) {
              set({
                analysisProgress: {
                  completed: parseInt(analysisMatch[1], 10),
                  total: parseInt(analysisMatch[2], 10)
                }
              })
            }
          } else if (event === 'progress') {
            try {
              const p = JSON.parse(data)
              set({ progress: { downloaded: p.downloaded, total: p.total } })
            } catch { /* ignore */ }
          } else if (event === 'done') {
            try {
              const parsed: DoneResult = JSON.parse(data)
              set({ result: parsed })
            } catch {
              set({ result: { downloaded: 0, analyzed: 0, message: data } })
            }
            set({ status: 'done' })
          } else if (event === 'cancelled') {
            set({ status: 'cancelled' })
          } else if (event === 'error') {
            set({ error: data, status: 'error' })
          }
        },
        newController.signal,
      )
      // Stream closed normally but may not have sent a done/error event (e.g. proxy disconnect).
      // If status is still 'running', the audit didn't complete — surface it as an error.
      if (get().status === 'running') {
        set({ error: 'Connection lost before audit completed. The download may still be running on the server — check back in a few minutes.', status: 'error' })
      }
    } catch (error: unknown) {
      if (isAbortError(error)) {
        set({ status: 'cancelled' })
      } else {
        set({ error: getErrorMessage(error, 'Unknown error'), status: 'error' })
      }
    }
  },

  cancel: () => {
    const token = useAuthStore.getState().token
    const { abortController } = get()
    abortController?.abort()
    if (token) readymodeApi.cancel(token)
    set({ status: 'cancelled' })
  },

  reset: () => {
    const { abortController } = get()
    abortController?.abort()
    set({
      status: 'idle',
      logs: [],
      result: null,
      error: null,
      progress: null,
      analysisProgress: null,
      abortController: null,
    })
  },
}))
