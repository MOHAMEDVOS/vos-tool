# Anime.js Transitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two anime.js v4 animations — a shockwave reveal on post-login and an eclipse ripple on theme toggle.

**Architecture:** The shockwave is a fixed overlay component (`ShockwaveOverlay`) mounted in `App.tsx`, gated by a `loginAnimating` boolean in `uiStore`. The eclipse ripple is self-contained inside `Sidebar.tsx` — a single `useRef`-managed overlay div that expands from the button position and swaps the theme mid-flight.

**Tech Stack:** animejs v4 (named exports: `createTimeline`, `animate`), React 19, Zustand, Tailwind CSS

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `webapp/src/store/uiStore.ts` | Add `loginAnimating` flag + `setLoginAnimating` action (not persisted) |
| Create | `webapp/src/components/ui/ShockwaveOverlay.tsx` | Full-screen clip-path ripple, watches `loginAnimating`, self-dismisses |
| Modify | `webapp/src/App.tsx` | Mount `<ShockwaveOverlay />` alongside routes |
| Modify | `webapp/src/pages/LoginPage.tsx` | Set `loginAnimating: true` before navigating after login success |
| Modify | `webapp/src/components/layout/Sidebar.tsx` | Eclipse ripple on theme button click — overlay div + icon flip |

---

## Task 1: Add `loginAnimating` to uiStore

**Files:**
- Modify: `webapp/src/store/uiStore.ts`

- [ ] **Step 1: Add the flag and action**

Open `webapp/src/store/uiStore.ts`. The current `UiState` interface and `create()` call need two additions. Replace the file content with:

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type NavTab = 'Audit' | 'Actions' | 'Call Review' | 'Dashboard' | 'Phrase Management' | 'Settings'
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
```

- [ ] **Step 2: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/store/uiStore.ts
git commit -m "feat: add loginAnimating flag to uiStore"
```

---

## Task 2: Create ShockwaveOverlay component

**Files:**
- Create: `webapp/src/components/ui/ShockwaveOverlay.tsx`

- [ ] **Step 1: Create the file**

```typescript
import { useEffect, useRef } from 'react'
import { animate } from 'animejs'
import { useUiStore } from '@/store/uiStore'

/**
 * Full-screen clip-path shockwave that fires once after login.
 * Mounts in App.tsx. Watches loginAnimating from uiStore.
 * Expands from center, then auto-dismisses and clears the flag.
 */
export function ShockwaveOverlay() {
  const loginAnimating   = useUiStore((s) => s.loginAnimating)
  const setLoginAnimating = useUiStore((s) => s.setLoginAnimating)
  const theme            = useUiStore((s) => s.theme)
  const overlayRef       = useRef<HTMLDivElement>(null)
  const hasRun           = useRef(false)

  useEffect(() => {
    if (!loginAnimating || hasRun.current) return
    const el = overlayRef.current
    if (!el) return

    hasRun.current = true

    // Ripple color matches the destination theme background
    el.style.background = theme === 'dark' ? '#0a0a0a' : '#ffffff'
    el.style.clipPath   = 'circle(0% at 50% 50%)'
    el.style.opacity    = '1'

    animate(el, {
      clipPath: [
        { to: 'circle(0% at 50% 50%)' },
        { to: 'circle(150% at 50% 50%)' },
      ],
      duration: 750,
      ease: 'cubicBezier(0.4, 0, 0.2, 1)',
      onComplete: () => {
        // Brief hold so the app behind is fully rendered, then fade out
        animate(el, {
          opacity: [1, 0],
          duration: 320,
          ease: 'cubicBezier(0.16, 1, 0.3, 1)',
          onComplete: () => {
            setLoginAnimating(false)
            hasRun.current = false
          },
        })
      },
    })
  }, [loginAnimating, theme, setLoginAnimating])

  if (!loginAnimating) return null

  return (
    <div
      ref={overlayRef}
      style={{
        position:   'fixed',
        inset:      0,
        zIndex:     9999,
        pointerEvents: 'none',
        willChange: 'clip-path, opacity',
      }}
    />
  )
}
```

- [ ] **Step 2: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/ui/ShockwaveOverlay.tsx
git commit -m "feat: add ShockwaveOverlay component"
```

---

## Task 3: Mount ShockwaveOverlay in App.tsx

**Files:**
- Modify: `webapp/src/App.tsx`

- [ ] **Step 1: Add the import and mount point**

In `webapp/src/App.tsx`, add the import at the top with the other UI imports:

```typescript
import { ShockwaveOverlay } from '@/components/ui/ShockwaveOverlay'
```

Then inside the `return` of `App()`, add `<ShockwaveOverlay />` as the first child of `QueryClientProvider`, before `<TopLoadingBar />`:

```tsx
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ShockwaveOverlay />
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
```

- [ ] **Step 2: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/App.tsx
git commit -m "feat: mount ShockwaveOverlay in App"
```

---

## Task 4: Trigger shockwave from LoginPage on success

**Files:**
- Modify: `webapp/src/pages/LoginPage.tsx`

- [ ] **Step 1: Wire the trigger**

In `webapp/src/pages/LoginPage.tsx`, add the store selector near the top of the component (after the existing `useAuthStore` line):

```typescript
const setLoginAnimating = useUiStore((s) => s.setLoginAnimating)
```

Add the `useUiStore` import if not present:
```typescript
import { useUiStore } from '@/store/uiStore'
```

