import { api } from './client'
import type { EverythingPayload } from '@/types/api'

export const userApi = {
  getEverything: () => api.get<EverythingPayload>('/api/user/me/everything'),
}
