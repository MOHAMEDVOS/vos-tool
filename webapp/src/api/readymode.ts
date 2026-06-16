import { api } from './client'
import type { ReadyModeStatus } from '@/types/api'

export const READYMODE_DIALER_URLS: Record<string, string> = {
  resva: 'https://resva.readymode.com/',
  resva2: 'https://resva2.readymode.com/',
  resva4: 'https://resva4.readymode.com/',
  resva5: 'https://resva5.readymode.com/',
  resva6: 'https://resva6.readymode.com/',
  resva7: 'https://resva7.readymode.com/',
}

export const DISPOSITIONS = [
  'Spanish Speaker',
  'DNC - Unknown',
  'Unknown',
  'DNC - Decision Maker',
  'Wrong Number',
  'Decision Maker - NYI',
  'Dead Call',
  'Not logged',
]

export const DURATION_FILTERS = [
  { value: 'all', label: 'All durations' },
  { value: 'lt30', label: 'Less than 30 seconds' },
  { value: '30to60', label: '30 seconds - 1:00' },
  { value: '60to600', label: '1:00 to 10:00' },
  { value: 'gt_custom', label: 'Greater than...' },
  { value: 'lt_custom', label: 'Less than...' },
]

export interface DownloadRequest {
  dialer_url: string
  dialer_url_2?: string  // agent audit only; each dialer gets max_calls independently
  agent_name: string
  campaign_name?: string
  max_calls: number
  start_date: string
  end_date: string
  start_time?: string   // e.g. "02:30 PM" — optional start-of-day time filter
  dispositions: string[]
  duration_filter: string
  custom_duration_seconds?: number
  audit_type: 'heavy' | 'lite'
}

export const readymodeApi = {
  status: () => api.get<ReadyModeStatus>('/api/readymode/status'),
  download: (body: DownloadRequest) => api.post<ReadyModeStatus>('/api/readymode/download', body),
  streamFetch: async (
    body: DownloadRequest,
    token: string,
    onMessage: (event: string, data: string) => void,
    signal: AbortSignal,
  ): Promise<void> => {
    const res = await fetch('/api/readymode/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
      signal,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new Error(text || `HTTP ${res.status}`)
    }
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''
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
        } catch { /* ping/keep-alive lines */ }
      }
    }
  },
  cancel: (token: string) =>
    fetch('/api/readymode/cancel', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }),
}
