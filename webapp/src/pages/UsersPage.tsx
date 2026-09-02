import { useState, useMemo, useRef, useEffect } from 'react'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { READYMODE_DIALER_URLS } from '@/api/readymode'

// ── Folder & Role option maps ────────────────────────────────────────────────
// Folder is sent by NAME, not id: folder IDs are per-dialer (e.g. 'Agents' is
// 48-36-14 on resva but 54-109- on resva4), so the backend resolves the name to
// each dialer's own id at creation time. Admin/Agents/Team Leaders exist on every
// dialer; the rest only on some (resolution fails cleanly where absent).
const FOLDER_OPTIONS = [
  { value: 'Agents',           label: 'Agents' },
  { value: 'Team Leaders',     label: 'Team Leaders' },
  { value: 'Admin',            label: 'Admin' },
  { value: 'Client A',         label: 'Client A' },
  { value: 'Delegates',        label: 'Delegates' },
  { value: 'Spanish Speakers', label: 'Spanish Speakers' },
]

const ROLE_OPTIONS = [
  { value: 'inherit', label: 'Inherit' },
  { value: '2',  label: 'Administrative' },
  { value: '6',  label: 'Users' },
  { value: '4',  label: 'Sales' },
  { value: '9',  label: 'Users-Limited Access' },
  { value: '14', label: 'Users-Openers' },
  { value: '15', label: 'Users-Closers' },
  { value: '16', label: 'Team Leader' },
  { value: '17', label: 'Quality' },
  { value: '18', label: 'Auditors/QA' },
  { value: '20', label: 'Team Leaders' },
  { value: '21', label: 'Heads/ACMs' },
  { value: '30', label: 'Team Leaders' },
]

const LS_KEY = 'vos-custom-dialers'

function loadCustomDialers(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(LS_KEY) ?? '{}') } catch { return {} }
}

function generatePassword(): string {
  const upper   = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
  const lower   = 'abcdefghjkmnpqrstuvwxyz'
  const digits  = '23456789'
  const symbols = '@#!$'
  const all     = upper + lower + digits + symbols
  const guaranteed = [
    upper[Math.floor(Math.random() * upper.length)],
    lower[Math.floor(Math.random() * lower.length)],
    digits[Math.floor(Math.random() * digits.length)],
    symbols[Math.floor(Math.random() * symbols.length)],
  ]
  for (let i = 4; i < 10; i++) guaranteed.push(all[Math.floor(Math.random() * all.length)])
  return guaranteed.sort(() => Math.random() - 0.5).join('')
}

type ResultRow = {
  name: string
  login_id: string
  dialer: string
  status: 'created' | 'failed'
  detail: string
}

type DeleteResultRow = {
  name: string
  uid?: string | null
  dialer: string
  status: 'deleted' | 'failed'
  detail: string
}

type DuplicateAccount = {
  uid: string
  folder: string
  label: string
  role: 'keep' | 'delete_candidate'
}

type DuplicateGroup = {
  name: string
  accounts: DuplicateAccount[]
}

type DuplicateDialerResult = {
  dialer: string
  dialer_url: string
  status: 'ok' | 'failed'
  detail: string
  groups: DuplicateGroup[]
}

type InactiveUser = {
  uid: string
  name: string
  folder: string
  days_active: number
}

type InactiveDialerResult = {
  dialer: string
  dialer_url: string
  status: 'ok' | 'failed'
  detail: string
  users: InactiveUser[]
}

