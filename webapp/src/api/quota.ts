import { api } from './client'
import type { GenericActionResponse, QuotaStatus } from '@/types/api'

export const quotaApi = {
  status: () => api.get<QuotaStatus>('/api/quota/status'),
  redistribution: () => api.get<Record<string, unknown>>('/api/quota/redistribution'),
  preview: (allocations: Record<string, number>) => api.post<Record<string, unknown>>('/api/quota/redistribution/preview', { allocations }),
  apply: (allocations: Record<string, number>) => api.post<GenericActionResponse>('/api/quota/redistribution/apply', { allocations }),
  suggest: () => api.get<Record<string, unknown>>('/api/quota/redistribution/suggest'),
  getAdminLimits: () => api.get<Record<string, any>>('/api/quota/admin-limits'),
  setAdminLimits: (admin_username: string, max_users: number, daily_quota: number) =>
    api.put<GenericActionResponse>('/api/quota/admin-limits', { admin_username, max_users, daily_quota }),
}
