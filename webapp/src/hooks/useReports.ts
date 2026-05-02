import { useMutation, useQuery } from '@tanstack/react-query'
import { reportsApi } from '@/api/reports'
import { ApiError } from '@/api/client'

export function useWorkspaceStatus() {
  return useQuery({
    queryKey: ['workspace-status'],
    queryFn: reportsApi.workspaceStatus,
    staleTime: 60_000,
  })
}

export function useGenerateCampaignReport() {
  return useMutation({
    mutationFn: reportsApi.generateCampaignReport,
  })
}

export function isGoogleNotConnectedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401 && error.message === 'google_not_connected'
}
