import React, { useRef } from 'react'
import { useAuthStore } from '@/store/authStore'
import { useUiStore, type NavTab } from '@/store/uiStore'
import { useUnreadCount } from '@/store/badgeStore'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Mic, Flag, PlayCircle, BookOpen, Settings, LogOut,
  ChevronLeft, ChevronRight, Sun, Moon,
} from 'lucide-react'
import { UsageCard } from './UsageCard'
import { useAuditStore } from '@/store/auditStore'
import { inferPhase } from '@/hooks/useAuditStream'
import { animate } from 'animejs'

interface NavItem { id: NavTab; label: string; icon: React.ReactElement; roles?: string[] }

const ALL_ITEMS: NavItem[] = [
  { id: 'Audit',             label: 'Audit',       icon: <Mic size={15} /> },
  { id: 'Actions',           label: 'Actions',     icon: <Flag size={15} /> },
  { id: 'Call Review',       label: 'Call Review', icon: <PlayCircle size={15} /> },
  { id: 'Dashboard',         label: 'Dashboard',   icon: <LayoutDashboard size={15} /> },
  { id: 'Phrase Management', label: 'Phrases',     icon: <BookOpen size={15} />, roles: ['Owner'] },
  { id: 'Settings',          label: 'Settings',    icon: <Settings size={15} />, roles: ['Owner', 'Admin'] },
]

/* Stagger container for nav items */
const navContainer = {
  hidden: {},
  show:   { transition: { staggerChildren: 0.045 } },
}
const navItemVariant = {
  hidden: { opacity: 0, x: -6 },
  show:   { opacity: 1, x: 0, transition: { duration: 0.28, ease: [0.16, 1, 0.3, 1] as any } },
}

