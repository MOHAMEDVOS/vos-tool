import { useState, useMemo, useRef, useEffect } from 'react'
import { useAuthStore } from '@/store/authStore'
import { READYMODE_DIALER_URLS } from '@/api/readymode'

// ── Folder & Role option maps (from ReadyMode HTML) ──────────────────────────
const FOLDER_OPTIONS = [
  { value: '46-33-2',    label: 'Admin' },
  { value: '48-36-14',  label: 'Agents' },
  { value: '55-1570-14',label: 'Client A' },
  { value: '57-3772-',  label: 'Delegates' },
  { value: '54-null-2', label: 'Spanish Speakers' },
  { value: '56-3667-20',label: 'Team Leaders' },
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

export function UsersPage() {
  const token = useAuthStore((s) => s.token)

  // ── Form state ──────────────────────────────────────────────────────────────
  const [selectedDialers, setSelectedDialers] = useState<string[]>(['resva'])
  const [folder, setFolder] = useState('48-36-14')
  const [ou, setOu] = useState('4')
  const [namesText, setNamesText] = useState('')
  const [loginIdsText, setLoginIdsText] = useState('')
  const [passwordsText, setPasswordsText] = useState('')

  const [copied, setCopied] = useState(false)

  // ── Auto-generate passwords when name count changes ──────────────────────────
  useEffect(() => {
    if (names.length === 0) return
    const current = passwordsText.split('\n').map(s => s.trim())
    const next = names.map((_, i) => current[i] || generatePassword())
    if (next.join('\n') !== passwordsText) setPasswordsText(next.join('\n'))
  }, [names.length]) // eslint-disable-line react-hooks/exhaustive-deps

  const regenerateAll = () => setPasswordsText(names.map(() => generatePassword()).join('\n'))

  // ── Running state ───────────────────────────────────────────────────────────
  const [running, setRunning] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [results, setResults] = useState<ResultRow[]>([])

  // ── Derived preview ─────────────────────────────────────────────────────────
  const names = useMemo(() =>
    namesText.split('\n').map(s => s.trim()).filter(Boolean), [namesText])
  const loginIds = useMemo(() =>
    loginIdsText.split('\n').map(s => s.trim()).filter(Boolean), [loginIdsText])
  const passwords = useMemo(() =>
    passwordsText.split('\n').map(s => s.trim()).filter(Boolean), [passwordsText])

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

  // ── Custom dialers (persisted to localStorage) ──────────────────────────────
  const [customDialers, setCustomDialers] = useState<Record<string, string>>(loadCustomDialers)
  const [newDialerName, setNewDialerName] = useState('')
  const [newDialerUrl, setNewDialerUrl]   = useState('')

  const allDialerUrls  = { ...READYMODE_DIALER_URLS, ...customDialers }
  const allDialerNames = Object.keys(allDialerUrls)

  const saveCustomDialers = (next: Record<string, string>) => {
    setCustomDialers(next)
    localStorage.setItem(LS_KEY, JSON.stringify(next))
  }

  const addCustomDialer = () => {
    const name = newDialerName.trim()
    let url = newDialerUrl.trim()
    if (!name || !url) return
    if (!url.endsWith('/')) url += '/'
    saveCustomDialers({ ...customDialers, [name]: url })
    setNewDialerName('')
    setNewDialerUrl('')
  }

  const removeCustomDialer = (name: string) => {
    const next = { ...customDialers }
    delete next[name]
    saveCustomDialers(next)
    setSelectedDialers(prev => prev.filter(d => d !== name))
  }

  // ── Dialer dropdown ─────────────────────────────────────────────────────────
  const [dialerOpen, setDialerOpen] = useState(false)
  const [dialerSearch, setDialerSearch] = useState('')
  const dialerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dialerRef.current && !dialerRef.current.contains(e.target as Node)) {
        setDialerOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filteredDialers = allDialerNames.filter(d =>
    d.toLowerCase().includes(dialerSearch.toLowerCase()))

  const toggleDialer = (d: string) =>
    setSelectedDialers(prev =>
      prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d])

  const allSelected = selectedDialers.length === allDialerNames.length
  const toggleAll = () =>
    setSelectedDialers(allSelected ? [] : [...allDialerNames])

  // ── Create ──────────────────────────────────────────────────────────────────
  const handleCreate = async () => {
    setRunning(true)
    setLogs([])
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
            if (event === 'log') setLogs(prev => [...prev, data])
            if (event === 'done') setResults(data as ResultRow[])
            if (event === 'error') setLogs(prev => [...prev, `ERROR: ${data}`])
          } catch { /* ignore malformed SSE */ }
        }
      }
    } catch (e: any) {
      setLogs(prev => [...prev, `Connection error: ${e.message}`])
    } finally {
      setRunning(false)
    }
  }

  // ── Stats ───────────────────────────────────────────────────────────────────
  const created = results.filter(r => r.status === 'created').length
  const failed  = results.filter(r => r.status === 'failed').length

  return (
    <div className="flex flex-col gap-6 p-6 max-w-5xl mx-auto">
      <div>
        <h1 className="text-xl font-bold text-t-primary">Create Dialer Users</h1>
        <p className="text-sm text-t-muted mt-0.5">
          Paste names &amp; passwords, pick dialers, create all accounts in one click.
        </p>
      </div>

      {/* ── Dialers ── */}
      <section className="rounded-xl border border-b-subtle bg-surface-card p-4 space-y-2">
        <span className="text-sm font-semibold text-t-primary">Dialers</span>
        <div ref={dialerRef} className="relative">
          {/* Trigger */}
          <button
            type="button"
            onClick={() => setDialerOpen(o => !o)}
            className="w-full flex items-center justify-between rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary hover:border-accent focus:outline-none focus:border-accent transition-colors"
          >
            <span className={selectedDialers.length === 0 ? 'text-t-muted' : ''}>
              {selectedDialers.length === 0
                ? 'Select dialers…'
                : selectedDialers.length === allDialerNames.length
                  ? 'All dialers selected'
                  : selectedDialers.join(', ')}
            </span>
            <svg className={`w-4 h-4 text-t-muted transition-transform ${dialerOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Dropdown panel */}
          {dialerOpen && (
            <div className="absolute z-50 mt-1 w-full rounded-xl border border-b-medium bg-surface-card shadow-card overflow-hidden">
              {/* Search */}
              <div className="p-2 border-b border-b-subtle">
                <input
                  autoFocus
                  value={dialerSearch}
                  onChange={e => setDialerSearch(e.target.value)}
                  placeholder="Search…"
                  className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary placeholder:text-t-muted focus:outline-none focus:border-accent"
                />
              </div>
              {/* Select All */}
              <button
                type="button"
                onClick={toggleAll}
                className="w-full flex items-center gap-3 px-4 py-3 text-sm text-t-primary hover:bg-surface-soft transition-colors border-b border-b-subtle"
              >
                <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${allSelected ? 'bg-accent border-accent' : 'border-b-medium bg-surface-soft'}`}>
                  {allSelected && <svg className="w-3 h-3 text-t-on-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                </span>
                <span className="font-semibold">Select all</span>
              </button>
              {/* Options */}
              <div className="max-h-52 overflow-y-auto">
                {filteredDialers.map(d => {
                  const checked   = selectedDialers.includes(d)
                  const isCustom  = d in customDialers
                  return (
                    <div key={d} className="flex items-center hover:bg-surface-soft transition-colors">
                      <button
                        type="button"
                        onClick={() => toggleDialer(d)}
                        className="flex-1 flex items-center gap-3 px-4 py-3 text-sm text-t-primary"
                      >
                        <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${checked ? 'bg-accent border-accent' : 'border-b-medium bg-surface-soft'}`}>
                          {checked && <svg className="w-3 h-3 text-t-on-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                        </span>
                        <span>{d}</span>
                        {isCustom && <span className="ml-auto text-xs text-t-muted font-mono pr-1">{customDialers[d]}</span>}
                      </button>
                      {isCustom && (
                        <button
                          type="button"
                          onClick={() => removeCustomDialer(d)}
                          className="pr-4 text-t-muted hover:text-semantic-error transition-colors text-lg leading-none"
                          title="Remove dialer"
                        >×</button>
                      )}
                    </div>
                  )
                })}
                {filteredDialers.length === 0 && (
                  <p className="px-4 py-3 text-sm text-t-muted">No dialers match.</p>
                )}
              </div>

              {/* Add dialer */}
              <div className="border-t border-b-subtle p-3 space-y-2">
                <p className="text-xs font-semibold text-t-muted uppercase tracking-wide">Add dialer</p>
                <div className="flex gap-2">
                  <input
                    value={newDialerName}
                    onChange={e => setNewDialerName(e.target.value)}
                    placeholder="Name (e.g. resva3)"
                    className="w-28 rounded-lg border border-b-subtle bg-surface-soft px-2 py-1.5 text-xs text-t-primary placeholder:text-t-muted focus:outline-none focus:border-accent"
                  />
                  <input
                    value={newDialerUrl}
                    onChange={e => setNewDialerUrl(e.target.value)}
                    placeholder="https://resva3.readymode.com/"
                    className="flex-1 rounded-lg border border-b-subtle bg-surface-soft px-2 py-1.5 text-xs text-t-primary placeholder:text-t-muted focus:outline-none focus:border-accent"
                  />
                  <button
                    type="button"
                    onClick={addCustomDialer}
                    disabled={!newDialerName.trim() || !newDialerUrl.trim()}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-accent text-t-on-primary disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
                  >Add</button>
                </div>
              </div>
            </div>
          )}
        </div>
        {selectedDialers.length === 0 && (
          <p className="text-xs text-semantic-error">Select at least one dialer.</p>
        )}
      </section>

      {/* ── Role & Folder ── */}
      <section className="rounded-xl border border-b-subtle bg-surface-card p-4 grid grid-cols-2 gap-4">
        <div className="space-y-1">
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
        <div className="space-y-1">
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
      </section>

      {/* ── Paste boxes ── */}
      <section className="rounded-xl border border-b-subtle bg-surface-card p-4 space-y-3">
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">
              Agent Names <span className="normal-case font-normal">(one per line)</span>
            </label>
            <textarea
              value={namesText}
              onChange={e => setNamesText(e.target.value)}
              rows={8}
              placeholder={"Ahmed Hassan\nSara Mohamed\nKhaled Ali"}
              className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent resize-none font-mono"
            />
            <p className="text-xs text-t-muted">{names.length} names</p>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">
              Login IDs <span className="normal-case font-normal">(one per line, same order)</span>
            </label>
            <textarea
              value={loginIdsText}
              onChange={e => setLoginIdsText(e.target.value)}
              rows={8}
              placeholder={"RES-014\nRES-015\nRES-016"}
              className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-2 text-sm text-t-primary focus:outline-none focus:border-accent resize-none font-mono"
            />
            <p className="text-xs text-t-muted">{loginIds.length} login IDs</p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">
                Passwords <span className="normal-case font-normal">(auto-generated)</span>
              </label>
              <button
                type="button"
                onClick={regenerateAll}
                disabled={names.length === 0}
                className="text-xs font-semibold text-accent hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Regenerate All
              </button>
            </div>
            <textarea
              value={passwordsText}
              onChange={e => setPasswordsText(e.target.value)}
              rows={8}
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

      {/* ── Preview table ── */}
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
                onClick={() => {
                  const header = 'Name\tLogin ID\tPassword'
                  const rows = preview.map(r => `${r.name}\t${r.login_id}\t${r.password}`).join('\n')
                  navigator.clipboard.writeText(`${header}\n${rows}`)
                  setCopied(true)
                  setTimeout(() => setCopied(false), 2000)
                }}
                className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg border border-b-medium bg-surface-soft text-t-primary hover:border-accent hover:text-accent transition-colors"
              >
                {copied ? '✓ Copied' : '⎘ Copy'}
              </button>
            </div>
          </div>
          <div className="overflow-x-auto max-h-56 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-surface-soft">
                <tr>
                  {['Name', 'Login ID', 'Password', 'Folder', 'Role'].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-semibold text-t-muted">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.map((row, i) => (
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ── Create button ── */}
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
          ? 'Creating...'
          : `Create ${preview.length * selectedDialers.length} accounts on ${selectedDialers.length} dialer${selectedDialers.length !== 1 ? 's' : ''}`}
      </button>

      {/* ── Live logs ── */}
      {(logs.length > 0 || running) && (
        <section className="rounded-xl border border-b-subtle bg-surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-b-subtle flex items-center justify-between">
            <span className="text-sm font-semibold text-t-primary">Live Results</span>
            {results.length > 0 && (
              <span className="text-xs">
                <span className="text-green-500 font-bold">{created} created</span>
                {failed > 0 && <span className="text-semantic-error font-bold ml-2">{failed} failed</span>}
              </span>
            )}
          </div>
          <div className="p-4 space-y-1 max-h-72 overflow-y-auto font-mono text-xs">
            {logs.map((l, i) => {
              const isCreated = l.startsWith('CREATED')
              const isFailed  = l.startsWith('FAILED') || l.startsWith('ERROR')
              return (
                <p key={i} className={
                  isCreated ? 'text-green-500' :
                  isFailed  ? 'text-semantic-error' :
                  'text-t-muted'
                }>
                  {l}
                </p>
              )
            })}
            {running && (
              <p className="text-t-muted animate-pulse">Running...</p>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
