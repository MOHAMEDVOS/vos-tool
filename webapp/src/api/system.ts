import { api } from './client'
import type { GenericActionResponse, ReadonlyStatus, SessionInfo, SystemHealth } from '@/types/api'

export const systemApi = {
  readonlyStatus: () => api.get<ReadonlyStatus>('/api/system/readonly-status'),
  health: () => api.get<SystemHealth>('/api/system/health'),
  sessions: () => api.get<SessionInfo[]>('/api/system/sessions'),
  invalidateSession: (username: string) => api.post<GenericActionResponse>(`/api/system/sessions/${encodeURIComponent(username)}/invalidate`),
}
