import { api } from './client'
import type { DashboardData, FlaggedCall, ReachabilityScan } from '@/types/api'

export const dashboardApi = {
  agentAudits: (params?: { start_date?: string; end_date?: string; agent_name?: string }) => {
    const q = new URLSearchParams()
    if (params?.start_date)  q.set('start_date',  params.start_date)
    if (params?.end_date)    q.set('end_date',    params.end_date)
    if (params?.agent_name)  q.set('agent_name',  params.agent_name)
    const qs = q.toString()
    return api.get<DashboardData>(`/api/dashboard/agent-audits${qs ? '?' + qs : ''}`)
  },

  liteAudits: (params?: { start_date?: string; end_date?: string }) => {
    const q = new URLSearchParams()
    if (params?.start_date) q.set('start_date', params.start_date)
    if (params?.end_date)   q.set('end_date',   params.end_date)
    const qs = q.toString()
    return api.get<DashboardData>(`/api/dashboard/lite-audits${qs ? '?' + qs : ''}`)
  },

  campaignAudits: (params?: { campaign?: string; start_date?: string; end_date?: string }) => {
    const q = new URLSearchParams()
    if (params?.campaign)    q.set('campaign',    params.campaign)
    if (params?.start_date)  q.set('start_date',  params.start_date)
    if (params?.end_date)    q.set('end_date',    params.end_date)
    const qs = q.toString()
    return api.get<DashboardData>(`/api/dashboard/campaign-audits${qs ? '?' + qs : ''}`)
  },

  campaigns: () => api.get<string[]>('/api/dashboard/campaigns'),

  flaggedCalls: (params?: { start_date?: string; end_date?: string }) => {
    const q = new URLSearchParams()
    if (params?.start_date) q.set('start_date', params.start_date)
    if (params?.end_date)   q.set('end_date',   params.end_date)
    const qs = q.toString()
    return api.get<FlaggedCall[]>(`/api/dashboard/flagged-calls${qs ? '?' + qs : ''}`)
  },

  flaggedCount: () => api.get<{ count: number }>('/api/dashboard/flagged-calls/count'),

  campaignDisposition: (params: { campaign: string; start_date?: string; end_date?: string }) => {
    const q = new URLSearchParams()
    q.set('campaign', params.campaign)
    if (params.start_date) q.set('start_date', params.start_date)
    if (params.end_date)   q.set('end_date',   params.end_date)
    return api.get<ReachabilityScan>(`/api/dashboard/campaign-disposition?${q.toString()}`)
  },

  clearAgentAudits:    () => api.post('/api/dashboard/clear/agent-audits'),
  clearLiteAudits:     () => api.post('/api/dashboard/clear/lite-audits'),
  clearCampaignAudits: (campaign?: string) => 
    api.post(`/api/dashboard/clear/campaign-audits${campaign ? `?campaign=${encodeURIComponent(campaign)}` : ''}`),
}
