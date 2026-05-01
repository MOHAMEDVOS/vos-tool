import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface BadgeState {
  flaggedCount: number
  // map of username -> lastSeenCount so each user's seen state is independent
  seenByUser: Record<string, number>
  currentUser: string
  setCurrentUser: (username: string) => void
  setFlaggedCount: (n: number) => void
  markAsSeen: () => void
}

export const useBadgeStore = create<BadgeState>()(
  persist(
    (set, get) => ({
      flaggedCount: 0,
      seenByUser: {},
      currentUser: '',
      setCurrentUser: (username) => set({ currentUser: username }),
      setFlaggedCount: (n) => set({ flaggedCount: n }),
      markAsSeen: () =>
        set((state) => ({
          seenByUser: {
            ...state.seenByUser,
            [state.currentUser]: state.flaggedCount,
          },
        })),
    }),
    { name: 'badge-store' }
  )
)

// Unread count for current user
export function useUnreadCount() {
  return useBadgeStore((s) =>
    Math.max(0, s.flaggedCount - (s.seenByUser[s.currentUser] ?? 0))
  )
}
