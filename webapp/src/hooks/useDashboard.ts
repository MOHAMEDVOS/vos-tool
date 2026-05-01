import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/api/dashboard'
import { useBadgeStore } from '@/store/badgeStore'
import { useEffect } from 'react'

export function useAgentAudits(params?: { start_date?: string; end_date?: string; agent_name?: string }) {
  return useQuery({
    queryKey: ['agent-audits', params],
    queryFn:  () => dashboardApi.agentAudits(params),
    staleTime: 30_000,
  })
}

export function useLiteAudits(params?: { start_date?: string; end_date?: string }) {
  return useQuery({
    queryKey: ['lite-audits', params],
    queryFn:  () => dashboardApi.liteAudits(params),
    staleTime: 30_000,
  })
}

export function useCampaignAudits(params?: { campaign?: string; start_date?: string; end_date?: string }) {
  return useQuery({
    queryKey: ['campaign-audits', params],
    queryFn:  () => dashboardApi.campaignAudits(params),
    staleTime: 30_000,
  })
}

export function useCampaigns() {
  return useQuery({
    queryKey: ['campaigns'],
    queryFn:  dashboardApi.campaigns,
    staleTime: 60_000,
  })
}

export function useFlaggedCalls(params?: { start_date?: string; end_date?: string }) {
  return useQuery({
    queryKey: ['flagged-calls', params],
    queryFn:  () => dashboardApi.flaggedCalls(params),
    staleTime: 30_000,
  })
}

// Polls badge count every 60 s and syncs to Zustand
export function useFlaggedBadge() {
  const setFlaggedCount = useBadgeStore((s) => s.setFlaggedCount)
  const result = useQuery({
    queryKey: ['flagged-count'],
    queryFn:  dashboardApi.flaggedCount,
    refetchInterval: 60_000,
  })
  useEffect(() => {
    if (result.data) setFlaggedCount(result.data.count)
  }, [result.data, setFlaggedCount])
  return result
}
