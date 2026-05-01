import { api } from './client'
import type { GenericActionResponse, SharingConfig } from '@/types/api'

export const sharingApi = {
  config: () => api.get<SharingConfig>('/api/sharing/config'),
  groups: () => api.get<Record<string, unknown>>('/api/sharing/groups'),
  createGroup: (group_name: string, members: string[]) => api.post<GenericActionResponse>('/api/sharing/groups', { group_name, members }),
  updateGroup: (group_name: string, members: string[]) => api.put<GenericActionResponse>(`/api/sharing/groups/${encodeURIComponent(group_name)}`, { members }),
  deleteGroup: (group_name: string) => api.delete<GenericActionResponse>(`/api/sharing/groups/${encodeURIComponent(group_name)}`),
  syncModes: () => api.post<{ success: boolean; message?: string; updated_count: number }>('/api/sharing/sync-modes'),
  myMode: () => api.get<{ mode: string }>('/api/sharing/me/mode'),
}
