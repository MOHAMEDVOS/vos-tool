import { api } from '@/api/client'

export interface TlActionResult {
  sheet_row: number
  action_date: string
  details: string
  team_leader: string
}

export interface TlActionsReconciliation {
  start_date: string
  end_date: string
  sheet_count: number
  missing_count: number
  results: TlActionResult[]
}

export interface TlActionFormLinks {
  podio_url: string
  google_form_url: string
  agent_name: string
  agent_warning?: string | null
}

export interface PodioConnectionStatus {
  configured: boolean
  connected: boolean
}

export const tlActionsApi = {
  reconcile: (start_date: string, end_date: string) =>
    api.post<TlActionsReconciliation>('/api/tl-actions/reconcile', { start_date, end_date }),
  prepare: (row: TlActionResult) =>
    api.post<TlActionFormLinks>('/api/tl-actions/prepare', {
      sheet_row: row.sheet_row,
      action_date: row.action_date,
      details: row.details,
    }),
  podioStatus: () => api.get<PodioConnectionStatus>('/api/tl-actions/podio/status'),
  podioConnect: () => api.get<{ auth_url: string }>('/api/tl-actions/podio/connect'),
  checkPodio: (row: TlActionResult, started_after?: string) => api.post<{ confirmed: boolean; item_id: number | null }>('/api/tl-actions/podio/check', {
    sheet_row: row.sheet_row,
    action_date: row.action_date,
    details: row.details,
    started_after,
  }),
}
