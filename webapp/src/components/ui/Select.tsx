import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, Check } from 'lucide-react'

interface Option {
  label: string
  value: string
}

interface CustomSelectProps {
  options: Option[] | string[]
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  label?: string
  className?: string
}

export function CustomSelect({
  options,
  value,
  onChange,
  placeholder = 'Select option',
  disabled,
  label,
  className = ''
}: CustomSelectProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  useEffect(() => {
    if (open) {
      setSearch('')
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  const normalizedOptions = options.map(opt =>
    typeof opt === 'string' ? { label: opt, value: opt } : opt
  )

  const filteredOptions = normalizedOptions.filter(opt =>
    opt.label.toLowerCase().includes(search.toLowerCase())
  )

  const selectedOption = normalizedOptions.find(opt => opt.value === value)

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
        onClick={() => setOpen((o) => !o)}
        style={{ backgroundColor: 'var(--c-base)', color: 'var(--t-primary)' }}
        className="flex h-[38px] w-full items-center justify-between rounded-md border border-b-subtle px-3 py-1.5 text-sm shadow-inner outline-none transition-all focus:border-b-strong disabled:opacity-50"
      >
        <span style={{ color: selectedOption ? 'var(--t-primary)' : 'var(--t-muted)' }}>
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <ChevronDown
          size={14}
          className={`shrink-0 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
          style={{ color: 'var(--t-muted)' }}
        />
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 5, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 5, scale: 0.98 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            style={{ backgroundColor: 'var(--c-float)', borderColor: 'var(--b-medium)' }}
            className="absolute z-50 mt-1 w-full rounded-lg shadow-2xl border backdrop-blur-xl p-1.5 flex flex-col gap-1"
          >
            <div className="px-1 pt-1 pb-2" style={{ borderBottom: '1px solid var(--b-divider)' }}>
              <input
                ref={inputRef}
                type="text"
                placeholder="Type to search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  backgroundColor: 'var(--c-raised)',
                  borderColor: 'var(--b-subtle)',
                  color: 'var(--t-primary)',
                }}
                className="w-full border rounded px-2 py-1.5 text-xs outline-none focus:border-b-strong transition-colors"
              />
            </div>

            <div className="max-h-60 overflow-y-auto custom-scrollbar">
              {filteredOptions.length === 0 ? (
                <div className="px-2.5 py-3 text-xs text-center" style={{ color: 'var(--t-muted)' }}>No results found</div>
              ) : (
                filteredOptions.map((opt) => {
                  const isSelected = opt.value === value
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => {
                        onChange(opt.value)
                        setOpen(false)
                      }}
                      style={{
                        backgroundColor: isSelected ? 'var(--selected-bg)' : undefined,
                        color: isSelected ? 'var(--t-primary)' : 'var(--t-label)',
                      }}
                      className="flex w-full items-center justify-between rounded-md px-2.5 py-2 text-sm transition-colors select-none hover:bg-c-raised"
                    >
                      {opt.label}
                      {isSelected && <Check size={12} style={{ color: 'var(--selected-check)' }} />}
                    </button>
                  )
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      </div>
    </div>
  )
}
