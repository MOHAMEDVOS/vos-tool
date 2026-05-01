import { api } from './client'
import type {
  GenericActionResponse,
  PendingPhrase,
  PhraseLearningSettings,
  PhraseStats,
} from '@/types/api'

export const phrasesApi = {
  stats: () => api.get<PhraseStats>('/api/phrases/stats'),
  repository: () => api.get<Record<string, string[]>>('/api/phrases/'),
  pending: (status = 'pending') => api.get<PendingPhrase[]>(`/api/phrases/pending?status_filter=${encodeURIComponent(status)}`),
  add: (phrase: string, category: string) => api.post<GenericActionResponse>('/api/phrases/', { phrase, category }),
  bulk: (phrases: string[], category: string) => api.post<{ success: boolean; added_count: number; skipped_count: number }>('/api/phrases/bulk', { phrases, category }),
  approve: (id: string) => api.post<GenericActionResponse>(`/api/phrases/${id}/approve`),
  reject: (id: string, reason = '') => api.post<GenericActionResponse>(`/api/phrases/${id}/reject`, { reason }),
  approveAll: () => api.post<{ success: boolean; message?: string }>('/api/phrases/approve-all'),
  approveByQuality: (min_quality_score: number) => api.post<{ success: boolean; message?: string }>('/api/phrases/approve-by-quality', { min_quality_score }),
  approveByCategory: (category: string, min_quality_score: number) => api.post<{ success: boolean; message?: string }>('/api/phrases/approve-by-category', { category, min_quality_score }),
  removeDuplicates: () => api.post<{ success: boolean; message?: string }>('/api/phrases/remove-duplicates'),
  settings: () => api.get<PhraseLearningSettings>('/api/phrases/settings'),
  updateSettings: (body: PhraseLearningSettings) => api.put<PhraseLearningSettings & { success: boolean; message?: string }>('/api/phrases/settings', body),
}
