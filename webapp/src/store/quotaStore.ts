import { create } from 'zustand'
import { userApi } from '@/api/user'
import type { UsageInfo } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

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
    } catch (error: unknown) {
      set({ error: getErrorMessage(error, 'Failed to fetch usage data'), isLoading: false })
    }
  },
}))
