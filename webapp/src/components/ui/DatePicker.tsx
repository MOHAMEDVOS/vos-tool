import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, Calendar, LayoutGrid } from 'lucide-react'

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function localISO(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

interface Props {
  label?: string
  value: string
  onChange: (val: string) => void
  disabled?: boolean
  className?: string
}

export function CustomDatePicker({ value, onChange, disabled, label, className = '' }: Props) {
  const [isOpen, setIsOpen] = useState(false)
  
  const parseLocalDate = (iso: string) => {
    if (!iso) return new Date()
    const [y, m, d] = iso.split('-').map(Number)
    return new Date(y, m - 1, d)
  }

  const [viewDate, setViewDate] = useState(() => parseLocalDate(value || todayISO()))
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setViewDate(parseLocalDate(value || todayISO()))
  }, [value])

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false)
    }
    if (isOpen) document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [isOpen])

  const daysInMonth = (y: number, m: number) => new Date(y, m + 1, 0).getDate()
  const firstDayOfMonth = (y: number, m: number) => new Date(y, m, 1).getDay()
  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()
  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December']

  const generateDays = () => {
    const days = []
    const prevMonthDays = daysInMonth(year, month - 1)
    const currentMonthDays = daysInMonth(year, month)
    const firstDay = firstDayOfMonth(year, month)
    const startingDay = firstDay === 0 ? 6 : firstDay - 1
    for (let i = startingDay - 1; i >= 0; i--) days.push({ day: prevMonthDays - i, current: false, monthOffset: -1 })
    for (let i = 1; i <= currentMonthDays; i++) days.push({ day: i, current: true, monthOffset: 0 })
    const remaining = 42 - days.length
    for (let i = 1; i <= remaining; i++) days.push({ day: i, current: false, monthOffset: 1 })
    return days
  }

  const handleDayClick = (d: number, offset: number) => {
    const iso = localISO(new Date(year, month + offset, d))
    onChange(iso)
    setIsOpen(false)
  }

  const changeMonth = (offset: number) => setViewDate(new Date(year, month + offset, 1))
  const changeYear = (offset: number) => setViewDate(new Date(year + offset, month, 1))

  return (
    <div ref={ref} className={`flex flex-col gap-2 group ${className}`}>
      {label && (
        <div className="flex items-center justify-between px-1">
          <label className="text-[10px] font-black uppercase tracking-[0.15em] text-t-label group-focus-within:text-t-primary transition-colors">
            {label}
          </label>
        </div>
      )}
      
      <div className="relative w-full">
        <motion.button
          whileTap={{ scale: 0.995 }}
          type="button"
          disabled={disabled}
          onClick={() => setIsOpen(!isOpen)}
          style={{ backgroundColor: 'var(--c-base)', borderColor: 'var(--b-subtle)', color: 'var(--t-primary)' }}
          className="flex w-full h-[38px] items-center justify-between rounded-md border px-3 py-1.5 text-sm shadow-inner outline-none transition-all disabled:opacity-50 cursor-pointer focus:border-b-strong"
        >
          <span style={{ color: value ? 'var(--t-primary)' : 'var(--t-muted)' }}>
            {value ? (() => { const [y,m,d] = value.split('-'); return `${m}/${d}/${y}` })() : 'Select Date'}
          </span>
          <Calendar size={14} style={{ color: 'var(--t-muted)' }} />
        </motion.button>

        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              style={{ backgroundColor: 'var(--c-calendar)', borderColor: 'var(--b-medium)' }}
              className="absolute z-[60] mt-2 w-[280px] rounded-[24px] border shadow-2xl p-5 backdrop-blur-2xl right-0 md:left-0"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex gap-0.5">
                  <button onClick={() => changeYear(-1)} style={{ color: 'var(--t-muted)' }} className="p-1.5 hover:bg-c-raised rounded-lg transition-colors"><LayoutGrid size={12} className="rotate-45" /></button>
                  <button onClick={() => changeMonth(-1)} style={{ color: 'var(--t-muted)' }} className="p-1.5 hover:bg-c-raised rounded-lg transition-colors"><ChevronDown size={12} className="rotate-90" /></button>
                </div>
                <span style={{ color: 'var(--t-primary)' }} className="text-[11px] font-black uppercase tracking-tight">
                  {monthNames[month]} {year}
                </span>
                <div className="flex gap-0.5">
                  <button onClick={() => changeMonth(1)} style={{ color: 'var(--t-muted)' }} className="p-1.5 hover:bg-c-raised rounded-lg transition-colors"><ChevronDown size={12} className="-rotate-90" /></button>
                  <button onClick={() => changeYear(1)} style={{ color: 'var(--t-muted)' }} className="p-1.5 hover:bg-c-raised rounded-lg transition-colors"><LayoutGrid size={12} /></button>
                </div>
              </div>

              {/* Weekdays */}
              <div className="grid grid-cols-7 mb-1.5">
                {['Mo','Tu','We','Th','Fr','Sa','Su'].map(d => (
                  <span key={d} style={{ color: 'var(--t-muted)' }} className="text-center text-[9px] font-black uppercase">{d}</span>
                ))}
              </div>

              {/* Days Grid */}
              <div className="grid grid-cols-7 gap-1">
                {generateDays().map((d, i) => {
                  const dateStr = localISO(new Date(year, month + d.monthOffset, d.day))
                  const isSelected = value === dateStr
                  const isToday = todayISO() === dateStr
                  return (
                    <button
                      key={i}
                      onClick={() => handleDayClick(d.day, d.monthOffset)}
                      style={
                        isSelected
                          ? { backgroundColor: 'var(--cal-selected-bg)', color: 'var(--cal-selected-text)' }
                          : isToday
                          ? { backgroundColor: 'var(--cal-today-bg)', color: 'var(--cal-today-text)' }
                          : d.current
                          ? { color: 'var(--cal-current-text)' }
                          : { color: 'var(--cal-other-text)' }
                      }
                      className={`h-8 w-8 rounded-lg flex items-center justify-center text-[10px] transition-all ${isSelected ? 'font-bold shadow-lg scale-110' : isToday ? 'font-bold' : 'hover:bg-c-raised'}`}
                    >
                      {d.day}
                    </button>
                  )
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