Then find the `useEffect` that watches `token` and navigates:

```typescript
useEffect(() => {
  if (token) navigate('/', { replace: true })
}, [token, navigate])
```

Replace it with:

```typescript
useEffect(() => {
  if (token) {
    setLoginAnimating(true)
    navigate('/', { replace: true })
  }
}, [token, navigate, setLoginAnimating])
```

- [ ] **Step 2: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/pages/LoginPage.tsx
git commit -m "feat: trigger shockwave on login success"
```

---

## Task 5: Eclipse ripple on theme toggle in Sidebar

**Files:**
- Modify: `webapp/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add animate import**

At the top of `webapp/src/components/layout/Sidebar.tsx`, add to the animejs import (or add fresh if not present):

```typescript
import { animate } from 'animejs'
```

- [ ] **Step 2: Add refs and ripple handler inside the `Sidebar` function**

Add these right after the existing `const` declarations at the top of `Sidebar()`:

```typescript
const themeButtonRef = useRef<HTMLButtonElement>(null)
const rippleRef      = useRef<HTMLDivElement | null>(null)
const isRippling     = useRef(false)
```

Add the `useRef` import to the React import if not already there:
```typescript
import React, { useRef } from 'react'
```

- [ ] **Step 3: Add the handleThemeToggle function**

Add this function inside `Sidebar()`, before the `return`:

```typescript
const handleThemeToggle = () => {
  if (isRippling.current) return
  isRippling.current = true

  const btn    = themeButtonRef.current
  const rect   = btn?.getBoundingClientRect()
  const cx     = rect ? rect.left + rect.width  / 2 : window.innerWidth  / 2
  const cy     = rect ? rect.top  + rect.height / 2 : window.innerHeight / 2

  // Next theme determines ripple color
  const nextTheme  = theme === 'light' ? 'dark' : 'light'
  const rippleColor = nextTheme === 'dark' ? '#0a0a0a' : '#f5f5f5'

  // Create and mount overlay
  const overlay = document.createElement('div')
  overlay.style.cssText = `
    position: fixed;
    inset: 0;
    z-index: 9998;
    pointer-events: none;
    background: ${rippleColor};
    clip-path: circle(0% at ${cx}px ${cy}px);
    will-change: clip-path;
  `
  document.body.appendChild(overlay)
  rippleRef.current = overlay

  // Animate icon flip on the button
  if (btn) {
    animate(btn, {
      rotateY: [0, 360],
      duration: 600,
      ease: 'cubicBezier(0.4, 0, 0.2, 1)',
    })
  }

  // Expand ripple; swap theme at ~60% (360ms into 600ms)
  animate(overlay, {
    clipPath: [
      { to: `circle(0% at ${cx}px ${cy}px)` },
      { to: `circle(150% at ${cx}px ${cy}px)` },
    ],
    duration: 600,
    ease: 'cubicBezier(0.4, 0, 0.2, 1)',
    onUpdate: (anim) => {
      // Swap theme exactly once at 60% progress
      if (!overlay.dataset.swapped && anim.progress >= 60) {
        overlay.dataset.swapped = '1'
        toggleTheme()
      }
    },
    onComplete: () => {
      // Fade out overlay
      animate(overlay, {
        opacity: [1, 0],
        duration: 280,
        ease: 'cubicBezier(0.16, 1, 0.3, 1)',
        onComplete: () => {
          overlay.remove()
          rippleRef.current  = null
          isRippling.current = false
        },
      })
    },
  })
}
```

- [ ] **Step 4: Wire ref and handler to the theme buttons**

Find every theme toggle `<motion.button>` in the JSX. There are two — one in the expanded sidebar, one in the collapsed sidebar. Add `ref={themeButtonRef}` and replace `onClick={toggleTheme}` with `onClick={handleThemeToggle}` on **both**:

Expanded sidebar button (around line 263):
```tsx
<motion.button
  ref={themeButtonRef}
  onClick={handleThemeToggle}
  // ... rest unchanged
>
```

Collapsed sidebar button (around line 308):
```tsx
<motion.button
  onClick={handleThemeToggle}
  // ... rest unchanged
>
```

Note: `ref` only goes on the first (expanded) button. The collapsed one just gets the handler.

- [ ] **Step 5: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/components/layout/Sidebar.tsx
git commit -m "feat: eclipse ripple animation on theme toggle"
```

---

## Task 6: Build and push

- [ ] **Step 1: Full build**

```bash
cd webapp && npm run build
```

Expected: `✓ built in X.XXs` — zero TypeScript errors, zero Vite errors.

- [ ] **Step 2: Push to Railway**

```bash
git push vos-tool fix/railway-session-auth
```

Expected: Railway triggers a new build automatically.

---

## Self-Review Checklist

- [x] `loginAnimating` added to store and not persisted ✓
- [x] `ShockwaveOverlay` guards with `hasRun.current` — prevents double-fire on StrictMode ✓
- [x] `onUpdate` progress check uses `>= 60` (percentage 0–100) matching animejs v4 `progress` property ✓
- [x] Eclipse ripple uses `document.createElement` — no React state, no re-render, instant ✓
- [x] Both theme buttons (expanded + collapsed) get `handleThemeToggle` ✓
- [x] `isRippling` guard prevents double-clicks mid-animation ✓
- [x] All anime.js calls use v4 named export `animate()` — no default import ✓
- [x] `clip-path` string format matches what browsers accept: `circle(0% at Xpx Ypx)` ✓
