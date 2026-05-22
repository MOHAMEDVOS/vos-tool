import { create } from 'zustand'
import { readymodeApi, type DownloadRequest } from '@/api/readymode'
import { type LogLine, type LogStage, type StreamStatus, type DoneResult, type ProgressState, type AnalysisProgress } from '@/hooks/useAuditStream'
import { useAuthStore } from './authStore'

interface AuditState {
  status: StreamStatus
  logs: LogLine[]
  result: DoneResult | null
  error: string | null
  progress: ProgressState | null
  analysisProgress: AnalysisProgress | null
  abortController: AbortController | null
  
  // Actions
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
        token,
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
    } catch (e: any) {
      if (e?.name === 'AbortError') {
        set({ status: 'cancelled' })
      } else {
        set({ error: e?.message ?? 'Unknown error', status: 'error' })
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
