import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type NavTab = 'Audit' | 'Actions' | 'Call Review' | 'Dashboard' | 'Scoring' | 'Phrase Management' | 'Settings' | 'Users'
type Theme = 'light' | 'dark'

interface UiState {
  activeTab: NavTab
  sidebarCollapsed: boolean
  theme: Theme
  loginAnimating: boolean
  setActiveTab: (tab: NavTab) => void
  setSidebarCollapsed: (v: boolean) => void
  setTheme: (t: Theme) => void
  toggleTheme: () => void
  setLoginAnimating: (v: boolean) => void
}

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme)
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      activeTab: 'Dashboard',
      sidebarCollapsed: false,
      theme: 'light',
      loginAnimating: false,
      setActiveTab: (tab) => set({ activeTab: tab }),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      setTheme: (t) => {
        applyTheme(t)
        set({ theme: t })
      },
      toggleTheme: () => {
        const next: Theme = get().theme === 'light' ? 'dark' : 'light'
        applyTheme(next)
        set({ theme: next })
      },
      setLoginAnimating: (v) => set({ loginAnimating: v }),
    }),
    {
      name: 'vos-ui',
      partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }),
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme)
      },
    },
  ),
)

export type { NavTab, Theme }
