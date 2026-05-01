import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  username: string | null
  name: string | null
  picture: string | null
  role: string | null
  sessionId: string | null
  setAuth: (token: string, username: string, role: string, sessionId: string, name?: string, picture?: string) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      name: null,
      picture: null,
      role: null,
      sessionId: null,

      setAuth: (token, username, role, sessionId, name, picture) => {
        localStorage.setItem('vos_token', token)
        set({ token, username, role, sessionId, name: name || null, picture: picture || null })
      },

      clearAuth: () => {
        localStorage.removeItem('vos_token')
        set({ token: null, username: null, name: null, picture: null, role: null, sessionId: null })
      },
    }),
    {
      name: 'vos-auth',
      partialize: (s) => ({ 
        token: s.token, 
        username: s.username, 
        name: s.name, 
        picture: s.picture, 
        role: s.role, 
        sessionId: s.sessionId 
      }),
    },
  ),
)
