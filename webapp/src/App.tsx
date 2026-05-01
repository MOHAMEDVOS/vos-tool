import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@/styles/tokens.css'
import { AppShell } from '@/components/layout/AppShell'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { useUiStore } from '@/store/uiStore'
import { useFlaggedBadge } from '@/hooks/useDashboard'
import { useBadgeStore } from '@/store/badgeStore'

import { TopLoadingBar } from '@/components/ui/TopLoadingBar'
import { LoginPage }      from '@/pages/LoginPage'
import { DashboardPage }  from '@/pages/DashboardPage'
import { ActionsPage }    from '@/pages/ActionsPage'
import { CallReviewPage } from '@/pages/CallReviewPage'
import { AuditPage }      from '@/pages/AuditPage'
import { PhrasesPage }    from '@/pages/PhrasesPage'
import { SettingsPage }   from '@/pages/SettingsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

import { useAuthStore } from '@/store/authStore'

const TAB_ROLES: Partial<Record<string, string[]>> = {
  'Phrase Management': ['Owner'],
  'Settings': ['Owner', 'Admin'],
}

function InnerApp() {
  const activeTab = useUiStore((s) => s.activeTab)
  const setActiveTab = useUiStore((s) => s.setActiveTab)
  const theme = useUiStore((s) => s.theme)
  const role = useAuthStore((s) => s.role)
  useFlaggedBadge()

  useEffect(() => {
    const html = document.documentElement
    html.classList.add('light')
    html.classList.remove('dark')
  }, [theme])

  useEffect(() => {
    if (role) {
      const allowedRoles = TAB_ROLES[activeTab]
      if (allowedRoles && !allowedRoles.includes(role)) {
        setActiveTab('Dashboard')
      }
    }
  }, [activeTab, role, setActiveTab])

  const allowedRoles = TAB_ROLES[activeTab]
  if (allowedRoles && role && !allowedRoles.includes(role)) {
    return null
  }

  return (
    <AppShell pageKey={activeTab}>
      {activeTab === 'Audit'             && <AuditPage />}
      {activeTab === 'Actions'           && <ActionsPage />}
      {activeTab === 'Call Review'       && <CallReviewPage />}
      {activeTab === 'Dashboard'         && <DashboardPage />}
      {activeTab === 'Phrase Management' && <PhrasesPage />}
      {activeTab === 'Settings'          && <SettingsPage />}
    </AppShell>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TopLoadingBar />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <InnerApp />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
