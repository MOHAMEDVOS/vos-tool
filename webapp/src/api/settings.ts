import { api } from './client'
import type {
  AppConfigCategory,
  CreateUserRequest,
  GenericActionResponse,
  UpdateUserRequest,
  UserInfo,
  UserListResponse,
  UserSettings,
} from '@/types/api'

export const settingsApi = {
  me: () => api.get<UserSettings>('/api/settings/'),
  updateMe: (body: Partial<UserSettings>) => api.put<UserSettings>('/api/settings/', body),
  users: () => api.get<UserListResponse>('/api/settings/users'),
  createUser: (body: CreateUserRequest) => api.post<UserInfo>('/api/settings/users', body),
  updateUser: (username: string, body: UpdateUserRequest) => api.put<UserInfo>(`/api/settings/users/${encodeURIComponent(username)}`, body),
  deleteUser: (username: string) => api.delete<{ message: string }>(`/api/settings/users/${encodeURIComponent(username)}`),
  assemblyAiKeyStatus: () => api.get<{ has_key: boolean }>('/api/settings/assemblyai-key'),
  updateAssemblyAiKey: (api_key: string) => api.put<{ status: string; message: string }>('/api/settings/assemblyai-key', { api_key }),
  appConfig: (category: AppConfigCategory) => api.get<Record<string, unknown>>(`/api/settings/app-config/${category}`),
  updateAppConfig: (category: AppConfigCategory, updates: Record<string, unknown>) => api.put<{ success: boolean; category: string; values: Record<string, unknown> }>(`/api/settings/app-config/${category}`, updates),
}