export function Sidebar() {
  const { role, username, name, picture, clearAuth } = useAuthStore()
  const { activeTab, setActiveTab, sidebarCollapsed, setSidebarCollapsed, theme, toggleTheme } = useUiStore()
  const unreadCount = useUnreadCount()
  const { status, progress, analysisProgress, logs } = useAuditStore()
  const isAuditRunning = status === 'running'
  const auditPhase = inferPhase(logs)

  const auditPct = React.useMemo(() => {
    if (!isAuditRunning) return 0
    if (auditPhase === 'analyzing' && analysisProgress && analysisProgress.total > 0) {
      return Math.round((analysisProgress.completed / analysisProgress.total) * 100)
    }
    if (progress && progress.total > 0) {
      return Math.round((progress.downloaded / progress.total) * 100)
    }
    return 0
  }, [isAuditRunning, auditPhase, analysisProgress, progress])

  const themeButtonRef = useRef<HTMLButtonElement>(null)
  const rippleRef      = useRef<HTMLDivElement | null>(null)
  const isRippling     = useRef(false)

  const items = ALL_ITEMS.filter((i) => !i.roles || (role && i.roles.includes(role)))

  const handleThemeToggle = () => {
    if (isRippling.current) return
    isRippling.current = true

    const btn    = themeButtonRef.current
    const rect   = btn?.getBoundingClientRect()
    const cx     = rect ? rect.left + rect.width  / 2 : window.innerWidth  / 2
    const cy     = rect ? rect.top  + rect.height / 2 : window.innerHeight / 2

    const nextTheme   = theme === 'light' ? 'dark' : 'light'
    const rippleColor = nextTheme === 'dark' ? '#0a0a0a' : '#f5f5f5'

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

    if (btn) {
      animate(btn, {
        rotateY: [0, 360],
        duration: 600,
        ease: 'cubicBezier(0.4, 0, 0.2, 1)',
      })
    }

    // Swap theme at 60% of the 600ms animation = 360ms
    setTimeout(() => toggleTheme(), 360)

    animate(overlay, {
      clipPath: [
        { to: `circle(0% at ${cx}px ${cy}px)` },
        { to: `circle(150% at ${cx}px ${cy}px)` },
      ],
      duration: 600,
      ease: 'cubicBezier(0.4, 0, 0.2, 1)',
      onComplete: () => {
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

  return (
    <aside
      className={[
        'flex h-screen flex-col bg-[var(--surface-sidebar)] border-r border-[var(--b-strong)]',
        'shrink-0 transition-[width] duration-200',
        sidebarCollapsed ? 'w-[60px]' : 'w-[220px]',
      ].join(' ')}
    >
      {/* ── Header ── */}
      <div className={[
        'flex h-14 shrink-0 items-center border-b border-[var(--b-divider)]',
        sidebarCollapsed ? 'justify-center px-2' : 'justify-between px-4',
      ].join(' ')}>
        {/* V logo mark — always visible */}
        <div
          className="w-[26px] h-[26px] rounded-[4px] flex items-center justify-center shrink-0 select-none"
          style={{ background: 'var(--accent)', boxShadow: '0 0 0 1px rgba(0,0,0,0.08)' }}
        >
          <span
            className="text-[13px] font-black leading-none"
            style={{ color: theme === 'dark' ? '#000' : '#fff', letterSpacing: '-0.5px' }}
          >V</span>
        </div>

        <AnimatePresence mode="wait">
          {!sidebarCollapsed && (
            <motion.span
              key="logo"
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -4 }}
              transition={{ duration: 0.18 }}
              className="font-bold text-[15px] tracking-[-0.5px] select-none flex-1 ml-2"
              style={{ color: 'var(--accent)' }}
            >
              VOS
            </motion.span>
          )}
        </AnimatePresence>

        <motion.button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          whileHover={{ scale: 1.12 }}
          whileTap={{ scale: 0.92 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          className="flex h-7 w-7 items-center justify-center rounded text-t-muted hover:text-t-primary hover:bg-[var(--hover-overlay)] transition-colors"
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <motion.span
            animate={{ rotate: sidebarCollapsed ? 0 : 180 }}
            transition={{ type: 'spring', stiffness: 300, damping: 24 }}
            style={{ display: 'flex' }}
          >
            <ChevronRight size={14} />
          </motion.span>
        </motion.button>
      </div>

      {/* ── Nav ── */}
      <nav className="flex-1 min-h-0 overflow-y-auto custom-scrollbar py-2 px-2">
        <motion.div
          className="space-y-px"
          variants={navContainer}
          initial="hidden"
          animate="show"
        >
          {items.map((item) => {
            const isActive = activeTab === item.id
            const badge = item.id === 'Actions' && !isActive && unreadCount > 0 ? unreadCount : undefined

            return (
              <motion.div key={item.id} variants={navItemVariant}>
                <motion.button
                  onClick={() => setActiveTab(item.id)}
                  title={sidebarCollapsed ? item.label : undefined}
                  whileTap={{ scale: 0.97 }}
                  className={[
                    'group relative flex w-full items-center gap-2.5 rounded-md px-2.5 py-2',
                    'text-[13px] font-medium transition-colors duration-150',
                    isActive
                      ? ''
                      : 'text-t-muted hover:bg-[var(--hover-overlay)] hover:text-t-primary',
                    sidebarCollapsed ? 'justify-center' : '',
                  ].join(' ')}
                  style={isActive ? {
                    backgroundColor: 'var(--accent-muted)',
                    color:           'var(--accent-text)',
                    /* Glow — light mode: ink shadow, dark mode: white glow */
                    boxShadow:       theme === 'dark'
                      ? '0 0 0 1px rgba(237,237,237,0.08), 0 2px 12px rgba(180,160,255,0.12)'
                      : '0 0 0 1px rgba(15,17,23,0.08), 0 2px 8px rgba(0,0,0,0.06)',
                  } : {}}
                >
                  {/* Active left-bar indicator */}
                  {isActive && (
                    <motion.div
                      layoutId="activeNav"
                      className="absolute left-0 top-[20%] bottom-[20%] w-[2px] rounded-r-full"
                      style={{ backgroundColor: 'var(--accent)' }}
                      transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                    />
                  )}

                  {/* Icon with hover micro-animation */}
                  <motion.span
                    className="shrink-0"
                    style={isActive ? { color: 'var(--accent)' } : {}}
                    whileHover={{ scale: 1.18, rotate: isActive ? 0 : 8 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 18 }}
                  >
                    {React.cloneElement(item.icon as any, { size: 15 })}
                  </motion.span>

                  {!sidebarCollapsed && (
                    <span className="flex-1 text-left font-semibold">{item.label}</span>
                  )}

                  {!sidebarCollapsed && badge !== undefined && (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: 'spring', stiffness: 500, damping: 20 }}
                      className="rounded-full bg-[var(--ship-red)]/10 text-[var(--ship-red)] px-1.5 py-0.5 text-[10px] font-semibold leading-none"
                    >
                      {badge}
                    </motion.span>
                  )}
                </motion.button>
              </motion.div>
            )
          })}
        </motion.div>
        
        {/* Audit Progress in Sidebar */}
        <AnimatePresence>
          {isAuditRunning && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="mt-6 mx-2 p-3 rounded-lg bg-surface-card border border-b-subtle shadow-sm overflow-hidden"
            >
              {!sidebarCollapsed ? (
                <>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-black uppercase tracking-widest text-accent">
                      {auditPhase === 'analyzing' ? 'Analyzing' : 'Downloading'}
                    </span>
                    <span className="text-[10px] font-bold tabular-nums text-t-muted">
                      {auditPct}%
                    </span>
                  </div>
                  <div className="h-1 w-full bg-surface-soft rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-accent"
                      initial={{ width: 0 }}
                      animate={{ width: `${auditPct}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                </>
              ) : (
                <div className="flex justify-center">
                  <div className="relative h-6 w-6">
                    <svg className="h-full w-full" viewBox="0 0 24 24">
                      <circle
                        className="text-surface-soft stroke-current"
                        strokeWidth="3"
                        fill="transparent"
                        r="10"
                        cx="12"
                        cy="12"
                      />
                      <motion.circle
                        className="text-accent stroke-current"
                        strokeWidth="3"
                        strokeLinecap="round"
                        fill="transparent"
                        r="10"
                        cx="12"
                        cy="12"
                        initial={{ strokeDasharray: "62.83", strokeDashoffset: "62.83" }}
                        animate={{ strokeDashoffset: 62.83 - (62.83 * auditPct) / 100 }}
                        transition={{ duration: 0.5 }}
                      />
                    </svg>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* ── Bottom ── */}
      <div className="shrink-0 border-t border-[var(--b-divider)]">
        <div className={sidebarCollapsed ? 'flex justify-center py-2 px-2' : 'px-2 pt-2'}>
          <UsageCard />
        </div>

        <div className="p-2 space-y-px">
          {!sidebarCollapsed ? (
            <>
              {/* Profile row */}
              <div className="flex items-center gap-2.5 px-2 py-2 rounded-md shadow-[var(--shadow-border)] bg-surface-card mb-1">
                <div className="h-7 w-7 shrink-0 rounded-full bg-[var(--surface-soft)] overflow-hidden flex items-center justify-center shadow-[var(--shadow-ring)]">
                  {picture
                    ? <img src={picture} alt={name || 'User'} className="h-full w-full object-cover" />
                    : <span className="text-[11px] font-semibold text-t-primary">{(name || username || 'U').charAt(0).toUpperCase()}</span>
                  }
                </div>
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-[12px] font-semibold text-t-primary truncate leading-tight">{name || 'User Account'}</span>
                  <span className="text-[11px] text-t-muted truncate">{username}</span>
                </div>
              </div>

              {/* Theme toggle */}
              <motion.button
                ref={themeButtonRef}
                onClick={handleThemeToggle}
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.97 }}
                transition={{ type: 'spring', stiffness: 400, damping: 22 }}
                className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium text-t-muted hover:text-t-primary hover:bg-[var(--hover-overlay)] transition-colors"
              >
                <motion.span
                  whileHover={{ rotate: 20, scale: 1.15 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                  style={{ display: 'flex' }}
                >
                  {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
                </motion.span>
                <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
              </motion.button>

              {/* Sign out */}
              <motion.button
                onClick={clearAuth}
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.97 }}
                transition={{ type: 'spring', stiffness: 400, damping: 22 }}
                className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium text-t-muted hover:text-[var(--semantic-error)] hover:bg-[var(--semantic-error)]/5 transition-colors"
              >
                <motion.span
                  whileHover={{ x: -3, scale: 1.1 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 18 }}
                  style={{ display: 'flex' }}
                >
                  <LogOut size={14} />
                </motion.span>
                <span>Sign out</span>
              </motion.button>
            </>
          ) : (
            /* Collapsed icons */
            <div className="flex flex-col items-center gap-2 py-1">
              <div className="h-7 w-7 rounded-full bg-[var(--surface-soft)] overflow-hidden flex items-center justify-center shadow-[var(--shadow-ring)]">
                {picture
                  ? <img src={picture} alt="User" className="h-full w-full object-cover" />
                  : <span className="text-[11px] font-semibold text-t-primary">{(name || username || 'U').charAt(0).toUpperCase()}</span>
                }
              </div>

              <motion.button
                onClick={handleThemeToggle}
                whileHover={{ scale: 1.15, rotate: 20 }}
                whileTap={{ scale: 0.92 }}
                transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                title={theme === 'light' ? 'Dark mode' : 'Light mode'}
                className="p-1.5 rounded text-t-muted hover:text-t-primary hover:bg-[var(--hover-overlay)] transition-colors"
              >
                {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
              </motion.button>

              <motion.button
                onClick={clearAuth}
                whileHover={{ scale: 1.15, x: -2 }}
                whileTap={{ scale: 0.92 }}
                transition={{ type: 'spring', stiffness: 500, damping: 18 }}
                title="Sign out"
                className="p-1.5 rounded text-t-muted hover:text-[var(--semantic-error)] hover:bg-[var(--semantic-error)]/5 transition-colors"
              >
                <LogOut size={14} />
              </motion.button>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
