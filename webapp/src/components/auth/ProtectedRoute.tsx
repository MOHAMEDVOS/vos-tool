import React, { useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/api/auth'
import { Spinner } from '@/components/ui/Spinner'

interface Props {
  children: React.ReactNode
  requiredRole?: string | string[]
}

export function ProtectedRoute({ children, requiredRole }: Props) {
  const { token, role, clearAuth } = useAuthStore()

  const { isLoading, isError } = useQuery({
    queryKey: ['auth-me', token],
    queryFn: authApi.me,
    enabled: Boolean(token),
    retry: false,
    staleTime: 5 * 60 * 1000,   // treat as fresh for 5 min — prevents re-auth during long audits
    gcTime: 10 * 60 * 1000,
  })

  useEffect(() => {
    if (isError) clearAuth()
  }, [clearAuth, isError])

  if (!token) return <Navigate to="/login" replace />
  if (isLoading) return <div className="flex min-h-screen items-center justify-center bg-surface-page"><Spinner size="lg" /></div>
  if (isError) {
    return <Navigate to="/login" replace />
  }

  if (requiredRole) {
    const allowed = Array.isArray(requiredRole) ? requiredRole : [requiredRole]
    if (!role || !allowed.includes(role)) return <Navigate to="/" replace />
  }

  return <>{children}</>
}
