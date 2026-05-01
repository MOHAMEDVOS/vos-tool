import { Navigate } from 'react-router-dom'
import { useEffect } from 'react'
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