// ── Shared dialer picker (used by both Create and Delete) ───────────────────
function DialerPicker({
  selected, onToggle, onToggleAll,
  allDialerNames, customDialers, onAddCustomDialer, onRemoveCustomDialer,
}: {
  selected: string[]
  onToggle: (name: string) => void
  onToggleAll: () => void
  allDialerNames: string[]
  customDialers: Record<string, string>
  onAddCustomDialer: (name: string, url: string) => void
  onRemoveCustomDialer: (name: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = allDialerNames.filter(d => d.toLowerCase().includes(search.toLowerCase()))
  const allSelected = selected.length === allDialerNames.length

  return (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">Dialers</label>
      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="w-full flex items-center justify-between rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary hover:border-accent focus:outline-none focus:border-accent transition-colors"
        >
          <span className={selected.length === 0 ? 'text-t-muted' : ''}>
            {selected.length === 0
              ? 'Select dialers…'
              : selected.length === allDialerNames.length
                ? 'All dialers selected'
                : selected.join(', ')}
          </span>
          <svg className={`w-4 h-4 text-t-muted transition-transform flex-shrink-0 ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {open && (
          <div className="absolute z-50 mt-1 w-full rounded-xl border border-b-medium bg-surface-card shadow-card overflow-hidden">
            <div className="p-2 border-b border-b-subtle">
              <input
                autoFocus
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search…"
                className="w-full rounded-lg border border-b-medium bg-surface-soft px-3 py-2 text-sm text-t-primary placeholder:text-t-muted focus:outline-none focus:border-accent transition-colors"
              />
            </div>
            <button
              type="button"
              onClick={onToggleAll}
              className="w-full flex items-center gap-3 px-4 py-3 text-sm text-t-primary hover:bg-surface-soft transition-colors border-b border-b-subtle"
            >
              <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${allSelected ? 'bg-accent border-accent' : 'border-b-medium bg-surface-soft'}`}>
                {allSelected && <svg className="w-3 h-3 text-t-on-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
              </span>
              <span className="font-semibold">Select all</span>
            </button>
            <div className="max-h-48 overflow-y-auto">
              {filtered.map(d => {
                const checked  = selected.includes(d)
                const isCustom = d in customDialers
                return (
                  <div key={d} className={`flex items-center transition-colors ${checked ? 'bg-[var(--selected-bg)]' : 'hover:bg-surface-soft'}`}>
                    <button
                      type="button"
                      onClick={() => onToggle(d)}
                      className="flex-1 flex items-center gap-3 px-4 py-3 text-sm text-t-primary"
                    >
                      <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${checked ? 'bg-accent border-accent' : 'border-b-medium bg-surface-soft'}`}>
                        {checked && <svg className="w-3 h-3 text-t-on-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                      </span>
                      <span className={checked ? 'font-medium' : ''}>{d}</span>
                      {isCustom && <span className="ml-auto text-xs text-t-muted font-mono pr-1 truncate max-w-[100px]">{customDialers[d]}</span>}
                    </button>
                    {isCustom && (
                      <button
                        type="button"
                        onClick={() => onRemoveCustomDialer(d)}
                        className="pr-4 text-t-muted hover:text-semantic-error transition-colors text-lg leading-none"
                        title="Remove dialer"
                      >×</button>
                    )}
                  </div>
                )
              })}
              {filtered.length === 0 && (
                <p className="px-4 py-3 text-sm text-t-muted">No dialers match.</p>
              )}
            </div>
            <div className="border-t border-b-medium bg-surface-soft p-3 space-y-2">
              <p className="text-[11px] font-semibold text-t-secondary uppercase tracking-wide">Add dialer</p>
              <div className="flex gap-2">
                <input
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  placeholder="Name"
                  className="w-24 rounded-lg border border-b-medium bg-surface-card px-2 py-1.5 text-xs text-t-primary placeholder:text-t-placeholder focus:outline-none focus:border-accent transition-colors"
                />
                <input
                  value={newUrl}
                  onChange={e => setNewUrl(e.target.value)}
                  placeholder="https://…readymode.com/"
                  className="flex-1 min-w-0 rounded-lg border border-b-medium bg-surface-card px-2 py-1.5 text-xs text-t-primary placeholder:text-t-placeholder focus:outline-none focus:border-accent transition-colors"
                />
                <button
                  type="button"
                  onClick={() => { onAddCustomDialer(newName.trim(), newUrl.trim()); setNewName(''); setNewUrl('') }}
                  disabled={!newName.trim() || !newUrl.trim()}
                  className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-accent text-t-on-primary disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
                >Add</button>
              </div>
            </div>
          </div>
        )}
      </div>
      {selected.length === 0 && (
        <p className="text-xs text-semantic-error">Select at least one dialer.</p>
      )}
    </div>
  )
}

export function UsersPage() {
  const token = useAuthStore((s) => s.token)
  const [mode, setMode] = useState<'create' | 'delete' | 'duplicates'>('create')

  // ── Shared: custom dialers (persisted to localStorage) ──────────────────────
  const [customDialers, setCustomDialers] = useState<Record<string, string>>(loadCustomDialers)
  const allDialerUrls  = { ...READYMODE_DIALER_URLS, ...customDialers }
  const allDialerNames = Object.keys(allDialerUrls)

  const saveCustomDialers = (next: Record<string, string>) => {
    setCustomDialers(next)
    localStorage.setItem(LS_KEY, JSON.stringify(next))
  }
  const addCustomDialer = (name: string, url: string) => {
    if (!name || !url) return
    if (!url.endsWith('/')) url += '/'
    saveCustomDialers({ ...customDialers, [name]: url })
  }
  const removeCustomDialer = (name: string) => {
    const next = { ...customDialers }
    delete next[name]
    saveCustomDialers(next)
    setSelectedDialers(prev => prev.filter(d => d !== name))
    setDeleteSelectedDialers(prev => prev.filter(d => d !== name))
    setDupSelectedDialers(prev => prev.filter(d => d !== name))
  }

  // ══════════════════════════════════════════════════════════════════════════
  // CREATE mode
  // ══════════════════════════════════════════════════════════════════════════
  const [selectedDialers, setSelectedDialers] = useState<string[]>(['resva'])
  const [folder, setFolder] = useState('Agents')
  const [ou, setOu] = useState('4')
  const [namesText, setNamesText] = useState('')
  const [loginIdsText, setLoginIdsText] = useState('')
  const [passwordsText, setPasswordsText] = useState('')
  const [copied, setCopied] = useState(false)

  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<ResultRow[]>([])

  const names = useMemo(() =>
    namesText.split('\n').map(s => s.trim()).filter(Boolean), [namesText])
  const loginIds = useMemo(() =>
    loginIdsText.split('\n').map(s => s.trim()).filter(Boolean), [loginIdsText])
  const passwords = useMemo(() =>
    passwordsText.split('\n').map(s => s.trim()).filter(Boolean), [passwordsText])

  useEffect(() => {
    if (names.length === 0) return
    const current = passwordsText.split('\n').map(s => s.trim())
    const next = names.map((_, i) => current[i] || generatePassword())
    if (next.join('\n') !== passwordsText) setPasswordsText(next.join('\n'))
  }, [names.length]) // eslint-disable-line react-hooks/exhaustive-deps

  const regenerateAll = () => setPasswordsText(names.map(() => generatePassword()).join('\n'))

  const preview = useMemo(() => {
    return names.map((name, i) => ({
      name,
      login_id: loginIds[i] ?? '',
      password: passwords[i] ?? '',
      folder,
      ou,
    }))
  }, [names, loginIds, passwords, folder, ou])

  const mismatch = names.length > 0 && (
    (loginIds.length > 0 && loginIds.length !== names.length) ||
    (passwords.length > 0 && passwords.length !== names.length)
  )
  const canCreate = preview.length > 0 && !mismatch && selectedDialers.length > 0 && !running &&
    preview.every(r => r.password && r.login_id)

  const toggleDialer = (d: string) =>
    setSelectedDialers(prev =>
      prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d])
  const toggleAllDialers = () =>
    setSelectedDialers(selectedDialers.length === allDialerNames.length ? [] : [...allDialerNames])

  const handleCopy = () => {
    const pad = (s: string, n: number) => s + ' '.repeat(Math.max(0, n - s.length))
    const nameW = Math.max(4, ...preview.map(r => r.name.length))
    const idW   = Math.max(8, ...preview.map(r => r.login_id.length))
    const header  = `${pad('Name', nameW)}  ${pad('Login ID', idW)}  Password`
    const divider = `${'-'.repeat(nameW)}  ${'-'.repeat(idW)}  ----------`
    const rows = preview.map(r =>
      `${pad(r.name, nameW)}  ${pad(r.login_id, idW)}  ${r.password}`
    ).join('\n')
    navigator.clipboard.writeText(`${header}\n${divider}\n${rows}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleCreate = async () => {
    setRunning(true)
    setResults([])

    const body = {
      dialer_urls: selectedDialers.map(d => allDialerUrls[d]),
      users: preview.map(r => ({
        name: r.name,
        login_id: r.login_id,
        password: r.password,
        folder: r.folder,
        ou: r.ou,
        ext: '',
      })),
    }

    try {
      const res = await fetch('/api/readymode-users/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          try {
            const { event, data } = JSON.parse(line.slice(5).trim())
            if (event === 'done') setResults(data as ResultRow[])
            if (event === 'error') setResults(prev => [...prev, { name: '—', login_id: '—', dialer: 'all', status: 'failed', detail: String(data) }])
          } catch { /* ignore malformed SSE */ }
        }
      }
    } catch (e) {
      setResults(prev => [...prev, { name: '—', login_id: '—', dialer: 'all', status: 'failed', detail: `Connection error: ${(e as Error).message}` }])
    } finally {
      setRunning(false)
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // DELETE mode
  // ══════════════════════════════════════════════════════════════════════════
  const [deleteSelectedDialers, setDeleteSelectedDialers] = useState<string[]>(['resva'])
  const [deleteNamesText, setDeleteNamesText] = useState('')
  const [deleteRunning, setDeleteRunning] = useState(false)
  const [deleteResults, setDeleteResults] = useState<DeleteResultRow[]>([])

  const deleteNames = useMemo(() =>
    deleteNamesText.split('\n').map(s => s.trim()).filter(Boolean), [deleteNamesText])

  const canDelete = deleteNames.length > 0 && deleteSelectedDialers.length > 0 && !deleteRunning

  const toggleDeleteDialer = (d: string) =>
    setDeleteSelectedDialers(prev =>
      prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d])
  const toggleAllDeleteDialers = () =>
    setDeleteSelectedDialers(deleteSelectedDialers.length === allDialerNames.length ? [] : [...allDialerNames])

  const handleDelete = async () => {
    const total = deleteNames.length * deleteSelectedDialers.length
    if (!window.confirm(
      `Permanently delete ${deleteNames.length} user(s) on ${deleteSelectedDialers.length} dialer(s) ` +
      `(${total} account${total === 1 ? '' : 's'} total)?\n\nThis cannot be undone from VOS.`
    )) return

    setDeleteRunning(true)
    setDeleteResults([])

    const body = {
      dialer_urls: deleteSelectedDialers.map(d => allDialerUrls[d]),
      users: deleteNames.map(name => ({ name })),
    }

    try {
      const res = await fetch('/api/readymode-users/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          try {
            const { event, data } = JSON.parse(line.slice(5).trim())
            if (event === 'done') setDeleteResults(data as DeleteResultRow[])
            if (event === 'error') setDeleteResults(prev => [...prev, { name: '—', dialer: 'all', status: 'failed', detail: String(data) }])
          } catch { /* ignore malformed SSE */ }
        }
      }
    } catch (e) {
      setDeleteResults(prev => [...prev, { name: '—', dialer: 'all', status: 'failed', detail: `Connection error: ${(e as Error).message}` }])
    } finally {
      setDeleteRunning(false)
    }
  }

  // ── Inactive-users scan (lives inside Delete mode, shares its dialer picker) ─
  const [maxDaysActive, setMaxDaysActive] = useState(2)
  const [lookbackDays, setLookbackDays] = useState(60)
  const [inactiveRunning, setInactiveRunning] = useState(false)
  const [inactiveResults, setInactiveResults] = useState<InactiveDialerResult[]>([])
  const [inactiveSelectedUids, setInactiveSelectedUids] = useState<Record<string, boolean>>({}) // key: `${dialer}:${uid}`
  const [inactiveDeleting, setInactiveDeleting] = useState(false)
  const [inactiveDeleteResults, setInactiveDeleteResults] = useState<DeleteResultRow[]>([])

  const sortedInactiveResults = useMemo(() =>
    [...inactiveResults].sort((a, b) => a.dialer.localeCompare(b.dialer)), [inactiveResults])

  const inactiveCandidateCount = useMemo(() =>
    inactiveResults.reduce((n, r) => n + r.users.length, 0), [inactiveResults])

  const inactiveSelectedCount = useMemo(() =>
    Object.values(inactiveSelectedUids).filter(Boolean).length, [inactiveSelectedUids])

  const canScanInactive = deleteSelectedDialers.length > 0 && !inactiveRunning

  const handleScanInactive = async () => {
    setInactiveRunning(true)
    setInactiveResults([])
    setInactiveSelectedUids({})
    setInactiveDeleteResults([])

    const body = {
      dialer_urls: deleteSelectedDialers.map(d => allDialerUrls[d]),
      max_days_active: maxDaysActive,
      lookback_days: lookbackDays,
    }

    try {
      const res = await fetch('/api/readymode-users/inactive', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          try {
            const { event, data } = JSON.parse(line.slice(5).trim())
            if (event === 'done') {
              const results = data as InactiveDialerResult[]
              setInactiveResults(results)
            }
            if (event === 'error') setInactiveResults(prev => [...prev, {
              dialer: 'all', dialer_url: '', status: 'failed', detail: String(data), users: [],
            }])
          } catch { /* ignore malformed SSE */ }
        }
      }
    } catch (e) {
      setInactiveResults(prev => [...prev, {
        dialer: 'all', dialer_url: '', status: 'failed',
        detail: `Connection error: ${(e as Error).message}`, users: [],
      }])
    } finally {
      setInactiveRunning(false)
    }
  }

  const handleDeleteInactive = async () => {
    const toDelete = inactiveResults.flatMap(r =>
      r.users
        .filter(u => inactiveSelectedUids[`${r.dialer}:${u.uid}`])
        .map(u => ({ dialerUrl: r.dialer_url, dialer: r.dialer, name: u.name, uid: u.uid })))
    if (toDelete.length === 0) return

    const dialerCount = new Set(toDelete.map(t => t.dialerUrl)).size
    if (!window.confirm(
      `Permanently delete ${toDelete.length} inactive account(s) across ${dialerCount} dialer(s)?\n\nThis cannot be undone from VOS.`
    )) return

    setInactiveDeleting(true)
    setInactiveDeleteResults([])

    const byDialer = new Map<string, typeof toDelete>()
    for (const t of toDelete) byDialer.set(t.dialerUrl, [...(byDialer.get(t.dialerUrl) ?? []), t])

    // Sequential per dialer — a uid-carrying request must target exactly one dialer
    // (enforced server-side too).
    for (const [dialerUrl, rows] of byDialer) {
      const body = {
        dialer_urls: [dialerUrl],
        users: rows.map(r => ({ name: r.name, uid: r.uid })),
      }
      try {
        const res = await fetch('/api/readymode-users/delete', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(body),
        })

        const reader = res.body?.getReader()
        const decoder = new TextDecoder()
        let buf = ''

        while (reader) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''
          for (const line of lines) {
            if (!line.startsWith('data:')) continue
            try {
              const { event, data } = JSON.parse(line.slice(5).trim())
              if (event === 'done') setInactiveDeleteResults(prev => [...prev, ...(data as DeleteResultRow[])])
              if (event === 'error') setInactiveDeleteResults(prev => [...prev, {
                name: '—', dialer: rows[0]?.dialer ?? 'unknown', status: 'failed', detail: String(data),
              }])
            } catch { /* ignore malformed SSE */ }
          }
        }
      } catch (e) {
        setInactiveDeleteResults(prev => [...prev, {
          name: '—', dialer: rows[0]?.dialer ?? 'unknown', status: 'failed',
          detail: `Connection error: ${(e as Error).message}`,
        }])
      }
    }

    setInactiveDeleting(false)
  }

  const toggleAllInactive = () => {
    const allKeys = inactiveResults.flatMap(r => r.users.map(u => `${r.dialer}:${u.uid}`))
    const allSelected = allKeys.length > 0 && allKeys.every(k => inactiveSelectedUids[k])
    const next: Record<string, boolean> = {}
    if (!allSelected) for (const k of allKeys) next[k] = true
    setInactiveSelectedUids(next)
  }

  // ══════════════════════════════════════════════════════════════════════════
  // DUPLICATES mode
  // ══════════════════════════════════════════════════════════════════════════
  const [dupSelectedDialers, setDupSelectedDialers] = useState<string[]>(['resva'])
  const [dupRunning, setDupRunning] = useState(false)
  const [dupResults, setDupResults] = useState<DuplicateDialerResult[]>([])
  const [dupSelectedUids, setDupSelectedUids] = useState<Record<string, boolean>>({}) // key: `${dialer}:${uid}`
  const [dupDeleting, setDupDeleting] = useState(false)
  const [dupDeleteResults, setDupDeleteResults] = useState<DeleteResultRow[]>([])

  const toggleDupDialer = (d: string) =>
    setDupSelectedDialers(prev =>
      prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d])
  const toggleAllDupDialers = () =>
    setDupSelectedDialers(dupSelectedDialers.length === allDialerNames.length ? [] : [...allDialerNames])

  const sortedDupResults = useMemo(() =>
    [...dupResults].sort((a, b) => a.dialer.localeCompare(b.dialer)), [dupResults])

  const dupCandidateCount = useMemo(() =>
    dupResults.reduce((n, r) => n + r.groups.reduce((m, g) =>
      m + g.accounts.filter(a => a.role === 'delete_candidate').length, 0), 0),
    [dupResults])

  const dupSelectedCount = useMemo(() =>
    Object.values(dupSelectedUids).filter(Boolean).length, [dupSelectedUids])

  const canScanDuplicates = dupSelectedDialers.length > 0 && !dupRunning

  const handleScanDuplicates = async () => {
    setDupRunning(true)
    setDupResults([])
    setDupSelectedUids({})
    setDupDeleteResults([])

    const body = { dialer_urls: dupSelectedDialers.map(d => allDialerUrls[d]) }

    try {
      const res = await fetch('/api/readymode-users/duplicates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          try {
            const { event, data } = JSON.parse(line.slice(5).trim())
            if (event === 'done') {
              const results = data as DuplicateDialerResult[]
              setDupResults(results)
              // Pre-check every delete-candidate — still requires the confirm() below to act.
              const initial: Record<string, boolean> = {}
              for (const r of results) {
                for (const g of r.groups) {
                  for (const a of g.accounts) {
                    if (a.role === 'delete_candidate') initial[`${r.dialer}:${a.uid}`] = true
                  }
                }
              }
              setDupSelectedUids(initial)
            }
            if (event === 'error') setDupResults(prev => [...prev, {
              dialer: 'all', dialer_url: '', status: 'failed', detail: String(data), groups: [],
            }])
          } catch { /* ignore malformed SSE */ }
        }
      }
    } catch (e) {
      setDupResults(prev => [...prev, {
        dialer: 'all', dialer_url: '', status: 'failed',
        detail: `Connection error: ${(e as Error).message}`, groups: [],
      }])
    } finally {
      setDupRunning(false)
    }
  }

  const handleDeleteDuplicates = async () => {
    const toDelete = dupResults.flatMap(r =>
      r.groups.flatMap(g => g.accounts
        .filter(a => a.role === 'delete_candidate' && dupSelectedUids[`${r.dialer}:${a.uid}`])
        .map(a => ({ dialerUrl: r.dialer_url, dialer: r.dialer, name: g.name, uid: a.uid }))))
    if (toDelete.length === 0) return

    const dialerCount = new Set(toDelete.map(t => t.dialerUrl)).size
    if (!window.confirm(
      `Permanently delete ${toDelete.length} duplicate account(s) across ${dialerCount} dialer(s)?\n\nThis cannot be undone from VOS.`
    )) return

    setDupDeleting(true)
    setDupDeleteResults([])

    const byDialer = new Map<string, typeof toDelete>()
    for (const t of toDelete) byDialer.set(t.dialerUrl, [...(byDialer.get(t.dialerUrl) ?? []), t])

    // Sequential per dialer — a uid-carrying request must target exactly one dialer
    // (enforced server-side too), and this keeps progress easy to render.
    for (const [dialerUrl, rows] of byDialer) {
      const body = {
        dialer_urls: [dialerUrl],
        users: rows.map(r => ({ name: r.name, uid: r.uid })),
      }
      try {
        const res = await fetch('/api/readymode-users/delete', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(body),
        })

        const reader = res.body?.getReader()
        const decoder = new TextDecoder()
        let buf = ''

        while (reader) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''
          for (const line of lines) {
            if (!line.startsWith('data:')) continue
            try {
              const { event, data } = JSON.parse(line.slice(5).trim())
              if (event === 'done') setDupDeleteResults(prev => [...prev, ...(data as DeleteResultRow[])])
              if (event === 'error') setDupDeleteResults(prev => [...prev, {
                name: '—', dialer: rows[0]?.dialer ?? 'unknown', status: 'failed', detail: String(data),
              }])
            } catch { /* ignore malformed SSE */ }
          }
        }
      } catch (e) {
        setDupDeleteResults(prev => [...prev, {
          name: '—', dialer: rows[0]?.dialer ?? 'unknown', status: 'failed',
          detail: `Connection error: ${(e as Error).message}`,
        }])
      }
    }

    setDupDeleting(false)
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-5 p-6">

      {/* Page header + mode toggle */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-t-primary">
            {mode === 'create' ? 'Create Dialer Users' : mode === 'delete' ? 'Delete Dialer Users' : 'Duplicate Dialer Users'}
          </h1>
          <p className="text-sm text-t-muted mt-0.5">
            {mode === 'create'
              ? 'Paste names & login IDs, pick dialers, create all accounts in one click.'
              : mode === 'delete'
                ? 'Paste names, pick dialers, permanently delete those accounts. This cannot be undone.'
                : 'Scan dialers for accounts sharing a name, then delete the extra copies. This cannot be undone.'}
          </p>
        </div>
        <div className="flex rounded-lg border border-b-subtle bg-surface-soft p-1">
          <button
            type="button"
            onClick={() => setMode('create')}
            className={`px-3 py-1.5 rounded-md text-sm font-semibold transition-colors ${mode === 'create' ? 'bg-accent text-t-on-primary' : 'text-t-muted hover:text-t-primary'}`}
          >Create</button>
          <button
            type="button"
            onClick={() => setMode('delete')}
            className={`px-3 py-1.5 rounded-md text-sm font-semibold transition-colors ${mode === 'delete' ? 'bg-semantic-error text-t-on-primary' : 'text-t-muted hover:text-t-primary'}`}
          >Delete</button>
          <button
            type="button"
            onClick={() => setMode('duplicates')}
            className={`px-3 py-1.5 rounded-md text-sm font-semibold transition-colors ${mode === 'duplicates' ? 'bg-semantic-warning text-t-on-primary' : 'text-t-muted hover:text-t-primary'}`}
          >Duplicates</button>
        </div>
      </div>

      {mode === 'create' ? (
        <div className="grid grid-cols-[300px_1fr] gap-4 items-start">

          {/* ════════ LEFT PANEL — config + summary + create ════════ */}
          <div className="sticky top-6 rounded-xl border border-b-subtle bg-surface-card p-4 flex flex-col gap-4">

            <DialerPicker
              selected={selectedDialers}
              onToggle={toggleDialer}
              onToggleAll={toggleAllDialers}
              allDialerNames={allDialerNames}
              customDialers={customDialers}
              onAddCustomDialer={addCustomDialer}
              onRemoveCustomDialer={removeCustomDialer}
            />

            {/* Folder */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">Folder</label>
              <select
                value={folder}
                onChange={e => setFolder(e.target.value)}
                className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent"
              >
                {FOLDER_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {/* Role */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">Role</label>
              <select
                value={ou}
                onChange={e => setOu(e.target.value)}
                className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent"
              >
                {ROLE_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div className="border-t border-b-subtle" />

            {/* Summary */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-t-muted uppercase tracking-wide">Summary</p>
              <div className="rounded-lg border border-b-subtle bg-surface-soft p-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-t-muted">Users</span>
                  <span className="font-semibold text-t-primary">{names.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-t-muted">Dialers</span>
                  <span className="font-semibold text-t-primary">{selectedDialers.length} selected</span>
                </div>
                <div className="border-t border-b-subtle pt-2 flex justify-between">
                  <span className="text-t-muted">Total accounts</span>
                  <span className={`font-bold ${names.length * selectedDialers.length > 0 ? 'text-accent' : 'text-t-muted'}`}>
                    {names.length * selectedDialers.length}
                  </span>
                </div>
              </div>
            </div>

            <button
              onClick={handleCreate}
              disabled={!canCreate}
              className={[
                'w-full rounded-xl py-3 text-sm font-bold tracking-wide transition-all',
                canCreate
                  ? 'bg-accent text-t-on-primary hover:opacity-90 active:scale-[0.99]'
                  : 'bg-surface-soft text-t-muted cursor-not-allowed',
              ].join(' ')}
            >
              {running
                ? <span className="flex items-center justify-center gap-2"><Loader2 size={14} className="animate-spin" /> Creating…</span>
                : `Create ${preview.length * selectedDialers.length || ''} accounts`}
            </button>
          </div>

          {/* ════════ RIGHT PANEL — user data + preview table ════════ */}
          <div className="flex flex-col gap-4">

            <section className="rounded-xl border border-b-subtle bg-surface-card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-t-primary">User Data</span>
                <button
                  type="button"
                  onClick={regenerateAll}
                  disabled={names.length === 0}
                  className="text-xs font-semibold text-accent hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  ↻ Regenerate All Passwords
                </button>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">
                    Agent Names <span className="normal-case font-normal">(one per line)</span>
                  </label>
                  <textarea
                    value={namesText}
                    onChange={e => setNamesText(e.target.value)}
                    rows={9}
                    placeholder={"Ahmed Hassan\nSara Mohamed\nKhaled Ali"}
                    className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent resize-none font-mono"
                  />
                  <p className="text-xs text-t-muted">{names.length} names</p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">
                    Login IDs <span className="normal-case font-normal">(same order)</span>
                  </label>
                  <textarea
                    value={loginIdsText}
                    onChange={e => setLoginIdsText(e.target.value)}
                    rows={9}
                    placeholder={"RES-014\nRES-015\nRES-016"}
                    className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent resize-none font-mono"
                  />
                  <p className="text-xs text-t-muted">{loginIds.length} login IDs</p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">
                    Passwords <span className="normal-case font-normal">(auto-generated)</span>
                  </label>
                  <textarea
                    value={passwordsText}
                    onChange={e => setPasswordsText(e.target.value)}
                    rows={9}
                    placeholder="Paste names to auto-generate…"
                    className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent resize-none font-mono"
                  />
                  <p className="text-xs text-t-muted">{passwords.length} passwords</p>
                </div>
              </div>

              {mismatch && (
                <p className="text-xs text-semantic-error font-semibold">
                  All three columns must have the same number of lines (names: {names.length}, login IDs: {loginIds.length}, passwords: {passwords.length}).
                </p>
              )}
            </section>

            {preview.length > 0 && (
              <section className="rounded-xl border border-b-subtle bg-surface-card overflow-hidden">
                <div className="px-4 py-3 border-b border-b-subtle flex items-center justify-between">
                  <span className="text-sm font-semibold text-t-primary">Preview</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-t-muted">
                      {preview.length} users × {selectedDialers.length} dialer{selectedDialers.length !== 1 ? 's' : ''} ={' '}
                      <span className="font-bold text-t-primary">{preview.length * selectedDialers.length} accounts</span>
                    </span>
                    <button
                      type="button"
                      onClick={handleCopy}
                      className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg border border-b-medium bg-surface-soft text-t-primary hover:border-accent hover:text-accent transition-colors"
                    >
                      {copied ? '✓ Copied' : '⎘ Copy'}
                    </button>
                  </div>
                </div>
                <div className="overflow-x-auto max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-surface-soft">
                      <tr>
                        {['Name', 'Login ID', 'Password', 'Folder', 'Role', 'Status'].map(h => (
                          <th key={h} className="px-3 py-2 text-left font-semibold text-t-muted">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.map((row, i) => {
                        const userResults   = results.filter(r => r.login_id === row.login_id)
                        const failedDialers = userResults.filter(r => r.status === 'failed').map(r => r.dialer)
                        const allCreated    = userResults.length > 0 && failedDialers.length === 0
                        return (
                          <tr key={i} className="border-t border-b-subtle hover:bg-surface-soft">
                            <td className="px-3 py-1.5 text-t-primary">{row.name}</td>
                            <td className="px-3 py-1.5 font-mono text-accent">
                              {row.login_id || <span className="text-semantic-error">missing</span>}
                            </td>
                            <td className="px-3 py-1.5 font-mono text-t-secondary">
                              {row.password || <span className="text-semantic-error">missing</span>}
                            </td>
                            <td className="px-3 py-1.5 text-t-muted">
                              {FOLDER_OPTIONS.find(f => f.value === row.folder)?.label ?? row.folder}
                            </td>
                            <td className="px-3 py-1.5 text-t-muted">
                              {ROLE_OPTIONS.find(r => r.value === row.ou)?.label ?? row.ou}
                            </td>
                            <td className="px-3 py-1.5">
                              {running && userResults.length === 0
                                ? <Loader2 size={16} className="animate-spin text-t-muted" />
                                : allCreated
                                  ? <CheckCircle2 size={16} className="text-semantic-success" />
                                  : failedDialers.length > 0
                                    ? <span className="flex items-center gap-1">
                                        <XCircle size={16} className="text-semantic-error flex-shrink-0" />
                                        <span className="text-xs text-semantic-error">{failedDialers.join(', ')}</span>
                                      </span>
                                    : null}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>
        </div>
      ) : mode === 'delete' ? (
        <div className="grid grid-cols-[300px_1fr] gap-4 items-start">

          {/* ════════ LEFT PANEL — dialers + summary + delete ════════ */}
          <div className="sticky top-6 rounded-xl border border-b-subtle bg-surface-card p-4 flex flex-col gap-4">

            <DialerPicker
              selected={deleteSelectedDialers}
              onToggle={toggleDeleteDialer}
              onToggleAll={toggleAllDeleteDialers}
              allDialerNames={allDialerNames}
              customDialers={customDialers}
              onAddCustomDialer={addCustomDialer}
              onRemoveCustomDialer={removeCustomDialer}
            />

            <div className="border-t border-b-subtle" />

            <div className="space-y-2">
              <p className="text-xs font-semibold text-t-muted uppercase tracking-wide">Summary</p>
              <div className="rounded-lg border border-b-subtle bg-surface-soft p-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-t-muted">Users</span>
                  <span className="font-semibold text-t-primary">{deleteNames.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-t-muted">Dialers</span>
                  <span className="font-semibold text-t-primary">{deleteSelectedDialers.length} selected</span>
                </div>
                <div className="border-t border-b-subtle pt-2 flex justify-between">
                  <span className="text-t-muted">Total to delete</span>
                  <span className={`font-bold ${deleteNames.length * deleteSelectedDialers.length > 0 ? 'text-semantic-error' : 'text-t-muted'}`}>
                    {deleteNames.length * deleteSelectedDialers.length}
                  </span>
                </div>
              </div>
            </div>

            <p className="text-xs text-t-muted">
              Names are matched against each dialer's recent call-log activity to find the
              account to delete — an account with no calls on record there may not resolve.
            </p>

            <button
              onClick={handleDelete}
              disabled={!canDelete}
              className={[
                'w-full rounded-xl py-3 text-sm font-bold tracking-wide transition-all',
                canDelete
                  ? 'bg-semantic-error text-t-on-primary hover:opacity-90 active:scale-[0.99]'
                  : 'bg-surface-soft text-t-muted cursor-not-allowed',
              ].join(' ')}
            >
              {deleteRunning
                ? <span className="flex items-center justify-center gap-2"><Loader2 size={14} className="animate-spin" /> Deleting…</span>
                : `Delete ${deleteNames.length * deleteSelectedDialers.length || ''} accounts`}
            </button>
          </div>

          {/* ════════ RIGHT PANEL — names + results ════════ */}
          <div className="flex flex-col gap-4">

            <section className="rounded-xl border border-b-subtle bg-surface-card p-4 space-y-3">
              <span className="text-sm font-semibold text-t-primary">Names to delete</span>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">
                  Agent Names <span className="normal-case font-normal">(one per line, matches ReadyMode's display name)</span>
                </label>
                <textarea
                  value={deleteNamesText}
                  onChange={e => setDeleteNamesText(e.target.value)}
                  rows={9}
                  placeholder={"Ahmed Hassan\nSara Mohamed"}
                  className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent resize-none font-mono"
                />
                <p className="text-xs text-t-muted">{deleteNames.length} names</p>
              </div>
            </section>

            {deleteNames.length > 0 && (
              <section className="rounded-xl border border-b-subtle bg-surface-card overflow-hidden">
                <div className="px-4 py-3 border-b border-b-subtle flex items-center justify-between">
                  <span className="text-sm font-semibold text-t-primary">Preview</span>
                  <span className="text-xs text-t-muted">
                    {deleteNames.length} users × {deleteSelectedDialers.length} dialer{deleteSelectedDialers.length !== 1 ? 's' : ''} ={' '}
                    <span className="font-bold text-t-primary">{deleteNames.length * deleteSelectedDialers.length} accounts</span>
                  </span>
                </div>
                <div className="overflow-x-auto max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-surface-soft">
                      <tr>
                        {['Name', 'Status'].map(h => (
                          <th key={h} className="px-3 py-2 text-left font-semibold text-t-muted">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {deleteNames.map((name, i) => {
                        const userResults   = deleteResults.filter(r => r.name === name)
                        const failedDialers = userResults.filter(r => r.status === 'failed').map(r => `${r.dialer} (${r.detail})`)
                        const allDeleted    = userResults.length > 0 && failedDialers.length === 0
                        return (
                          <tr key={i} className="border-t border-b-subtle hover:bg-surface-soft">
                            <td className="px-3 py-1.5 text-t-primary">{name}</td>
                            <td className="px-3 py-1.5">
                              {deleteRunning && userResults.length === 0
                                ? <Loader2 size={16} className="animate-spin text-t-muted" />
                                : allDeleted
                                  ? <CheckCircle2 size={16} className="text-semantic-success" />
                                  : failedDialers.length > 0
                                    ? <span className="flex items-center gap-1">
                                        <XCircle size={16} className="text-semantic-error flex-shrink-0" />
                                        <span className="text-xs text-semantic-error">{failedDialers.join(', ')}</span>
                                      </span>
                                    : null}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {/* ════════ Find inactive users — separate flow within Delete mode ════════ */}
            <section className="rounded-xl border border-b-subtle bg-surface-card p-4 space-y-3">
              <div>
                <span className="text-sm font-semibold text-t-primary">Find Inactive Users</span>
                <p className="text-xs text-t-muted mt-0.5">
                  Scans every account in every folder on the selected dialer(s) (uses the
                  Dialers selection above) and flags anyone with little-to-no shift activity —
                  a login/shift signal, not a call count. If you select more than one dialer,
                  someone active on any of them is excluded everywhere, even where their own
                  account looks idle — only flagged if inactive on every dialer selected.
                  Review the list, then delete in bulk.
                </p>
              </div>

              <div className="flex gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">Max active days</label>
                  <input
                    type="number"
                    min={0}
                    value={maxDaysActive}
                    onChange={e => setMaxDaysActive(Math.max(0, Number(e.target.value) || 0))}
                    className="w-24 rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">Lookback (days)</label>
                  <input
                    type="number"
                    min={1}
                    value={lookbackDays}
                    onChange={e => setLookbackDays(Math.max(1, Number(e.target.value) || 1))}
                    className="w-24 rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent"
                  />
                </div>
                <button
                  onClick={handleScanInactive}
                  disabled={!canScanInactive}
                  className={[
                    'self-end rounded-lg px-4 py-2 text-sm font-bold tracking-wide transition-all',
                    canScanInactive
                      ? 'bg-semantic-warning text-t-on-primary hover:opacity-90 active:scale-[0.99]'
                      : 'bg-surface-soft text-t-muted cursor-not-allowed',
                  ].join(' ')}
                >
                  {inactiveRunning
                    ? <span className="flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Scanning…</span>
                    : 'Scan for Inactive Users'}
                </button>
              </div>

              {inactiveResults.length > 0 && (
                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-t-muted">
                    {inactiveCandidateCount} candidate{inactiveCandidateCount === 1 ? '' : 's'} found
                    {inactiveResults.some(r => r.status === 'failed') &&
                      ` — ${inactiveResults.filter(r => r.status === 'failed').length} dialer(s) failed to scan`}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={toggleAllInactive}
                      className="text-xs font-semibold text-accent hover:underline"
                    >Select all</button>
                    <button
                      onClick={handleDeleteInactive}
                      disabled={inactiveSelectedCount === 0 || inactiveDeleting}
                      className={[
                        'rounded-lg px-3 py-1.5 text-xs font-bold tracking-wide transition-all',
                        inactiveSelectedCount > 0 && !inactiveDeleting
                          ? 'bg-semantic-error text-t-on-primary hover:opacity-90 active:scale-[0.99]'
                          : 'bg-surface-soft text-t-muted cursor-not-allowed',
                      ].join(' ')}
                    >
                      {inactiveDeleting
                        ? <span className="flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Deleting…</span>
                        : `Delete ${inactiveSelectedCount || ''} selected`}
                    </button>
                  </div>
                </div>
              )}
            </section>

            {sortedInactiveResults.map(r => (
              <section key={r.dialer} className="rounded-xl border border-b-subtle bg-surface-card overflow-hidden">
                <div className="px-4 py-3 border-b border-b-subtle flex items-center justify-between">
                  <span className="text-sm font-semibold text-t-primary">{r.dialer}</span>
                  {r.status === 'ok' && (
                    <span className="text-xs text-t-muted">
                      {r.users.length} candidate{r.users.length === 1 ? '' : 's'}
                    </span>
                  )}
                </div>
                {r.status === 'failed' ? (
                  <p className="px-4 py-3 text-sm text-semantic-error">{r.detail || 'Scan failed on this dialer.'}</p>
                ) : r.users.length === 0 ? (
                  <p className="px-4 py-3 text-sm text-t-muted">No inactive candidates found on {r.dialer}.</p>
                ) : (
                  <div className="overflow-x-auto max-h-80 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-surface-soft">
                        <tr>
                          {['', 'Name', 'uid', 'Folder', 'Active days', 'Status'].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-semibold text-t-muted">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {r.users.map(u => {
                          const key = `${r.dialer}:${u.uid}`
                          const deleteResult = inactiveDeleteResults.find(dr => dr.uid === u.uid && dr.dialer === r.dialer)
                          return (
                            <tr key={key} className="border-t border-b-subtle hover:bg-surface-soft">
                              <td className="px-3 py-1.5">
                                <input
                                  type="checkbox"
                                  checked={!!inactiveSelectedUids[key]}
                                  onChange={e => setInactiveSelectedUids(prev => ({ ...prev, [key]: e.target.checked }))}
                                  className="w-4 h-4 accent-semantic-error"
                                />
                              </td>
                              <td className="px-3 py-1.5 text-t-primary">{u.name}</td>
                              <td className="px-3 py-1.5 font-mono text-t-secondary">{u.uid}</td>
                              <td className="px-3 py-1.5 text-t-muted">{u.folder}</td>
                              <td className="px-3 py-1.5 text-t-muted">{u.days_active}</td>
                              <td className="px-3 py-1.5">
                                {inactiveDeleting && inactiveSelectedUids[key] && !deleteResult
                                  ? <Loader2 size={16} className="animate-spin text-t-muted" />
                                  : deleteResult?.status === 'deleted'
                                    ? <CheckCircle2 size={16} className="text-semantic-success" />
                                    : deleteResult?.status === 'failed'
                                      ? <span className="flex items-center gap-1">
                                          <XCircle size={16} className="text-semantic-error flex-shrink-0" />
                                          <span className="text-xs text-semantic-error">{deleteResult.detail}</span>
                                        </span>
                                      : null}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            ))}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-[300px_1fr] gap-4 items-start">

          {/* ════════ LEFT PANEL — dialers + scan + summary + delete ════════ */}
          <div className="sticky top-6 rounded-xl border border-b-subtle bg-surface-card p-4 flex flex-col gap-4">

            <DialerPicker
              selected={dupSelectedDialers}
              onToggle={toggleDupDialer}
              onToggleAll={toggleAllDupDialers}
              allDialerNames={allDialerNames}
              customDialers={customDialers}
              onAddCustomDialer={addCustomDialer}
              onRemoveCustomDialer={removeCustomDialer}
            />

            <p className="text-xs rounded-lg border border-semantic-warning/30 bg-[var(--semantic-warning-bg)] text-t-primary px-3 py-2">
              Scans check every writable folder, not just recent call history — so a
              duplicate with zero calls is still caught as long as it exists in a folder.
              Folder scanning takes a bit longer per dialer as a result.
            </p>

            <button
              onClick={handleScanDuplicates}
              disabled={!canScanDuplicates}
              className={[
                'w-full rounded-xl py-3 text-sm font-bold tracking-wide transition-all',
                canScanDuplicates
                  ? 'bg-semantic-warning text-t-on-primary hover:opacity-90 active:scale-[0.99]'
                  : 'bg-surface-soft text-t-muted cursor-not-allowed',
              ].join(' ')}
            >
              {dupRunning
                ? <span className="flex items-center justify-center gap-2"><Loader2 size={14} className="animate-spin" /> Scanning…</span>
                : 'Scan for Duplicates'}
            </button>

            {dupResults.length > 0 && (
              <>
                <div className="border-t border-b-subtle" />
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-t-muted uppercase tracking-wide">Summary</p>
                  <div className="rounded-lg border border-b-subtle bg-surface-soft p-3 space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-t-muted">Duplicate names</span>
                      <span className="font-semibold text-t-primary">
                        {dupResults.reduce((n, r) => n + r.groups.length, 0)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-t-muted">Delete candidates</span>
                      <span className={`font-bold ${dupCandidateCount > 0 ? 'text-semantic-error' : 'text-t-muted'}`}>
                        {dupCandidateCount}
                      </span>
                    </div>
                    {dupResults.some(r => r.status === 'failed') && (
                      <div className="border-t border-b-subtle pt-2 text-xs text-semantic-error">
                        {dupResults.filter(r => r.status === 'failed').length} dialer(s) failed to scan — see right panel.
                      </div>
                    )}
                  </div>
                </div>

                <button
                  onClick={handleDeleteDuplicates}
                  disabled={dupSelectedCount === 0 || dupDeleting}
                  className={[
                    'w-full rounded-xl py-3 text-sm font-bold tracking-wide transition-all',
                    dupSelectedCount > 0 && !dupDeleting
                      ? 'bg-semantic-error text-t-on-primary hover:opacity-90 active:scale-[0.99]'
                      : 'bg-surface-soft text-t-muted cursor-not-allowed',
                  ].join(' ')}
                >
                  {dupDeleting
                    ? <span className="flex items-center justify-center gap-2"><Loader2 size={14} className="animate-spin" /> Deleting…</span>
                    : `Delete ${dupSelectedCount || ''} selected duplicate${dupSelectedCount === 1 ? '' : 's'}`}
                </button>
              </>
            )}
          </div>

          {/* ════════ RIGHT PANEL — per-dialer duplicate groups ════════ */}
          <div className="flex flex-col gap-4">
            {dupResults.length === 0 && !dupRunning && (
              <section className="rounded-xl border border-b-subtle bg-surface-card p-8 text-center text-sm text-t-muted">
                Pick dialers and scan to see which names are duplicated.
              </section>
            )}

            {sortedDupResults.map(r => (
              <section key={r.dialer} className="rounded-xl border border-b-subtle bg-surface-card overflow-hidden">
                <div className="px-4 py-3 border-b border-b-subtle flex items-center justify-between">
                  <span className="text-sm font-semibold text-t-primary">{r.dialer}</span>
                  {r.status === 'ok' && (
                    <span className="text-xs text-t-muted">
                      {r.groups.length} duplicate name{r.groups.length === 1 ? '' : 's'}
                    </span>
                  )}
                </div>

                {r.status === 'failed' ? (
                  <p className="px-4 py-3 text-sm text-semantic-error">{r.detail || 'Scan failed on this dialer.'}</p>
                ) : r.groups.length === 0 ? (
                  <p className="px-4 py-3 text-sm text-t-muted">
                    No duplicates found on {r.dialer}, across recent call history and every writable folder.
                  </p>
                ) : (
                  <div className="overflow-x-auto max-h-80 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-surface-soft">
                        <tr>
                          {['', 'Name', 'uid', 'Folder', 'Role', 'Status'].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-semibold text-t-muted">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {r.groups.map(g => g.accounts.map((a, ai) => {
                          const key = `${r.dialer}:${a.uid}`
                          const deleteResult = dupDeleteResults.find(dr => dr.uid === a.uid && dr.dialer === r.dialer)
                          return (
                            <tr key={key} className={`border-t border-b-subtle hover:bg-surface-soft ${ai === 0 ? 'border-t-2 border-t-b-medium' : ''}`}>
                              <td className="px-3 py-1.5">
                                {a.role === 'delete_candidate' && (
                                  <input
                                    type="checkbox"
                                    checked={!!dupSelectedUids[key]}
                                    onChange={e => setDupSelectedUids(prev => ({ ...prev, [key]: e.target.checked }))}
                                    className="w-4 h-4 accent-semantic-error"
                                  />
                                )}
                              </td>
                              <td className="px-3 py-1.5 text-t-primary">{g.name}</td>
                              <td className="px-3 py-1.5 font-mono text-t-secondary">{a.uid}</td>
                              <td className="px-3 py-1.5 text-t-muted">{a.folder || '—'}</td>
                              <td className="px-3 py-1.5">
                                {a.role === 'keep'
                                  ? <span className="text-xs font-semibold text-semantic-success">Keep (oldest)</span>
                                  : <span className="text-xs font-semibold text-semantic-error">Delete candidate</span>}
                              </td>
                              <td className="px-3 py-1.5">
                                {dupDeleting && a.role === 'delete_candidate' && dupSelectedUids[key] && !deleteResult
                                  ? <Loader2 size={16} className="animate-spin text-t-muted" />
                                  : deleteResult?.status === 'deleted'
                                    ? <CheckCircle2 size={16} className="text-semantic-success" />
                                    : deleteResult?.status === 'failed'
                                      ? <span className="flex items-center gap-1">
                                          <XCircle size={16} className="text-semantic-error flex-shrink-0" />
                                          <span className="text-xs text-semantic-error">{deleteResult.detail}</span>
                                        </span>
                                      : null}
                              </td>
                            </tr>
                          )
                        }))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
