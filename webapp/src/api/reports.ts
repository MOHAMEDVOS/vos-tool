import { api } from './client'

export interface GenerateReportResponse {
  sheet_url: string
  doc_url: string
}

export interface WorkspaceStatusResponse {
  connected: boolean
}

export interface WorkspaceConnectResponse {
  auth_url: string
}

export const reportsApi = {
  generateCampaignReport: (params: {
    campaign: string
    start_date?: string
    end_date?: string
  }) => api.post<GenerateReportResponse>('/api/reports/campaign/generate', params),

  workspaceStatus: () =>
    api.get<WorkspaceStatusResponse>('/api/auth/google/workspace/status'),

  workspaceConnect: () =>
    api.get<WorkspaceConnectResponse>('/api/auth/google/workspace/connect'),
}
