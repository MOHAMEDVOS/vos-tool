import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { readymodeApi, DISPOSITIONS, DURATION_FILTERS, type DownloadRequest } from '@/api/readymode'
import { Info, Link2, Copy, Check, X } from 'lucide-react'
import { LiveCountUp } from '@/components/ui/LiveCountUp'
import { Spinner } from '@/components/ui/Spinner'
import { useAuthStore } from '@/store/authStore'
import { ChevronDown, Settings2, Square } from 'lucide-react'
import { CustomDatePicker } from '@/components/ui/DatePicker'
import { CustomSelect } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'
import { useAuditStore } from '@/store/auditStore'
import { useQuotaStore } from '@/store/quotaStore'
import { 
  inferPhase, 
  type StreamStatus, 
  type ProgressState, 
  type AnalysisProgress, 
  type DoneResult, 
  type LogLine 
} from '@/hooks/useAuditStream'

type AuditSection = 'agent' | 'campaign'
function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function localISO(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

/* â”€â”€â”€ Motion Variants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.3, staggerChildren: 0.05 } },
  exit: { opacity: 0, transition: { duration: 0.2 } },
}
const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
}

/* â”€â”€â”€ Shared class helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const inputBase: React.CSSProperties = {
  width: '100%',
  backgroundColor: 'var(--c-base)',
  border: '1px solid var(--b-subtle)',
  color: 'var(--t-primary)',
}

/* â”€â”€â”€ Multi-select Dropdown â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
function MultiSelectDropdown({
  options,
  selected,
  onChange,
  placeholder = 'Choose options',
  disabled,
}: {
  options: string[]
  selected: string[]
  onChange: (val: string[]) => void
  placeholder?: string
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({})
  const triggerRef = useRef<HTMLButtonElement>(null)
  const ref = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (
        ref.current && !ref.current.contains(e.target as Node) &&
        triggerRef.current && !triggerRef.current.contains(e.target as Node)
      ) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  useEffect(() => {
    if (open) {
      setSearch('')
      setTimeout(() => inputRef.current?.focus(), 100)
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect()
        setDropdownStyle({
          position: 'fixed',
          top: rect.bottom + 6,
          left: rect.left,
          width: Math.max(rect.width, 300),
          zIndex: 9999,
        })
      }
    }
  }, [open])

  const toggle = (val: string) => {
    const next = selected.includes(val) ? selected.filter((s) => s !== val) : [...selected, val]
    onChange(next)
  }

  const allSelected = selected.length === options.length && options.length > 0
  const toggleAll = () => onChange(allSelected ? [] : [...options])
  const filteredOptions = options.filter(opt => opt.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="relative w-full">
      <motion.button
        ref={triggerRef}
        whileTap={{ scale: 0.995 }}
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        style={{ backgroundColor: 'var(--c-base)', borderColor: 'var(--b-subtle)' }}
        className="flex w-full min-h-[38px] items-center justify-between rounded-md border px-3 py-1.5 text-sm shadow-inner outline-none transition-all disabled:opacity-50"
      >
        <div className="flex flex-1 flex-wrap gap-1.5 overflow-hidden mr-2">
          {selected.length === 0 ? (
            <span style={{ color: 'var(--t-muted)' }}>{placeholder}</span>
          ) : (
            selected.map((val) => (
              <span
                key={val}
                style={{ backgroundColor: 'var(--active-overlay)', color: 'var(--t-primary)' }}
                className="flex items-center gap-1 rounded pl-2 pr-1 py-0.5 text-[10px] font-black uppercase tracking-widest whitespace-nowrap transition-colors"
              >
                {val}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); toggle(val) }}
                  className="flex items-center justify-center h-3 w-3 rounded-sm transition-colors"
                  style={{ color: 'var(--t-muted)' }}
                >
                  <X size={8} strokeWidth={3} />
                </button>
              </span>
            ))
          )}
        </div>
        <ChevronDown
          size={14}
          className={`shrink-0 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
          style={{ color: 'var(--t-muted)' }}
        />
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={ref}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            style={{ ...dropdownStyle, borderColor: 'rgba(255,255,255,0.12)', backgroundColor: '#1e1e1e' }}
            className="rounded-xl border-2 p-2 flex flex-col gap-0.5"
          >
            <div className="px-1 pt-1 pb-2" style={{ borderBottom: '1px solid var(--b-divider)' }}>
              <input
                ref={inputRef}
                type="text"
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ backgroundColor: '#2a2a2a', borderColor: 'rgba(255,255,255,0.1)', color: '#ededed' }}
                className="w-full border rounded px-2 py-1.5 text-xs outline-none transition-colors"
              />
            </div>

            <div className="max-h-72 overflow-y-auto custom-scrollbar flex flex-col gap-0.5 py-1">
              {/* Select all */}
              <label
                style={{ color: 'var(--t-primary)' }}
                className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold hover:bg-c-raised transition-colors select-none"
              >
                <div
                  style={{
                    borderColor: allSelected ? 'var(--selected-check)' : 'var(--b-strong)',
                    backgroundColor: allSelected ? 'var(--selected-check)' : 'var(--c-raised)',
                  }}
                  className="relative flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border transition-all"
                >
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} className="peer absolute h-full w-full opacity-0 cursor-pointer" />
                  {allSelected && (
                    <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
                      <path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                </div>
                Select all
              </label>
              <div className="my-1 h-px mx-2" style={{ backgroundColor: 'var(--b-divider)' }} />

              {filteredOptions.length === 0 ? (
                <div className="px-2.5 py-3 text-xs text-center" style={{ color: 'var(--t-muted)' }}>No matches found</div>
              ) : (
                filteredOptions.map((opt) => {
                  const isChecked = selected.includes(opt)
                  return (
                    <label
                      key={opt}
                      style={{
                        color: isChecked ? 'var(--t-primary)' : 'var(--t-label)',
                        backgroundColor: isChecked ? 'rgba(255,255,255,0.06)' : undefined,
                      }}
                      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm hover:bg-c-raised transition-colors select-none"
                    >
                      <div
                        style={{
                          borderColor: isChecked ? 'var(--selected-check)' : 'var(--b-strong)',
                          backgroundColor: isChecked ? 'var(--selected-check)' : 'var(--c-raised)',
                        }}
                        className="relative flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border transition-all"
                      >
                        <input type="checkbox" checked={isChecked} onChange={() => toggle(opt)} className="peer absolute h-full w-full opacity-0 cursor-pointer" />
                        {isChecked && (
                          <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
                            <path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        )}
                      </div>
                      {opt}
                    </label>
                  )
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* â”€â”€â”€ Custom Date Picker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

/* â”€â”€â”€ Number Stepper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
function NumberStepper({
  value,
  onChange,
  min = 1,
  max = 2000,
  disabled,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  disabled?: boolean
}) {
  const [raw, setRaw] = React.useState(String(value))

  // Keep raw in sync when value changes externally (e.g. stepper buttons)
  React.useEffect(() => { setRaw(String(value)) }, [value])

  const commit = (str: string) => {
    const n = parseInt(str, 10)
    if (!isNaN(n)) onChange(Math.min(max, Math.max(min, n)))
    else setRaw(String(value)) // restore if empty/invalid on blur
  }

  return (
    <div
      style={{ backgroundColor: 'var(--c-base)', borderColor: 'var(--b-subtle)' }}
      className="inline-flex h-[38px] items-center rounded-md border overflow-hidden shadow-inner transition-all focus-within:border-b-strong"
    >
      <input
        type="text"
        inputMode="numeric"
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') commit(raw) }}
        disabled={disabled}
        style={{ color: 'var(--t-primary)', backgroundColor: 'transparent', width: '72px' }}
        className="px-3 py-1.5 text-sm font-medium outline-none disabled:opacity-50 shrink-0"
      />
      <div style={{ borderLeft: '1px solid var(--b-subtle)', backgroundColor: 'var(--c-raised)' }} className="flex h-full">
        <button
          type="button"
          disabled={disabled || value <= min}
          onClick={() => onChange(Math.max(min, value - 1))}
          style={{ color: 'var(--t-muted)' }}
          className="flex w-10 items-center justify-center text-lg hover:text-t-primary hover:bg-c-raised transition-colors disabled:opacity-20"
        >-</button>
        <div style={{ width: 1, backgroundColor: 'var(--b-subtle)' }} />
        <button
          type="button"
          disabled={disabled || value >= max}
          onClick={() => onChange(Math.min(max, value + 1))}
          style={{ color: 'var(--t-muted)' }}
          className="flex w-10 items-center justify-center text-lg hover:text-t-primary hover:bg-c-raised transition-colors disabled:opacity-20"
        >+</button>
      </div>
    </div>
  )
}

/* â”€â”€â”€ Main Page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
export function AuditPage() {
  const role = useAuthStore((s) => s.role)
  const isAuditor = role === 'Auditor'

  const sections: { id: AuditSection; label: string }[] = isAuditor
    ? []
    : [
        { id: 'agent', label: 'Agent Audit' },
        { id: 'campaign', label: 'Campaign Audit' },
      ]

  const [activeSection, setActiveSection] = useState<AuditSection>('agent')

  return (
    <div className="flex flex-col gap-6 pb-12 w-full max-w-[1400px]">
      {/* Tab bar */}
      {!isAuditor && sections.length > 1 && (
        <div
          style={{ backgroundColor: 'var(--c-raised)', borderColor: 'var(--b-subtle)' }}
          className="grid grid-cols-2 p-1 rounded-lg w-full border"
        >
          {sections.map((s) => {
            const isActive = activeSection === s.id
            return (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                style={{ color: isActive ? 'var(--t-primary)' : 'var(--t-muted)' }}
                className="relative py-2.5 rounded text-sm font-bold tracking-tight transition-colors"
              >
                {isActive && (
                  <motion.div
                    layoutId="activeTabPill"
                    style={{ backgroundColor: 'var(--active-overlay)' }}
                    className="absolute inset-0 rounded shadow-lg"
                    transition={{ type: 'spring', bounce: 0.1, duration: 0.4 }}
                  />
                )}
                <span className="relative z-10">{s.label}</span>
              </button>
            )
          })}
        </div>
      )}

      <motion.div
        key={activeSection}
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="w-full"
      >
        {(isAuditor || activeSection === 'agent') && <ReadyModeAuditForm mode="agent" />}
        {!isAuditor && activeSection === 'campaign' && <ReadyModeAuditForm mode="campaign" />}
      </motion.div>
    </div>
  )
}

/* â”€â”€â”€ Phase message banks (50+ messages, shuffled randomly) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const PHASE_MESSAGES = {
  login: [
    'Sneaking into the dialer...',
    'Picking the digital lock...',
    'Knocking on ReadyMode\'s door...',
    'Flashing the credentials...',
    'Bribing the gatekeepers...',
    'Convincing the server we\'re legit...',
    'Whispering the secret password...',
    'Handshaking with the dialer...',
    'Getting past the bouncer...',
    'Logging in like a boss...',
  ],
  collecting: [
    'Rounding up the suspects...',
    'Hunting for calls in the wild...',
    'Dragging recordings out of hiding...',
    'Collecting evidence...',
    'Fishing for calls...',
    'Sweeping the call database...',
    'Gathering the specimens...',
    'Counting every single call...',
    'Pulling files from the vault...',
    'Bagging and tagging recordings...',
  ],
  analyzing: [
    'Interrogating the recordings...',
    'Hunting for slackers...',
    'Sniffing out bad rebuttals...',
    'Exposing the rebuttalists...',
    'Putting calls under the microscope...',
    'Finding who skipped the hello...',
    'Catching agents red-handed...',
    'Listening so you don\'t have to...',
    'Separating stars from disasters...',
    'Scoring the performances...',
    'Naming and shaming...',
    'Running the quality gauntlet...',
    'Detecting the art of the dodge...',
    'Flagging the suspicious ones...',
    'AI is judging your agents now...',
  ],
  idle: [
    'Warming up the engines...',
    'Booting up the audit machine...',
    'Preparing for takeoff...',
    'Loading the QA cannon...',
    'Assembling the team...',
  ],
}

function useRotatingMessage(phase: keyof typeof PHASE_MESSAGES, isRunning: boolean) {
  const [index, setIndex] = useState(0)
  const [shuffled, setShuffled] = useState<string[]>([])

  useEffect(() => {
    const msgs = [...PHASE_MESSAGES[phase]]
    for (let i = msgs.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [msgs[i], msgs[j]] = [msgs[j], msgs[i]]
    }
    setShuffled(msgs)
    setIndex(0)
  }, [phase])

  useEffect(() => {
    if (!isRunning) return
    const id = setInterval(() => setIndex(i => (i + 1) % (shuffled.length || 1)), 3200)
    return () => clearInterval(id)
  }, [isRunning, shuffled.length])

  return shuffled[index] ?? PHASE_MESSAGES[phase][0]
}

/* â”€â”€â”€ Premium Audit Progress Bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
function AuditProgressBar({
  status,
  progress,
  analysisProgress,
  result,
  error,
  logs,
  maxCalls,
  onCancel,
  onReset,
}: {
  status: StreamStatus
  progress: ProgressState | null
  analysisProgress: AnalysisProgress | null
  result: DoneResult | null
  error: string | null
  logs: LogLine[]
  maxCalls: number
  onCancel: () => void
  onReset: () => void
}) {
  const isRunning = status === 'running'
  const isDone = status === 'done'
  const isCancelled = status === 'cancelled'
  const isError = status === 'error'

  const phase = inferPhase(logs)
  const message = useRotatingMessage(phase, isRunning)

  // Progress percentage — real if we have progress data, animated if not
  const pct = useMemo(() => {
    if (isDone) return 100
    if (phase === 'analyzing') {
      if (!analysisProgress) return 0 // Reset to 0 when analysis starts
      if (analysisProgress.total === 0) return 0
      return Math.min(100, Math.round((analysisProgress.completed / analysisProgress.total) * 100))
    }
    if (!progress) return isRunning ? null : 0  // null = indeterminate
    if (progress.total === 0) return 0
    return Math.min(100, Math.round((progress.downloaded / progress.total) * 100))
  }, [progress, analysisProgress, phase, isDone, isRunning])

  const phaseLabel: Record<typeof phase, string> = {
    idle: 'Initializing',
    login: 'Logging In',
    collecting: 'Collecting Calls',
    analyzing: 'Analyzing Calls',
  }

  const accentColor = isError
    ? '#f87171'
    : isCancelled
    ? '#f59e0b'
    : isDone
    ? '#4ade80'
    : '#60a5fa'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      transition={{ duration: 0.3 }}
      className="mt-6 rounded-2xl border overflow-hidden"
      style={{ borderColor: 'var(--b-medium)', backgroundColor: 'var(--c-raised)' }}
    >
      <div className="px-6 pt-6 pb-5 flex flex-col gap-4">

        {/* Top row — phase badge + counter */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {isRunning && (
              <span
                className="h-2 w-2 rounded-full animate-pulse"
                style={{ backgroundColor: accentColor }}
              />
            )}
            <span
              className="text-[10px] font-black uppercase tracking-[0.15em]"
              style={{ color: isRunning ? accentColor : 'var(--t-muted)' }}
            >
              {isDone
                ? 'Audit Complete'
                : isCancelled
                ? 'Cancelled'
                : isError
                ? 'Failed'
                : phaseLabel[phase]}
            </span>
          </div>

          {/* X / Total counter */}
          {(isRunning || isDone) && (phase === 'analyzing' ? analysisProgress : progress) && (
            <span className="text-xs font-bold tabular-nums" style={{ color: 'var(--t-label)' }}>
              <span style={{ color: accentColor }}>
                <LiveCountUp value={
                  isDone 
                    ? (phase === 'analyzing' ? analysisProgress?.total ?? 0 : progress?.total ?? 0) 
                    : (phase === 'analyzing' ? analysisProgress?.completed ?? 0 : progress?.downloaded ?? 0)
                } />
              </span>
              <span style={{ color: 'var(--t-muted)' }}> / {phase === 'analyzing' ? analysisProgress?.total : progress?.total}</span>
              <span className="ml-1.5 text-[10px] uppercase tracking-wider" style={{ color: 'var(--t-muted)' }}>
                {phase === 'analyzing' ? 'analyzed' : logs.some(l => l.stage === 'DOWNLOAD') ? 'downloaded' : 'collected'}
              </span>
            </span>
          )}
          {isRunning && !progress && (
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--t-muted)' }}>
              0 / {maxCalls} calls
            </span>
          )}
          {isDone && result && !progress && (
            <span className="text-xs font-bold" style={{ color: accentColor }}>
              {result.downloaded} downloaded آ· {result.analyzed} analyzed
            </span>
          )}
        </div>

        {/* Status message */}
        <AnimatePresence mode="wait">
          <motion.p
            key={isDone ? 'done' : isCancelled ? 'cancelled' : isError ? 'error' : message}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.4 }}
            className="text-sm font-medium leading-snug"
            style={{ color: isRunning ? 'var(--t-primary)' : 'var(--t-muted)', minHeight: 20 }}
          >
            {isDone
              ? result?.message ?? 'All done!'
              : isCancelled
              ? 'Audit was cancelled.'
              : isError
              ? (error ?? 'Something went wrong.')
              : message}
          </motion.p>
        </AnimatePresence>

        {/* Progress bar */}
        <div
          className="relative h-2 w-full rounded-full overflow-hidden"
          style={{ backgroundColor: 'var(--c-deep, #1a1a1f)' }}
        >
          {/* Indeterminate shimmer when no real progress yet */}
          {isRunning && pct === null && (
            <motion.div
              className="absolute inset-y-0 left-0 rounded-full"
              style={{
                width: '40%',
                background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
              }}
              animate={{ x: ['-100%', '350%'] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}

          {/* Determinate fill */}
          {pct !== null && (
            <motion.div
              className="absolute inset-y-0 left-0 rounded-full"
              style={{
                background: isDone
                  ? `linear-gradient(90deg, #22c55e, #4ade80)`
                  : isError
                  ? `linear-gradient(90deg, #dc2626, #f87171)`
                  : isCancelled
                  ? `linear-gradient(90deg, #b45309, #f59e0b)`
                  : `linear-gradient(90deg, #2563eb, ${accentColor})`,
                boxShadow: `0 0 8px ${accentColor}66`,
              }}
              initial={{ width: '0%' }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          )}
        </div>

        {/* Percentage label */}
        <div className="flex items-center justify-between -mt-2">
          <span className="text-[10px] font-bold tabular-nums" style={{ color: 'var(--t-muted)' }}>
            {pct !== null ? `${pct}%` : '—'}
          </span>
          {isRunning && (
            <button
              onClick={onCancel}
              className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest transition-opacity hover:opacity-70"
              style={{ color: '#f87171' }}
            >
              <Square size={8} fill="currentColor" />
              Cancel
            </button>
          )}
          {!isRunning && (status === 'done' || status === 'cancelled' || status === 'error') && (
            <button
              onClick={onReset}
              className="text-[10px] font-black uppercase tracking-widest transition-opacity hover:opacity-70"
              style={{ color: 'var(--t-muted)' }}
            >
              Clear
            </button>
          )}
        </div>

        {/* Done result breakdown */}
        <AnimatePresence>
          {isDone && result && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="flex items-center gap-3 pt-2 border-t"
              style={{ borderColor: 'var(--b-divider)' }}
            >
              <div className="flex items-center gap-1.5">
                <div className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: '#4ade80' }} />
                <span className="text-xs font-bold" style={{ color: '#4ade80' }}>{result.downloaded} downloaded</span>
              </div>
              <div className="h-3 w-px" style={{ backgroundColor: 'var(--b-divider)' }} />
              <div className="flex items-center gap-1.5">
                <div className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: '#60a5fa' }} />
                <span className="text-xs font-bold" style={{ color: '#60a5fa' }}>{result.analyzed} analyzed</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

/* ────────────────────────────────────────────────────────────────────────────── */
function ReadyModeAuditForm({ mode }: { mode: 'agent' | 'campaign' }) {
  const token = useAuthStore((s) => s.token)
  const [dialerUrl, setDialerUrl] = useState('https://resva.readymode.com/')
  const [identifier, setIdentifier] = useState(mode === 'agent' ? 'All users' : '')
  const [maxCalls, setMaxCalls] = useState(500)
  const [startDate, setStartDate] = useState(todayISO())
  const [endDate, setEndDate] = useState(todayISO())
  const [dispositions, setDispositions] = useState<string[]>([])
  const [durationFilter, setDurationFilter] = useState('all')
  const [customDuration, setCustomDuration] = useState(60)
  const isCampaign = mode === 'campaign'

  const { data: rmStatus } = useQuery({
    queryKey: ['readymode-status'],
    queryFn: readymodeApi.status,
    retry: false,
  })

  const { 
    status, logs, result, error, progress, analysisProgress, 
    start, cancel, reset 
  } = useAuditStore()
  const isRunning = status === 'running'
  const fetchUsage = useQuotaStore((s) => s.fetchUsage)

  useEffect(() => {
    if (status === 'done') fetchUsage()
  }, [status, fetchUsage])

  const buildBody = useCallback((auditType: 'heavy' | 'lite'): DownloadRequest => {
    const body: DownloadRequest = {
      dialer_url: dialerUrl,
      agent_name: isCampaign ? 'All users' : identifier.trim(),
      campaign_name: isCampaign ? identifier.trim() : undefined,
      max_calls: maxCalls,
      start_date: startDate,
      end_date: endDate,
      dispositions,
      duration_filter: durationFilter,
      audit_type: auditType,
    }
    if (durationFilter === 'gt_custom' || durationFilter === 'lt_custom')
      body.custom_duration_seconds = customDuration
    return body
  }, [dialerUrl, isCampaign, identifier, maxCalls, startDate, endDate, dispositions, durationFilter, customDuration])

  const notConfigured = rmStatus?.status === 'not_configured'
  const needsCustomDuration = durationFilter === 'gt_custom' || durationFilter === 'lt_custom'
  const identifierMissing = !identifier.trim()
  const disabled = notConfigured || identifierMissing || isRunning

  const labelClass = 'text-[10px] font-black uppercase tracking-[0.1em] mb-2 block'
  const sectionHeaderClass = 'text-xl font-black mb-4 tracking-tight'

  const showForm = status === 'idle'

  return (
    <div className="flex flex-col gap-8 w-full">
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="flex flex-col gap-8 w-full"
      >
        {/* Warning banner */}
        {notConfigured && (
          <motion.div variants={itemVariants} className="rounded-lg border border-semantic-warning/30 bg-semantic-warning/10 px-4 py-3 text-sm text-semantic-warning flex items-center gap-2">
            <Settings2 size={16} className="text-semantic-warning shrink-0" />
            ReadyMode credentials are not configured. Please contact the owner to set them up.
          </motion.div>
        )}

        {/* Row 1 — Config + Dates (always visible) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
          <motion.section variants={itemVariants}>
            <h2 className={sectionHeaderClass} style={{ color: 'var(--t-primary)' }}>
              {isCampaign ? 'Campaign Configuration' : 'Agent Configuration'}
            </h2>
            <div className="flex flex-col gap-4">
              <div>
                <label className={labelClass} style={{ color: 'var(--t-label)' }}>ReadyMode URL</label>
                <input
                  type="text"
                  value={dialerUrl}
                  onChange={(e) => setDialerUrl(e.target.value)}
                  placeholder="https://resva.readymode.com/"
                  disabled={isRunning}
                  style={{ ...inputBase, borderRadius: 6, padding: '6px 12px', fontSize: 14, outline: 'none' }}
                  className="w-full rounded-md border px-3 py-1.5 text-sm shadow-inner transition-all focus:ring-2 focus:ring-[rgba(0,102,204,0.2)] disabled:opacity-50"
                />
              </div>
              <div>
                <label className={labelClass} style={{ color: 'var(--t-label)' }}>{isCampaign ? 'Campaign Identifier' : 'Agent Identifier'}</label>
                <input
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder={isCampaign ? 'Enter exact campaign name' : 'All users'}
                  disabled={isRunning}
                  style={{ ...inputBase, borderRadius: 6, padding: '6px 12px', fontSize: 14, outline: 'none' }}
                  className="w-full rounded-md border px-3 py-1.5 text-sm shadow-inner transition-all focus:ring-2 focus:ring-[rgba(0,102,204,0.2)] disabled:opacity-50"
                />
              </div>
            </div>
          </motion.section>

          <motion.section variants={itemVariants}>
            <h2 className={`${sectionHeaderClass} lowercase`} style={{ color: 'var(--t-primary)' }}>Date parameters</h2>
            <div className="flex flex-col gap-4 w-full">
              <div>
                <label className={labelClass} style={{ color: 'var(--t-label)' }}>Start Date</label>
                <CustomDatePicker value={startDate} onChange={setStartDate} disabled={isRunning} />
              </div>
              <div>
                <label className={labelClass} style={{ color: 'var(--t-label)' }}>End Date</label>
                <CustomDatePicker value={endDate} onChange={setEndDate} disabled={isRunning} />
              </div>
            </div>
          </motion.section>
        </div>

        {/* Row 2 — Advanced Filter (always visible) */}
        <motion.section variants={itemVariants}>
          <div className="flex items-center gap-2 mb-4 w-full">
            <h2 className="text-3xl font-black tracking-tighter" style={{ color: 'var(--t-primary)' }}>Advanced Filter</h2>
            <Link2 size={18} style={{ color: 'var(--t-muted)' }} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-4">
            <div>
              <label className={labelClass} style={{ color: 'var(--t-label)' }}>Call Dispositions</label>
              <MultiSelectDropdown
                options={DISPOSITIONS}
                selected={dispositions}
                onChange={setDispositions}
                placeholder="Choose options"
                disabled={isRunning}
              />
            </div>
            <div>
              <label className={labelClass} style={{ color: 'var(--t-label)' }}>Duration Filter</label>
              <CustomSelect
                options={DURATION_FILTERS}
                value={durationFilter}
                onChange={setDurationFilter}
                disabled={isRunning}
                placeholder="Select duration..."
              />
              {needsCustomDuration && (
                <motion.input
                  initial={{ opacity: 0, height: 0, marginTop: 0 }}
                  animate={{ opacity: 1, height: 'auto', marginTop: 8 }}
                  type="number"
                  min={1}
                  value={customDuration}
                  onChange={(e) => setCustomDuration(Number(e.target.value))}
                  disabled={isRunning}
                  placeholder="Seconds"
                  style={{ ...inputBase, borderRadius: 6, padding: '6px 12px', fontSize: 14, outline: 'none' }}
                  className="w-full rounded-md border px-3 py-1.5 text-sm shadow-inner transition-all disabled:opacity-50"
                />
              )}
            </div>
          </div>
        </motion.section>

        {/* Row 3 — Processing Parameters OR Progress Bar (swaps on run) */}
        <AnimatePresence mode="wait">
          {showForm ? (
            <motion.section
              key="processing"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8, transition: { duration: 0.2 } }}
              transition={{ duration: 0.25 }}
            >
              <h2 className={sectionHeaderClass} style={{ color: 'var(--t-primary)' }}>Processing Parameters</h2>
              <div className="flex flex-col gap-6">
                <div className="w-full">
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--t-label)' }}>Number of Samples</label>
                    <Info size={12} style={{ color: 'var(--t-muted)' }} />
                  </div>
                  <NumberStepper value={maxCalls} onChange={setMaxCalls} min={1} max={2000} disabled={isRunning} />
                </div>
                <div className="flex items-center justify-between w-full mt-2 gap-3 flex-wrap">
                  <Button
                    variant="action"
                    onClick={() => { reset(); start(buildBody('heavy')) }}
                    disabled={disabled}
                    className="flex-1 h-11"
                  >
                    HEAVY AUDIT
                  </Button>

                  <Button
                    variant="action"
                    onClick={() => { reset(); start(buildBody('lite')) }}
                    disabled={disabled}
                    className="flex-1 h-11"
                  >
                    LITE AUDIT
                  </Button>
                </div>
              </div>
                </motion.section>
              ) : (
                <motion.div
                  key="progress"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -16 }}
                  transition={{ duration: 0.3 }}
                  className="w-full"
                >
                  <AuditProgressBar
                    status={status}
                    progress={progress}
                    analysisProgress={analysisProgress}
                    result={result}
                    error={error}
                    logs={logs}
                    maxCalls={maxCalls}
                    onCancel={cancel}
                    onReset={reset}
                  />
                </motion.div>
              )}
            </AnimatePresence>
      </motion.div>
    </div>
  )
}
