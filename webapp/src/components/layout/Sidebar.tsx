import React from 'react'
import { useAuthStore } from '@/store/authStore'
import { useUiStore, type NavTab } from '@/store/uiStore'
import { useUnreadCount } from '@/store/badgeStore'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Mic, Flag, PlayCircle, BookOpen, Settings, LogOut,
  ChevronLeft, ChevronRight, Sun, Moon,
} from 'lucide-react'
import { UsageCard } from './UsageCard'

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
  show:   { opacity: 1, x: 0, transition: { duration: 0.28, ease: [0.16, 1, 0.3, 1] } },
}

export function Sidebar() {
  const { role, username, name, picture, clearAuth } = useAuthStore()
  const { activeTab, setActiveTab, sidebarCollapsed, setSidebarCollapsed, theme, toggleTheme } = useUiStore()
  const unreadCount = useUnreadCount()

  const items = ALL_ITEMS.filter((i) => !i.roles || (role && i.roles.includes(role)))

  return (
    <aside
      className={[
        'flex h-screen flex-col bg-surface-page border-r border-[var(--b-divider)]',
        'shrink-0 transition-[width] duration-200',
        sidebarCollapsed ? 'w-[60px]' : 'w-[220px]',
      ].join(' ')}
    >
      {/* ── Header ── */}
      <div className={[
        'flex h-14 shrink-0 items-center border-b border-[var(--b-divider)]',
        sidebarCollapsed ? 'justify-center px-2' : 'justify-between px-4',
      ].join(' ')}>
        <AnimatePresence mode="wait">
          {!sidebarCollapsed && (
            <motion.span
              key="logo"
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -4 }}
              transition={{ duration: 0.18 }}
              className="font-bold text-[16px] tracking-[-0.5px] select-none"
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
                    {React.cloneElement(item.icon, { size: 15 })}
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
                onClick={toggleTheme}
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
                onClick={toggleTheme}
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
