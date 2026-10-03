import { useEffect, useMemo, useRef, useState } from 'react'
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'

interface Props {
  startDate: string
  endDate: string
  onChange: (startDate: string, endDate: string) => void
  className?: string
  disabled?: boolean
}

const presets = ['Today', 'Yesterday', 'Last 2 Weeks', 'This Month', 'Last Month', 'Last 30 days', 'Last Year'] as const
const weekdays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

function toIso(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function fromIso(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function shiftDays(date: Date, amount: number) {
  const result = new Date(date)
  result.setDate(result.getDate() + amount)
  return result
}

function formatDate(value: string) {
  if (!value) return ''
  const [year, month, day] = value.split('-')
  return `${month}/${day}/${year}`
}

function CalendarMonth({
  monthDate,
  startDate,
  endDate,
  onSelect,
}: {
  monthDate: Date
  startDate: string
  endDate: string
  onSelect: (value: string) => void
}) {
  const year = monthDate.getFullYear()
  const month = monthDate.getMonth()
  const firstWeekday = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cellCount = Math.ceil((firstWeekday + daysInMonth) / 7) * 7
  const today = toIso(new Date())

  return (
    <div className="min-w-0 flex-1">
      <h3 className="mb-2 text-center text-xs font-semibold text-t-secondary">{monthDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</h3>
      <div className="mb-1 grid grid-cols-7">
        {weekdays.map((day) => <span key={day} className="py-0.5 text-center text-[9px] font-semibold uppercase text-t-muted">{day}</span>)}
      </div>
      <div className="grid grid-cols-7 gap-y-0">
        {Array.from({ length: cellCount }, (_, index) => {
          const day = index - firstWeekday + 1
          if (day < 1 || day > daysInMonth) return <span key={index} className="h-7" />
          const value = toIso(new Date(year, month, day))
          const selected = value === startDate || value === endDate
          const inRange = Boolean(startDate && endDate && value > startDate && value < endDate)
          return (
            <button
              key={index}
              type="button"
              aria-label={new Date(year, month, day).toLocaleDateString('en-US', { dateStyle: 'full' })}
              aria-pressed={selected}
              onClick={() => onSelect(value)}
              style={selected ? { backgroundColor: 'var(--b-focus)', color: 'white' } : inRange ? { backgroundColor: 'var(--c-raised)', color: 'var(--t-primary)' } : undefined}
              className={`mx-auto flex h-7 w-7 items-center justify-center rounded-full text-xs transition-colors ${selected ? 'font-semibold' : value === today ? 'font-semibold text-t-primary ring-1 ring-b-focus' : 'text-t-primary hover:bg-surface-soft'}`}
            >{day}</button>
          )
        })}
      </div>
    </div>
  )
}

export function DateRangePicker({ startDate, endDate, onChange, className = '', disabled = false }: Props) {
  const [open, setOpen] = useState(false)
  const [viewDate, setViewDate] = useState(() => {
    const initial = startDate ? fromIso(startDate) : new Date()
    return new Date(initial.getFullYear(), initial.getMonth(), 1)
  })
  const [choosingEnd, setChoosingEnd] = useState(false)
  const [presetLabel, setPresetLabel] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const secondMonth = useMemo(() => new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1), [viewDate])
  const label = startDate && endDate
    ? `${formatDate(startDate)} – ${formatDate(endDate)}`
    : startDate ? `${formatDate(startDate)} – Select end date` : 'Select date range'

  const applyPreset = (preset: typeof presets[number]) => {
    const today = new Date()
    const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())
    let start = todayStart
    let end = todayStart
    if (preset === 'Yesterday') {
      start = shiftDays(todayStart, -1)
      end = start
    } else if (preset === 'Last 2 Weeks') {
      const daysSinceMonday = (todayStart.getDay() + 6) % 7
      const currentMonday = shiftDays(todayStart, -daysSinceMonday)
      start = shiftDays(currentMonday, -7)
      end = shiftDays(currentMonday, 4)
    } else if (preset === 'This Month') {
      start = new Date(todayStart.getFullYear(), todayStart.getMonth(), 1)
    } else if (preset === 'Last Month') {
      start = new Date(todayStart.getFullYear(), todayStart.getMonth() - 1, 1)
      end = new Date(todayStart.getFullYear(), todayStart.getMonth(), 0)
    } else if (preset === 'Last 30 days') {
      start = shiftDays(todayStart, -29)
    } else if (preset === 'Last Year') {
      start = new Date(todayStart.getFullYear() - 1, 0, 1)
      end = new Date(todayStart.getFullYear() - 1, 11, 31)
    }
    onChange(toIso(start), toIso(end))
    setPresetLabel(preset)
    setChoosingEnd(false)
    setViewDate(new Date(start.getFullYear(), start.getMonth(), 1))
    setOpen(false)
  }

  const selectDate = (value: string) => {
    if (!choosingEnd || !startDate || endDate) {
      onChange(value, '')
      setChoosingEnd(true)
      setPresetLabel('')
      return
    }
    onChange(value < startDate ? value : startDate, value < startDate ? startDate : value)
    setChoosingEnd(false)
    setPresetLabel('')
  }

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        disabled={disabled}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-10 w-full items-center justify-between gap-3 rounded-lg border border-b-strong bg-surface-input px-3.5 text-sm text-t-primary shadow-inner outline-none transition-colors hover:border-b-focus focus:border-b-focus focus:ring-2 focus:ring-b-focus/20 disabled:cursor-not-allowed disabled:opacity-50 sm:w-[min(100%,360px)]"
      >
        <span className="flex min-w-0 items-center gap-2.5"><CalendarDays size={16} className="shrink-0 text-t-secondary" /><span className="truncate">{presetLabel || label}</span></span>
        <ChevronDown size={16} className={`shrink-0 text-t-secondary transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && <div className="absolute right-0 top-full z-[70] mt-2 flex max-h-[calc(100vh-1.5rem)] w-[min(600px,calc(100vw-2rem))] flex-col overflow-auto rounded-2xl border border-b-strong bg-surface-card shadow-2xl sm:flex-row">
        <aside className="flex shrink-0 flex-row gap-1 overflow-x-auto border-b border-b-divider bg-surface-soft/40 p-2 sm:w-32 sm:flex-col sm:gap-0 sm:overflow-visible sm:border-b-0 sm:border-r sm:p-3">
          {presets.map((preset) => <button key={preset} type="button" onClick={() => applyPreset(preset)} className={`shrink-0 rounded-lg px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-surface-soft ${presetLabel === preset ? 'bg-vos-500/15 font-semibold text-vos-600' : 'text-t-secondary'}`}>{preset}</button>)}
          <button type="button" onClick={() => { onChange('', ''); setPresetLabel(''); setChoosingEnd(false); setOpen(false) }} className="shrink-0 rounded-lg px-2.5 py-1.5 text-left text-xs text-red-500 transition-colors hover:bg-red-500/10 sm:mt-auto">Clear</button>
        </aside>
        <div className="min-w-0 flex-1 p-3 sm:p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <button type="button" aria-label="Previous month" onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1))} className="rounded-md p-2 text-t-secondary hover:bg-surface-soft"><ChevronLeft size={18} /></button>
            <span className="text-center text-xs font-semibold text-t-primary">{viewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })} — {secondMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</span>
            <button type="button" aria-label="Next month" onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1))} className="rounded-md p-2 text-t-secondary hover:bg-surface-soft"><ChevronRight size={18} /></button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
            <CalendarMonth monthDate={viewDate} startDate={startDate} endDate={endDate} onSelect={selectDate} />
            <CalendarMonth monthDate={secondMonth} startDate={startDate} endDate={endDate} onSelect={selectDate} />
          </div>
          <p className="mt-2 text-center text-[10px] text-t-muted">{choosingEnd ? 'Choose an end date' : label}</p>
        </div>
      </div>}
    </div>
  )
}
