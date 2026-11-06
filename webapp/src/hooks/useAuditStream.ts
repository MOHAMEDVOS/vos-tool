import { useState, useRef, useCallback } from 'react'
import { readymodeApi, type DownloadRequest } from '@/api/readymode'
import { useAuthStore } from '@/store/authStore'
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

// Infer phase strictly by what has been seen — never jumps ahead or falls back randomly.
// Phases are strictly ordered: idle → login → collecting → analyzing
// DOWNLOAD stage = files being downloaded (collecting, not analyzing)
// Analyzing only starts after DOWNLOAD_COMPLETE log line appears
export function inferPhase(logs: LogLine[]): 'login' | 'collecting' | 'analyzing' | 'idle' {
  if (logs.length === 0) return 'idle'
  const hasDownloadComplete = logs.some(l => l.text.includes('DOWNLOAD_COMPLETE') || l.text.includes('files downloaded'))
  if (hasDownloadComplete) return 'analyzing'
  const hasCollecting = logs.some(
    l => l.stage === 'DATE' || l.stage === 'SEARCH' || l.stage === 'DOWNLOAD' || l.stage === 'PAGE' || l.stage === 'NEXT'
  )
  if (hasCollecting) return 'collecting'
  return 'login'
}

export function useAuditStream() {
  const [status, setStatus] = useState<StreamStatus>('idle')
  const [logs, setLogs] = useState<LogLine[]>([])
  const [result, setResult] = useState<DoneResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<ProgressState | null>(null)
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgress | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const idRef = useRef(0)
  const token = useAuthStore(s => s.token)

  const start = useCallback(async (body: DownloadRequest) => {
    if (!token) {
      setError('Auth token missing')
      setStatus('error')
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLogs([])
    setResult(null)
    setError(null)
    setProgress(null)
    setAnalysisProgress(null)
    setStatus('running')

    try {
      await readymodeApi.streamFetch(
        body,
        token,
        (event, data) => {
          if (event === 'log') {
            const { stage, text } = parseStage(data)
            setLogs(prev => [...prev, { id: idRef.current++, stage, text }])

            const analysisMatch = text.match(/(?:Async|Lite) Progress: (\d+)\/(\d+)/)
            if (analysisMatch) {
              setAnalysisProgress({
                completed: parseInt(analysisMatch[1], 10),
                total: parseInt(analysisMatch[2], 10),
              })
            }
          } else if (event === 'progress') {
            try {
              const p = JSON.parse(data)
              setProgress({ downloaded: p.downloaded, total: p.total })
            } catch { /* ignore */ }
          } else if (event === 'done') {
            try {
              const parsed: DoneResult = JSON.parse(data)
              setResult(parsed)
            } catch {
              setResult({ downloaded: 0, analyzed: 0, message: data })
            }
            setStatus('done')
          } else if (event === 'cancelled') {
            setStatus('cancelled')
          } else if (event === 'error') {
            setError(data)
            setStatus('error')
          }
        },
        controller.signal,
      )
    } catch (err: unknown) {
      if (isAbortError(err)) {
        setStatus('cancelled')
      } else {
        setError(getErrorMessage(err, 'Unknown error'))
        setStatus('error')
      }
    }
  }, [token])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    if (token) readymodeApi.cancel(token)
    setStatus('cancelled')
  }, [token])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setStatus('idle')
    setLogs([])
    setResult(null)
    setError(null)
    setProgress(null)
    setAnalysisProgress(null)
  }, [])

  return { status, logs, result, error, progress, analysisProgress, start, cancel, reset }
}
