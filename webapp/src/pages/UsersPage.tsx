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

export function UsersPage() {
  const token = useAuthStore((s) => s.token)

  // ── Form state ──────────────────────────────────────────────────────────────
  const [selectedDialers, setSelectedDialers] = useState<string[]>(['resva'])
  const [folder, setFolder] = useState('Agents')
  const [ou, setOu] = useState('4')
  const [namesText, setNamesText] = useState('')
  const [loginIdsText, setLoginIdsText] = useState('')
  const [passwordsText, setPasswordsText] = useState('')
  const [copied, setCopied] = useState(false)

  // ── Running state ───────────────────────────────────────────────────────────
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<ResultRow[]>([])

  // ── Derived preview ─────────────────────────────────────────────────────────
  const names = useMemo(() =>
    namesText.split('\n').map(s => s.trim()).filter(Boolean), [namesText])
  const loginIds = useMemo(() =>
    loginIdsText.split('\n').map(s => s.trim()).filter(Boolean), [loginIdsText])
  const passwords = useMemo(() =>
    passwordsText.split('\n').map(s => s.trim()).filter(Boolean), [passwordsText])

  // ── Auto-generate passwords when name count changes ──────────────────────────
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

  // ── Copy handler ─────────────────────────────────────────────────────────────
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

  // ── Create ──────────────────────────────────────────────────────────────────
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
    } catch (e: any) {
      setResults(prev => [...prev, { name: '—', login_id: '—', dialer: 'all', status: 'failed', detail: `Connection error: ${(e as Error).message}` }])
    } finally {
      setRunning(false)
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-5 p-6">

      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-t-primary">Create Dialer Users</h1>
        <p className="text-sm text-t-muted mt-0.5">
          Paste names &amp; login IDs, pick dialers, create all accounts in one click.
        </p>
      </div>

      {/* ── Two-panel grid ── */}
      <div className="grid grid-cols-[300px_1fr] gap-4 items-start">

        {/* ════════════════════════════════════════
            LEFT PANEL — config + summary + create
        ════════════════════════════════════════ */}
        <div className="sticky top-6 rounded-xl border border-b-subtle bg-surface-card p-4 flex flex-col gap-4">

          {/* Dialers */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">Dialers</label>
            <div ref={dialerRef} className="relative">
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
                <svg className={`w-4 h-4 text-t-muted transition-transform flex-shrink-0 ${dialerOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {dialerOpen && (
                <div className="absolute z-50 mt-1 w-full rounded-xl border border-b-medium bg-surface-card shadow-card overflow-hidden">
                  <div className="p-2 border-b border-b-subtle">
                    <input
                      autoFocus
                      value={dialerSearch}
                      onChange={e => setDialerSearch(e.target.value)}
                      placeholder="Search…"
                      className="w-full rounded-lg border border-b-medium bg-surface-soft px-3 py-2 text-sm text-t-primary placeholder:text-t-muted focus:outline-none focus:border-accent transition-colors"
                    />
                  </div>
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
                  <div className="max-h-48 overflow-y-auto">
                    {filteredDialers.map(d => {
                      const checked  = selectedDialers.includes(d)
                      const isCustom = d in customDialers
                      return (
                        <div key={d} className={`flex items-center transition-colors ${checked ? 'bg-[var(--selected-bg)]' : 'hover:bg-surface-soft'}`}>
                          <button
                            type="button"
                            onClick={() => toggleDialer(d)}
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
                  <div className="border-t border-b-medium bg-surface-soft p-3 space-y-2">
                    <p className="text-[11px] font-semibold text-t-secondary uppercase tracking-wide">Add dialer</p>
                    <div className="flex gap-2">
                      <input
                        value={newDialerName}
                        onChange={e => setNewDialerName(e.target.value)}
                        placeholder="Name"
                        className="w-24 rounded-lg border border-b-medium bg-surface-card px-2 py-1.5 text-xs text-t-primary placeholder:text-t-placeholder focus:outline-none focus:border-accent transition-colors"
                      />
                      <input
                        value={newDialerUrl}
                        onChange={e => setNewDialerUrl(e.target.value)}
                        placeholder="https://…readymode.com/"
                        className="flex-1 min-w-0 rounded-lg border border-b-medium bg-surface-card px-2 py-1.5 text-xs text-t-primary placeholder:text-t-placeholder focus:outline-none focus:border-accent transition-colors"
                      />
                      <button
                        type="button"
                        onClick={addCustomDialer}
                        disabled={!newDialerName.trim() || !newDialerUrl.trim()}
                        className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-accent text-t-on-primary disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
                      >Add</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
            {selectedDialers.length === 0 && (
              <p className="text-xs text-semantic-error">Select at least one dialer.</p>
            )}
          </div>

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

          {/* Divider */}
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

          {/* Create button */}
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

        {/* ════════════════════════════════════════
            RIGHT PANEL — user data + preview table
        ════════════════════════════════════════ */}
        <div className="flex flex-col gap-4">

          {/* Textareas */}
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

          {/* Preview table */}
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
    </div>
  )
}
