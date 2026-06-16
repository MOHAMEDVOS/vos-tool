import { useState, useMemo } from 'react'
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

const DIALER_NAMES = Object.keys(READYMODE_DIALER_URLS)

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

  // ── Dialer toggle ───────────────────────────────────────────────────────────
  const toggleDialer = (d: string) =>
    setSelectedDialers(prev =>
      prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d])

  const allSelected = selectedDialers.length === DIALER_NAMES.length
  const toggleAll = () =>
    setSelectedDialers(allSelected ? [] : [...DIALER_NAMES])

  // ── Create ──────────────────────────────────────────────────────────────────
  const handleCreate = async () => {
    setRunning(true)
    setLogs([])
    setResults([])

    const body = {
      dialer_urls: selectedDialers.map(d => READYMODE_DIALER_URLS[d]),
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
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-t-primary">
            Dialers
            <span className="ml-1 text-xs font-normal text-t-muted">(hold Ctrl / Cmd to select multiple)</span>
          </label>
          <button
            onClick={toggleAll}
            className="text-xs font-semibold text-accent hover:underline"
          >
            {allSelected ? 'Deselect All' : 'Select All'}
          </button>
        </div>
        <select
          multiple
          value={selectedDialers}
          onChange={e => setSelectedDialers(Array.from(e.target.selectedOptions, o => o.value))}
          className="w-full rounded-lg border border-b-subtle bg-surface-soft px-3 py-1 text-sm text-t-primary focus:outline-none focus:border-accent"
          size={DIALER_NAMES.length}
        >
          {DIALER_NAMES.map(d => (
            <option key={d} value={d} className="py-1.5 px-1 cursor-pointer">
              {d}
            </option>
          ))}
        </select>
        {selectedDialers.length === 0 && (
          <p className="text-xs text-semantic-error">Select at least one dialer.</p>
        )}
        {selectedDialers.length > 0 && (
          <p className="text-xs text-t-muted">{selectedDialers.length} dialer{selectedDialers.length !== 1 ? 's' : ''} selected: {selectedDialers.join(', ')}</p>
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
            <label className="text-xs font-semibold text-t-muted uppercase tracking-wide">
              Passwords <span className="normal-case font-normal">(one per line, same order)</span>
            </label>
            <textarea
              value={passwordsText}
              onChange={e => setPasswordsText(e.target.value)}
              rows={8}
              placeholder={"Xp!9kwQ2\nMn@4rTz8\nQw#7vLp3"}
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
            <span className="text-xs text-t-muted">
              {preview.length} users × {selectedDialers.length} dialer{selectedDialers.length !== 1 ? 's' : ''} ={' '}
              <span className="font-bold text-t-primary">{preview.length * selectedDialers.length} accounts</span>
            </span>
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
                    <td className="px-3 py-1.5 font-mono text-t-muted">
                      {row.password ? '••••••••' : <span className="text-semantic-error">missing</span>}
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
            ? 'bg-accent text-white hover:opacity-90 active:scale-[0.99]'
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
