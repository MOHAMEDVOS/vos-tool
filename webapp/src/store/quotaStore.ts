import { create } from 'zustand'
import { userApi } from '@/api/user'
import type { UsageInfo } from '@/types/api'

interface QuotaState {
  usage: UsageInfo | null
  isLoading: boolean
  error: string | null
  fetchUsage: () => Promise<void>
}

export const useQuotaStore = create<QuotaState>((set) => ({
  usage: null,
  isLoading: false,
  error: null,

  fetchUsage: async () => {
    set({ isLoading: true, error: null })
    try {
      const resp = await userApi.getEverything()
      set({ usage: resp.quota_and_usage.daily_usage, isLoading: false })
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch usage data', isLoading: false })
    }
  },
}))
