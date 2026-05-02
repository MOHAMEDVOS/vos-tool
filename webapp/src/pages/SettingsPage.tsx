import React, { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { 
  RefreshCw, Trash2, Shield, UserPlus, Users, Activity, 
  Settings2, Minus, Plus, Search, Info, ChevronRight, ChevronDown,
  LayoutDashboard, Database, Key, Home,
  Lock, Share2, Server, Check, AlertCircle
} from 'lucide-react'
import { quotaApi } from '@/api/quota'
import { settingsApi } from '@/api/settings'
import { systemApi } from '@/api/system'
import { sharingApi } from '@/api/sharing'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Metric } from '@/components/ui/Metric'
import { Spinner } from '@/components/ui/Spinner'
import { CustomSelect } from '@/components/ui/Select'
import type { AppConfigCategory } from '@/types/api'
import { motion, AnimatePresence } from 'framer-motion'

type NavItem  = { id: string; label: string; forRoles?: string[] }
type NavGroup = { id: string; label: string; icon: any; forRoles?: string[]; items: NavItem[] }

// forRoles: undefined = all roles with settings access; otherwise restrict to listed roles
const SIDEBAR_NAV: NavGroup[] = [
  {
    id: 'system_group',
    label: 'System',
    icon: Server,
    items: [
      { id: 'quota_control',   label: 'Quota Control',   forRoles: ['Owner'] },
      { id: 'admin_quota',     label: 'Quota Dashboard', forRoles: ['Admin'] },
      { id: 'system_health',   label: 'System Health',   forRoles: ['Owner'] },
      { id: 'app_config',      label: 'App Config',      forRoles: ['Owner'] },
    ]
  },
  {
    id: 'users_group',
    label: 'Users',
    icon: Shield,
    items: [
      { id: 'user_overview',      label: 'User Overview' },
      { id: 'user_create',        label: 'Create User' },
      { id: 'admin_manage_users', label: 'Manage Users',  forRoles: ['Admin'] },
      { id: 'user_edit',          label: 'Edit User',     forRoles: ['Owner'] },
      { id: 'user_sessions',      label: 'Sessions',      forRoles: ['Owner'] },
    ]
  },
  {
    id: 'sharing_group',
    label: 'Sharing',
    icon: Share2,
    forRoles: ['Owner'],
    items: [
      { id: 'dashboard_sharing', label: 'Dashboard Sharing' },
    ]
  }
]

export function SettingsPage() {
  const role = useAuthStore((s) => s.role)
  const [active, setActive] = useState('user_overview')
  const [expanded, setExpanded] = useState<string[]>(['users_group', 'system_group', 'sharing_group'])

  const toggleExpand = (id: string) => {
    setExpanded(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id])
  }

  const filteredNav = useMemo(() => {
    if (!role || role === 'Auditor') return []
    return SIDEBAR_NAV
      .filter(g => !g.forRoles || g.forRoles.includes(role))
      .map(g => ({
        ...g,
        items: g.items.filter(i => !i.forRoles || i.forRoles.includes(role))
      }))
      .filter(g => g.items.length > 0)
  }, [role])

  return (
    <div className="flex flex-col w-full h-full px-12 py-16">
      <div className="grid grid-cols-[280px_1fr] gap-24 items-start max-w-[1700px] mx-auto w-full">
        {/* Refined Sidebar */}
        <aside className="sticky top-0 flex flex-col gap-1 pr-4">
          {filteredNav.map((group) => (
            <div key={group.id} className="flex flex-col">
              <button
                onClick={() => toggleExpand(group.id)}
                className="flex items-center justify-between w-full px-4 py-3.5 rounded-xl hover:bg-c-raised/50 transition-all group"
              >
                <div className="flex items-center gap-3">
                  <group.icon size={18} className="text-vos-500 group-hover:text-t-primary transition-colors" />
                  <span className="text-[12px] font-black uppercase tracking-[0.1em] text-vos-400 group-hover:text-t-primary">{group.label}</span>
                </div>
                <ChevronDown 
                  size={12} 
                  className={`text-vos-600 transition-transform duration-300 ${expanded.includes(group.id) ? '' : '-rotate-90'}`} 
                />
              </button>

              <AnimatePresence initial={false}>
                {expanded.includes(group.id) && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden relative"
                  >
                    <div className="absolute left-6 top-0 bottom-4 w-[1px] bg-b-subtle" />
                    <div className="flex flex-col gap-0.5 py-1 ml-6 pl-5">
                      {group.items.map((item) => (
                        <button
                          key={item.id}
                          onClick={() => setActive(item.id)}
                          className={`
                            group flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all relative
                            ${active === item.id 
                              ? 'text-t-primary' 
                              : 'text-vos-500 hover:text-vos-200'}
                          `}
                        >
                          <div className={`w-1.5 h-1.5 rounded-full border border-b-medium transition-all ${active === item.id ? 'bg-ship-red border-ship-red shadow-[0_0_8px_rgba(239,68,68,0.4)] scale-110' : 'bg-transparent group-hover:border-b-medium'}`} />
                          <span className={`text-[11px] font-bold tracking-tight ${active === item.id ? 'translate-x-1' : 'group-hover:translate-x-1'} transition-transform`}>{item.label}</span>
                          {active === item.id && (
                            <motion.div 
                              layoutId="nav-pill"
                              className="absolute inset-0 bg-c-raised/50 rounded-lg -z-10" 
                            />
                          )}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </aside>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto custom-scrollbar">
          <AnimatePresence mode="wait">
            <motion.div
              key={active}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col gap-16 pb-24 px-8"
            >
              {active === 'user_overview' && <ManageUsers />}
              {active === 'user_create' && <CreateUser />}
              {active === 'user_edit' && <EditUser />}
              {active === 'user_sessions' && <UserSessions />}
              {active === 'admin_manage_users' && <AdminManageUsers />}

              {active === 'quota_control' && <QuotaSettings />}
              {active === 'admin_quota' && <AdminQuotaDashboard />}
              {active === 'system_health' && <SystemHealth />}
              {active === 'app_config' && <AppConfig />}
              {active === 'dashboard_sharing' && <SharingSettings />}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}


function UserSessions() {
  const qc = useQueryClient()
  const sessions = useQuery({ queryKey: ['active-sessions'], queryFn: systemApi.sessions })
  const invalidate = useMutation({
    mutationFn: systemApi.invalidateSession,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['active-sessions'] }),
  })

  return (
    <div className="flex flex-col gap-8">
       <div className="flex flex-col gap-2 text-center">
        <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase">Active Sessions</h2>
        <p className="text-vos-500 text-[10px] font-black uppercase tracking-[0.2em] opacity-50">Authorized system entry points</p>
      </div>

      <Card className="p-0 overflow-hidden bg-c-base border-b-subtle rounded-2xl shadow-3xl w-full max-w-5xl mx-auto">
        <div className="px-6 py-4 border-b border-b-subtle flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity size={14} className="text-vos-500" />
            <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-vos-600">Session Registry</h2>
          </div>
          <Button size="sm" variant="secondary" className="h-8 bg-vos-50" onClick={() => sessions.refetch()}>
            <RefreshCw size={12} className="mr-2" /> REFRESH
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[11px]">
            <thead className="bg-surface-page border-b border-b-subtle">
              <tr>
                <th className="px-6 py-4 text-[8px] font-black uppercase tracking-[0.3em] text-vos-700">Account</th>
                <th className="px-6 py-4 text-[8px] font-black uppercase tracking-[0.3em] text-vos-700">Session ID</th>
                <th className="px-6 py-4 text-[8px] font-black uppercase tracking-[0.3em] text-vos-700">Last Pulse</th>
                <th className="px-6 py-4" />
              </tr>
            </thead>
            <tbody className="divide-y divide-b-subtle">
              {(sessions.data ?? []).map((s, i) => (
                <tr key={`${s.username}-${i}`} className="group hover:bg-c-raised/30 transition-all">
                  <td className="px-6 py-4 font-bold text-t-primary">{s.username ?? '-'}</td>
                  <td className="px-6 py-4 font-mono text-vos-500 text-[10px] max-w-xs truncate">{s.session_id ?? '-'}</td>
                  <td className="px-6 py-4 text-vos-600">{s.last_activity ?? '-'}</td>
                  <td className="px-6 py-4 text-right">
                    {s.username && (
                      <Button 
                        variant="action"
                        size="sm"
                        onClick={() => { if(confirm(`Invalidate session for ${s.username}?`)) invalidate.mutate(String(s.username)) }}
                        disabled={invalidate.isPending}
                      >
                        Kick
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function CreateUser() {
  const qc = useQueryClient()
  const callerRole = useAuthStore((s) => s.role)
  const roleOptions = callerRole === 'Owner' ? ['Auditor', 'Admin'] : ['Auditor']
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [rmUsername, setRmUsername] = useState('')
  const [rmPassword, setRmPassword] = useState('')
  const [newRole, setNewRole] = useState('Auditor')
  const [dailyLimit, setDailyLimit] = useState<string | number>('')

  const create = useMutation({
    mutationFn: () => settingsApi.createUser({
      username,
      role: newRole,
      daily_limit: Number(dailyLimit) || 0,
      readymode_username: rmUsername || undefined,
      readymode_password: rmPassword || undefined,
    }),
    onSuccess: () => {
      setUsername(''); setRmUsername(''); setRmPassword(''); setDailyLimit('')
      qc.invalidateQueries({ queryKey: ['settings-users'] })
    },
  })

  return (
    <div className="flex flex-col gap-10 items-center">
      <div className="flex flex-col gap-2 text-center">
        <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase">Provision User</h2>
        <p className="text-vos-500 text-[10px] font-black uppercase tracking-[0.2em] opacity-50">Configure system-level credentials</p>
      </div>

      <Card className="bg-c-base border-b-subtle p-10 rounded-2xl shadow-3xl w-full max-w-4xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <Input label="EMAIL ADDRESS" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="user@example.com" autoComplete="off" />
          <Input label="READYMODE USERNAME" value={rmUsername} onChange={(e) => setRmUsername(e.target.value)} placeholder="Integration ID" autoComplete="off" />
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-black uppercase tracking-[0.2em] text-vos-600 mb-1">Access Tier</label>
            <CustomSelect options={roleOptions} value={newRole} onChange={setNewRole} className="h-12" />
          </div>
          <Input label="DAILY LIMIT" type="number" value={dailyLimit} onChange={(e) => setDailyLimit(e.target.value)} placeholder="0" />
          <Input label="READYMODE PASSWORD" type="password" value={rmPassword} onChange={(e) => setRmPassword(e.target.value)} placeholder="Enter password" autoComplete="new-password" />
        </div>

        <div className="flex justify-end mt-10">
          <Button 
            variant="action"
            className="px-12 py-4 bg-[var(--btn-heavy-bg)] text-[var(--btn-heavy-text)] hover:bg-[var(--btn-heavy-hover)]" 
            onClick={() => create.mutate()} 
            disabled={!username || create.isPending}
          >
            Finalize Provisioning
          </Button>
        </div>
      </Card>
    </div>
  )
}

function EditUser() {
  const qc = useQueryClient()
  const { data: userData } = useQuery({ queryKey: ['settings-users'], queryFn: settingsApi.users })
  const [selectedUser, setSelectedUser] = useState('')
  const [newRole, setNewRole] = useState('Auditor')
  const [appPassword, setAppPassword] = useState('')
  const [rmUsername, setRmUsername] = useState('')
  const [rmPassword, setRmPassword] = useState('')
  const [dailyLimit, setDailyLimit] = useState<string | number>(0)

  const users = userData?.users ?? []
  const userToEdit = users.find(u => u.username === selectedUser)

  useEffect(() => {
    if (userToEdit) {
      setNewRole(userToEdit.role)
      setDailyLimit(userToEdit.daily_limit ?? 0)
      setRmUsername(userToEdit.readymode_username ?? '')
    }
  }, [userToEdit])

  const update = useMutation({
    mutationFn: () => settingsApi.updateUser(selectedUser, {
      role: newRole,
      daily_limit: Number(dailyLimit),
      readymode_username: rmUsername || undefined,
      readymode_password: rmPassword || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings-users'] })
      setRmPassword('')
    },
  })

  // Clear success/error on user change
  useEffect(() => {
    update.reset()
  }, [selectedUser])

  return (
    <div className="flex flex-col gap-10 items-center">
      <div className="flex flex-col gap-1 text-center">
        <h2 className="text-4xl font-black text-t-primary tracking-tighter uppercase">Modify Access</h2>
        <p className="text-vos-500 text-[10px] font-black uppercase tracking-[0.2em]">Update permissions and integration credentials</p>
      </div>

      <div className="flex flex-col gap-8 w-full max-w-5xl">
        <div className="bg-c-base p-6 rounded-2xl border border-b-subtle">
          <label className="text-[9px] font-black uppercase tracking-[0.2em] text-vos-600 mb-3 block">Target Account Selection</label>
          <div className="max-w-2xl">
            <CustomSelect options={users.map(u => u.username)} value={selectedUser} onChange={setSelectedUser} placeholder="Search accounts..." />
          </div>
        </div>

        <AnimatePresence mode="wait">
          {selectedUser ? (
            <motion.div key={selectedUser} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="flex flex-col gap-8">
              <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-10">
                <div className="flex flex-col gap-6">
                  <h5 className="text-[9px] font-black uppercase tracking-[0.3em] text-vos-500">Profile Snapshot</h5>
                  <div className="grid gap-3">
                    <ProfileField label="Current Role" value={userToEdit?.role} active />
                    <ProfileField label="Current Limit" value={userToEdit?.daily_limit ?? 'Unlimited'} />
                    <ProfileField label="Integration" value={userToEdit?.readymode_username ? 'Linked' : 'None'} />
                  </div>
                </div>

                <Card className="bg-c-base border-b-subtle p-8 rounded-2xl flex flex-col gap-8 shadow-2xl">
                   <div className="flex flex-col gap-1 border-b border-b-subtle pb-4">
                    <h5 className="text-[10px] font-black uppercase tracking-[0.3em] text-vos-400">Account Modifications</h5>
                    {userToEdit?.role === 'Owner' && <p className="text-[9px] text-ship-red/60 font-black uppercase tracking-wider mt-2">Protected Account: API Secrets Only</p>}
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div className="flex flex-col gap-2">
                      <label className="text-[9px] font-black uppercase tracking-[0.2em] text-vos-600">Assign New Role</label>
                      <CustomSelect options={['Auditor', 'Admin', 'Owner']} value={newRole} onChange={setNewRole} />
                    </div>
                    <div className="flex flex-col gap-2">
                      <label className="text-[9px] font-black uppercase tracking-[0.2em] text-vos-600">Quota Adjustment</label>
                      <div className="flex h-[44px] w-full items-center rounded-lg bg-surface-page border border-b-subtle overflow-hidden">
                        <input type="number" value={dailyLimit} onChange={(e) => setDailyLimit(e.target.value)} className="flex-1 bg-transparent px-4 text-xs font-bold text-t-primary outline-none" autoComplete="off" />
                        <div className="flex h-full border-l border-b-subtle">
                          <button type="button" onClick={() => setDailyLimit(Math.max(0, Number(dailyLimit) - 100))} className="flex w-10 items-center justify-center text-vos-500 hover:text-t-primary"><Minus size={14} /></button>
                          <button type="button" onClick={() => setDailyLimit(Number(dailyLimit) + 100)} className="flex w-10 items-center justify-center text-vos-500 hover:text-t-primary border-l border-b-subtle"><Plus size={14} /></button>
                        </div>
                      </div>
                    </div>
                    <Input label="READYMODE USER" value={rmUsername} onChange={(e) => setRmUsername(e.target.value)} placeholder="Update username" autoComplete="off" />
                    <div className="md:col-span-2"><Input label="READYMODE SECRET" type="password" value={rmPassword} onChange={(e) => setRmPassword(e.target.value)} placeholder="Enter password" autoComplete="new-password" /></div>
                  </div>
                  <div className="pt-6 border-t border-b-subtle flex items-center justify-between">
                    <div className="flex-1">
                      {update.isSuccess && (
                        <div className="flex items-center gap-3 text-semantic-success animate-in fade-in slide-in-from-left-4 duration-500">
                          <div className="w-5 h-5 rounded-full bg-semantic-success/10 flex items-center justify-center">
                            <Check size={10} className="stroke-[3]" />
                          </div>
                          <span className="text-[9px] font-black uppercase tracking-widest">Update Successful</span>
                        </div>
                      )}
                      {update.isError && (
                        <div className="flex items-center gap-3 text-ship-red animate-in fade-in slide-in-from-left-4 duration-500">
                          <div className="w-5 h-5 rounded-full bg-ship-red/10 flex items-center justify-center">
                            <AlertCircle size={10} className="stroke-[3]" />
                          </div>
                          <span className="text-[9px] font-black uppercase tracking-widest">Update Failed</span>
                        </div>
                      )}
                    </div>
                    <Button 
                      className="bg-[var(--btn-heavy-bg)] text-[var(--btn-heavy-text)] hover:bg-[var(--btn-heavy-hover)] px-8 py-4 rounded-lg text-[10px] font-black uppercase tracking-[0.2em] transition-all" 
                      onClick={() => update.mutate()} 
                      disabled={update.isPending}
                    >
                      {update.isPending ? "Saving..." : update.isSuccess ? "Changes Committed" : "Commit Changes"}
                    </Button>
                  </div>
                </Card>
              </div>
            </motion.div>
          ) : (
            <div className="py-20 flex flex-col items-center justify-center text-center opacity-10">
              <Shield size={64} className="mb-4" />
              <p className="text-xs font-black uppercase tracking-widest">Select Account</p>
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function ManageUsers() {
  const qc = useQueryClient()
  const role = useAuthStore((s) => s.role)
  const myUsername = useAuthStore((s) => s.username)
  const { data, isLoading, error } = useQuery({ 
    queryKey: ['settings-users'], 
    queryFn: settingsApi.users,
    retry: 1
  })

  const remove = useMutation({
    mutationFn: settingsApi.deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings-users'] }),
  })

  if (isLoading) return <Spinner />

  return (
    <div className="flex flex-col gap-10 items-center">
       <div className="flex flex-col gap-2 text-center">
        <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase text-ship-red">User Termination</h2>
        <p className="text-vos-500 text-[10px] font-black uppercase tracking-[0.2em] opacity-50">Permanently revoke account credentials</p>
      </div>

      <Card className="p-0 overflow-hidden bg-c-base border-b-subtle rounded-2xl shadow-3xl w-full max-w-5xl">
        <div className="px-6 py-4 border-b border-b-subtle bg-ship-red/[0.02] flex items-center justify-between">
          <h2 className="text-[9px] font-black uppercase tracking-[0.3em] text-ship-red/60">Destructive Actions Area</h2>
          <div className="flex items-center gap-2">
            <div className="w-1 h-1 rounded-full bg-ship-red animate-pulse" />
            <span className="text-[8px] font-black uppercase tracking-widest text-vos-600">Master Control Active</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[11px]">
            <thead className="bg-surface-page border-b border-b-subtle">
              <tr>
                <th className="px-6 py-4 text-[8px] font-black uppercase tracking-[0.3em] text-vos-700">Account Email</th>
                <th className="px-6 py-4 text-[8px] font-black uppercase tracking-[0.3em] text-vos-700">Access Level</th>
                <th className="px-6 py-4 text-[8px] font-black uppercase tracking-[0.3em] text-vos-700">Current Quota</th>
                <th className="px-6 py-4" />
              </tr>
            </thead>
            <tbody className="divide-y divide-b-subtle">
              {isLoading ? (
                <tr><td colSpan={4} className="py-20 text-center"><Spinner /></td></tr>
              ) : error ? (
                <tr>
                  <td colSpan={4} className="py-20 text-center">
                    <div className="flex flex-col items-center gap-3 opacity-50">
                      <Shield size={32} className="text-ship-red" />
                      <p className="text-[10px] font-black uppercase tracking-widest">Access Denied or Connection Failed</p>
                      <p className="text-[8px] text-vos-700">{error.message}</p>
                    </div>
                  </td>
                </tr>
              ) : (data?.users ?? []).length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-20 text-center">
                    <div className="flex flex-col items-center gap-3 opacity-20">
                      <Users size={32} />
                      <p className="text-[10px] font-black uppercase tracking-widest">No active users identified</p>
                    </div>
                  </td>
                </tr>
              ) : (data?.users ?? []).map((u) => (
                <tr key={u.username} className="group hover:bg-ship-red/[0.01] transition-all duration-300">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-c-raised/50 border border-b-subtle flex items-center justify-center text-vos-600 font-black text-[10px]">
                        {u.username.substring(0, 2).toUpperCase()}
                      </div>
                      <div className="flex flex-col">
                        <span className="text-t-primary font-bold tracking-tight">{u.username}</span>
                        {u.username === myUsername && <span className="text-[7px] text-ship-red font-black uppercase tracking-widest">Active Session</span>}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <Badge role={u.role}>{u.role}</Badge>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-t-primary font-mono text-[10px]">{u.daily_limit >= 999999 ? '∞' : u.daily_limit?.toLocaleString() ?? '5,000'}</span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    {u.role === 'Owner' ? (
                      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-c-raised/50 border border-b-subtle">
                        <Shield size={10} className="text-vos-700" />
                        <span className="text-[8px] font-black uppercase tracking-widest text-vos-700">Protected</span>
                      </div>
                    ) : (role === 'Owner' || (role === 'Admin' && u.role === 'Auditor')) && u.username !== myUsername ? (
                      <Button 
                        variant="danger"
                        size="sm"
                        onClick={() => { if(confirm(`Confirm permanent deletion of ${u.username}?`)) remove.mutate(u.username) }} 
                        disabled={remove.isPending}
                        className="ml-auto"
                      >
                        <Trash2 size={12} />
                        <span>Terminate</span>
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function QuotaSettings() {
  const qc = useQueryClient()
  const role = useAuthStore((s) => s.role)
  const { data: adminLimits = {} } = useQuery({ queryKey: ['admin-limits'], queryFn: quotaApi.getAdminLimits })
  const { data: userData } = useQuery({ queryKey: ['settings-users'], queryFn: settingsApi.users })
  
  const [adminUsername, setAdminUsername] = useState('')
  const [maxUsers, setMaxUsers] = useState<string | number>('')
  const [dailyQuota, setDailyQuota] = useState<string | number>('')

  const allAdmins = useMemo(() => {
    return (userData?.users ?? [])
      .filter(u => u.role === 'Admin')
      .map(u => u.username)
  }, [userData])

  // Combine already set limits with any other admins found
  const targetAdmins = useMemo(() => {
    const fromLimits = Object.keys(adminLimits)
    const combined = Array.from(new Set([...fromLimits, ...allAdmins]))
    return combined.sort()
  }, [adminLimits, allAdmins])

  useEffect(() => {
    if (adminUsername && adminLimits[adminUsername]) {
      setMaxUsers(adminLimits[adminUsername].max_users)
      setDailyQuota(adminLimits[adminUsername].total_daily_quota)
    }
  }, [adminUsername, adminLimits])

  const setLimits = useMutation({
    mutationFn: () => quotaApi.setAdminLimits(adminUsername, Number(maxUsers), Number(dailyQuota)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-limits'] }),
  })

  return (
    <div className="flex flex-col gap-10">
       <div className="flex flex-col gap-2 text-center">
        <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase">Quota Pool</h2>
        <p className="text-vos-500 text-[10px] font-black uppercase tracking-[0.2em] opacity-50">Resource allocation management</p>
      </div>
      <div className="flex flex-col gap-12 w-full max-w-5xl mx-auto">
        <div className="flex flex-col gap-8">
          <div className="flex items-center gap-4 px-2">
            <h2 className="text-[10px] font-black uppercase tracking-[0.4em] text-vos-600 whitespace-nowrap">Provisioned Pool Overview</h2>
            <div className="h-px w-full bg-c-raised/50" />
          </div>
          <Card className="bg-c-base border-b-subtle overflow-hidden rounded-2xl shadow-3xl">
            <details className="group">
              <summary className="flex items-center justify-between cursor-pointer list-none py-6 px-10 rounded-xl hover:bg-c-raised/50 transition-all">
                <div className="flex items-center gap-4">
                  <div className="w-1.5 h-1.5 rounded-full bg-semantic-success group-open:bg-semantic-success" />
                  <span className="text-[10px] font-black uppercase tracking-[0.2em] text-vos-500 group-open:text-t-primary">View Current Admin Limits & Usage</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-[9px] font-bold text-vos-700 uppercase tracking-widest group-open:hidden">
                    {Object.keys(adminLimits).length} active pools
                  </span>
                  <ChevronDown size={16} className="text-vos-600 group-open:rotate-180 transition-transform duration-500" />
                </div>
              </summary>
              <div className="border-t border-b-subtle overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-c-raised/30">
                      <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-vos-600">Admin</th>
                      <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-vos-600 text-center">Max Users</th>
                      <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-vos-600 text-center">Quota Pool</th>
                      <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-vos-600 text-center">Users Created</th>
                      <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-vos-600 text-center">Remaining Slots</th>
                      <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-vos-600 text-center">Pool Usage</th>
                      <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-vos-600 text-center">Pool Remaining</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-b-subtle">
                    {Object.entries(adminLimits).map(([admin, limits]: [string, any]) => (
                      <tr key={admin} className="hover:bg-c-raised/50 transition-all group">
                        <td className="px-8 py-5">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-vos-900 border border-b-subtle flex items-center justify-center text-[10px] font-black text-vos-400 group-hover:text-t-primary transition-colors">
                              {admin.substring(0, 2).toUpperCase()}
                            </div>
                            <span className="text-sm font-black text-t-primary">{admin}</span>
                          </div>
                        </td>
                        <td className="px-8 py-5 text-center text-sm font-bold text-vos-400">{limits.max_users}</td>
                        <td className="px-8 py-5 text-center text-sm font-bold text-vos-400">{limits.total_daily_quota?.toLocaleString()}</td>
                        <td className="px-8 py-5 text-center text-sm font-bold text-vos-400">{limits.users_created}</td>
                        <td className="px-8 py-5 text-center">
                          <div className="flex justify-center">
                            <span className={`px-3 py-1 rounded-full text-[9px] font-black tracking-widest uppercase border ${
                              limits.remaining_slots > 0 
                                ? 'bg-semantic-success/10 text-semantic-success border-semantic-success/20' 
                                : 'bg-semantic-error/5 text-semantic-error border-semantic-error/10'
                            }`}>
                              {limits.remaining_slots} Slots
                            </span>
                          </div>
                        </td>
                        <td className="px-8 py-5 text-center text-sm font-bold text-vos-400">{limits.current_usage?.toLocaleString()}</td>
                        <td className="px-8 py-5 text-center text-sm font-black text-semantic-success">
                          {(limits.total_daily_quota - limits.current_usage).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                    {Object.keys(adminLimits).length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-8 py-20 text-center">
                          <div className="flex flex-col items-center gap-4 opacity-30">
                            <Activity size={40} className="text-vos-700" />
                            <span className="text-[10px] font-black uppercase tracking-[0.4em] text-vos-600">No active pools provisioned</span>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </details>
          </Card>
        </div>

        <div className="flex flex-col gap-8">
          <div className="flex items-center gap-4 px-2">
            <h2 className="text-[10px] font-black uppercase tracking-[0.4em] text-vos-600 whitespace-nowrap">Pool Allocation Engine</h2>
            <div className="h-px w-full bg-c-raised/50" />
          </div>
          <Card className="bg-c-base border-b-subtle p-10 rounded-2xl shadow-3xl flex flex-col gap-10">
            <div className="flex flex-col gap-4">
              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-vos-600">Select Target Administrator</label>
              <CustomSelect 
                options={targetAdmins} 
                value={adminUsername} 
                onChange={setAdminUsername} 
                className="h-12" 
                placeholder="Select administrator to provision pool..."
              />
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
              <div className="flex flex-col gap-3">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-vos-600">Maximum Users</label>
                <div className="flex h-[48px] w-full items-center rounded-xl bg-surface-page border border-b-subtle overflow-hidden">
                  <input type="number" value={maxUsers} onChange={(e) => setMaxUsers(e.target.value)} placeholder="0" className="flex-1 bg-transparent px-6 text-sm font-bold text-t-primary outline-none" autoComplete="off" />
                  <div className="flex h-full border-l border-b-subtle">
                    <button onClick={() => setMaxUsers(Math.max(0, Number(maxUsers) - 1))} className="flex w-12 items-center justify-center text-vos-500 hover:text-t-primary bg-c-raised/30"><Minus size={16} /></button>
                    <button onClick={() => setMaxUsers(Number(maxUsers) + 1)} className="flex w-12 items-center justify-center text-vos-500 hover:text-t-primary bg-c-raised/30 border-l border-b-subtle"><Plus size={16} /></button>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-vos-600">Daily Quota Pool</label>
                <div className="flex h-[48px] w-full items-center rounded-xl bg-surface-page border border-b-subtle overflow-hidden">
                  <input type="number" value={dailyQuota} onChange={(e) => setDailyQuota(e.target.value)} placeholder="0" className="flex-1 bg-transparent px-6 text-sm font-bold text-t-primary outline-none" autoComplete="off" />
                  <div className="flex h-full border-l border-b-subtle">
                    <button onClick={() => setDailyQuota(Math.max(0, Number(dailyQuota) - 1000))} className="flex w-12 items-center justify-center text-vos-500 hover:text-t-primary bg-c-raised/30"><Minus size={16} /></button>
                    <button onClick={() => setDailyQuota(Number(dailyQuota) + 1000)} className="flex w-12 items-center justify-center text-vos-500 hover:text-t-primary bg-c-raised/30 border-l border-b-subtle"><Plus size={16} /></button>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-4">
              <div className="flex-1">
                {setLimits.isSuccess && (
                   <div className="flex items-center gap-3 text-semantic-success animate-in fade-in slide-in-from-left-4 duration-500">
                    <div className="w-6 h-6 rounded-full bg-semantic-success/10 flex items-center justify-center">
                      <Check size={12} className="stroke-[3]" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[10px] font-black uppercase tracking-widest">Success</span>
                      <span className="text-[9px] font-bold text-vos-500 uppercase tracking-tighter opacity-70">Quota pool updated for {adminUsername}</span>
                    </div>
                  </div>
                )}
                {setLimits.isError && (
                  <div className="flex items-center gap-3 text-red-500 animate-in fade-in slide-in-from-left-4 duration-500">
                    <div className="w-6 h-6 rounded-full bg-red-500/10 flex items-center justify-center">
                      <AlertCircle size={12} className="stroke-[3]" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[10px] font-black uppercase tracking-widest">Error</span>
                      <span className="text-[9px] font-bold text-vos-500 uppercase tracking-tighter opacity-70">Failed to update resource pool</span>
                    </div>
                  </div>
                )}
              </div>
              <Button 
                className={`px-10 py-4 font-black uppercase tracking-[0.2em] text-[10px] rounded-xl shadow-2xl transition-all duration-300 ${
                  setLimits.isSuccess ? 'bg-[var(--btn-heavy-bg)] text-[var(--btn-heavy-text)]' : 'bg-[var(--btn-heavy-bg)] text-[var(--btn-heavy-text)] hover:bg-[var(--btn-heavy-hover)]'
                }`}
                onClick={() => setLimits.mutate()} 
                disabled={!adminUsername || setLimits.isPending}
              >
                {setLimits.isPending ? (
                  <div className="flex items-center gap-2">
                    <Spinner size="sm" />
                    <span>Processing...</span>
                  </div>
                ) : setLimits.isSuccess ? (
                  "Pool Initialized"
                ) : (
                  "Apply Pool Limits"
                )}
              </Button>
            </div>
          </Card>
        </div>

      </div>
    </div>
  )
}

function SharingSettings() {
  const [tab, setTab] = useState<'overview' | 'manage' | 'create'>('overview')

  return (
    <div className="flex flex-col gap-8 w-full max-w-5xl mx-auto">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase">Dashboard Sharing</h2>
        <p className="text-vos-500 text-xs">Control which users share dashboard views with each other.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-b-subtle pb-0">
        {(['overview', 'manage', 'create'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2.5 text-xs font-bold uppercase tracking-wider transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'border-t-primary text-t-primary'
                : 'border-transparent text-vos-500 hover:text-t-primary'
            }`}
          >
            {t === 'overview' ? 'Overview' : t === 'manage' ? 'Manage Groups' : 'Create Group'}
          </button>
        ))}
      </div>

      {tab === 'overview' && <SharingOverview />}
      {tab === 'manage' && <SharingManage />}
      {tab === 'create' && <SharingCreate onCreated={() => setTab('overview')} />}
    </div>
  )
}

function SharingOverview() {
  const { data, isLoading } = useQuery({ queryKey: ['sharing-config'], queryFn: sharingApi.config })

  if (isLoading) return <Spinner />

  const groups = data?.sharing_groups ? Object.entries(data.sharing_groups as Record<string, any>) : []
  const userModes = data?.user_dashboard_mode ? Object.entries(data.user_dashboard_mode as Record<string, string>) : []

  return (
    <div className="flex flex-col gap-10">
      {/* Current Groups table */}
      <div className="flex flex-col gap-4">
        <h3 className="text-xs font-black uppercase tracking-widest text-vos-500">Current Groups</h3>
        <Card className="p-0 overflow-hidden bg-c-base border-b-subtle rounded-2xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-page border-b border-b-subtle">
              <tr>
                <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Group Name</th>
                <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Members</th>
                <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Created By</th>
                <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-b-subtle">
              {groups.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-vos-600 text-xs">
                    All users are currently isolated
                  </td>
                </tr>
              ) : groups.map(([name, group]) => (
                <tr key={name} className="hover:bg-c-raised/30">
                  <td className="px-6 py-3 font-bold text-t-primary">{name}</td>
                  <td className="px-6 py-3 text-vos-400">{(group.members || []).join(', ')}</td>
                  <td className="px-6 py-3 text-vos-500">{group.created_by || '—'}</td>
                  <td className="px-6 py-3 text-vos-600">{group.created_date || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      {/* User Dashboard Status table */}
      <div className="flex flex-col gap-4">
        <h3 className="text-xs font-black uppercase tracking-widest text-vos-500">User Dashboard Status</h3>
        <Card className="p-0 overflow-hidden bg-c-base border-b-subtle rounded-2xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-page border-b border-b-subtle">
              <tr>
                <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Username</th>
                <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Dashboard Mode</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-b-subtle">
              {userModes.length === 0 ? (
                <tr>
                  <td colSpan={2} className="px-6 py-12 text-center text-vos-600 text-xs">No user mode data</td>
                </tr>
              ) : userModes.map(([username, mode]) => (
                <tr key={username} className="hover:bg-c-raised/30">
                  <td className="px-6 py-3 font-bold text-t-primary">{username}</td>
                  <td className="px-6 py-3">
                    {mode === 'isolated' || !mode ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-black bg-vos-50 border border-b-medium text-vos-500">Isolated</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-[10px] font-black bg-vos-50 border border-b-medium text-t-primary">Shared ({mode})</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  )
}

function SharingManage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['sharing-config'], queryFn: sharingApi.config })
  const { data: userData } = useQuery({ queryKey: ['settings-users'], queryFn: settingsApi.users })

  const [selectedGroup, setSelectedGroup] = useState('')
  const [toAdd, setToAdd] = useState<string[]>([])
  const [toRemove, setToRemove] = useState<string[]>([])

  const groups = data?.sharing_groups ? Object.entries(data.sharing_groups as Record<string, any>) : []
  const groupNames = groups.map(([name]) => name)
  const currentGroup = groups.find(([name]) => name === selectedGroup)
  const currentMembers: string[] = currentGroup ? (currentGroup[1].members || []) : []

  const allUsers = (userData?.users ?? []).map(u => u.username)

  const availableToAdd = allUsers.filter(u => !currentMembers.includes(u))

  const addMembers = useMutation({
    mutationFn: () => sharingApi.updateGroup(selectedGroup, [...currentMembers, ...toAdd]),
    onSuccess: () => { setToAdd([]); qc.invalidateQueries({ queryKey: ['sharing-config'] }) },
  })

  const removeMembers = useMutation({
    mutationFn: () => sharingApi.updateGroup(selectedGroup, currentMembers.filter(m => !toRemove.includes(m))),
    onSuccess: () => { setToRemove([]); qc.invalidateQueries({ queryKey: ['sharing-config'] }) },
  })

  const deleteGroup = useMutation({
    mutationFn: () => sharingApi.deleteGroup(selectedGroup),
    onSuccess: () => { setSelectedGroup(''); qc.invalidateQueries({ queryKey: ['sharing-config'] }) },
  })

  const sync = useMutation({
    mutationFn: sharingApi.syncModes,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sharing-config'] }),
  })

  if (isLoading) return <Spinner />

  return (
    <div className="flex flex-col gap-8">
      {/* Sync button */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-c-raised/50 border border-b-subtle">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-bold text-t-primary">Sync User Statuses</span>
          <span className="text-[10px] text-vos-600">Force-sync dashboard modes from current group definitions</span>
        </div>
        <Button variant="secondary" onClick={() => sync.mutate()} disabled={sync.isPending}>
          <RefreshCw size={13} className="mr-2" />
          {sync.isPending ? 'Syncing…' : sync.isSuccess ? `Done` : 'Sync'}
        </Button>
      </div>

      {/* Group selector */}
      <div className="flex flex-col gap-2">
        <label className="text-[10px] font-black uppercase tracking-widest text-vos-600">Select a group to manage</label>
        <CustomSelect options={groupNames} value={selectedGroup} onChange={setSelectedGroup} placeholder="Select group…" />
      </div>

      {selectedGroup && (
        <div className="flex flex-col gap-8">
          {/* Add / Remove members */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Add */}
            <Card className="bg-c-base border-b-subtle p-6 rounded-2xl flex flex-col gap-4">
              <h4 className="text-xs font-black uppercase tracking-widest text-vos-500">Add Members</h4>
              <div className="flex flex-col gap-2">
                {availableToAdd.length === 0 ? (
                  <p className="text-xs text-vos-700">No users available to add</p>
                ) : availableToAdd.map(u => (
                  <label key={u} className="flex items-center gap-3 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={toAdd.includes(u)}
                      onChange={e => setToAdd(prev => e.target.checked ? [...prev, u] : prev.filter(x => x !== u))}
                      className="accent-white"
                    />
                    <span className="text-xs text-vos-300 group-hover:text-t-primary transition-colors">{u}</span>
                  </label>
                ))}
              </div>
              <Button className="mt-auto" onClick={() => addMembers.mutate()} disabled={toAdd.length === 0 || addMembers.isPending}>
                Add Selected Users
              </Button>
            </Card>

            {/* Remove */}
            <Card className="bg-c-base border-b-subtle p-6 rounded-2xl flex flex-col gap-4">
              <h4 className="text-xs font-black uppercase tracking-widest text-vos-500">Remove Members</h4>
              <div className="flex flex-col gap-2">
                {currentMembers.length === 0 ? (
                  <p className="text-xs text-vos-700">No members in this group</p>
                ) : currentMembers.map(u => (
                  <label key={u} className="flex items-center gap-3 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={toRemove.includes(u)}
                      onChange={e => setToRemove(prev => e.target.checked ? [...prev, u] : prev.filter(x => x !== u))}
                      className="accent-white"
                    />
                    <span className="text-xs text-vos-300 group-hover:text-t-primary transition-colors">{u}</span>
                  </label>
                ))}
              </div>
              <Button variant="secondary" className="mt-auto border-ship-red/20 text-ship-red hover:bg-ship-red hover:text-t-primary" onClick={() => removeMembers.mutate()} disabled={toRemove.length === 0 || removeMembers.isPending}>
                Remove Selected Users
              </Button>
            </Card>
          </div>

          {/* Delete group */}
          <div className="flex justify-end border-t border-b-subtle pt-6">
            <Button
              variant="secondary"
              className="border-ship-red/30 text-ship-red hover:bg-ship-red hover:text-t-primary"
              onClick={() => { if (confirm(`Delete group "${selectedGroup}"?`)) deleteGroup.mutate() }}
              disabled={deleteGroup.isPending}
            >
              <Trash2 size={13} className="mr-2" />
              Delete Group &quot;{selectedGroup}&quot;
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function SharingCreate({ onCreated }: { onCreated: () => void }) {
  const qc = useQueryClient()
  const { data: userData } = useQuery({ queryKey: ['settings-users'], queryFn: settingsApi.users })

  const [groupName, setGroupName] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [error, setError] = useState('')

  const allUsers = (userData?.users ?? []).map(u => u.username)

  const create = useMutation({
    mutationFn: () => sharingApi.createGroup(groupName.trim(), selected),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sharing-config'] })
      onCreated()
    },
  })

  const handleCreate = () => {
    setError('')
    if (!groupName.trim()) { setError('Group name is required.'); return }
    if (selected.length < 2) { setError('A sharing group must have at least two users.'); return }
    create.mutate()
  }

  return (
    <div className="flex flex-col gap-8 max-w-xl">
      <div className="flex flex-col gap-6">
        <Input
          label="GROUP NAME"
          value={groupName}
          onChange={e => setGroupName(e.target.value)}
          placeholder="e.g. Sales Team"
        />

        <div className="flex flex-col gap-3">
          <label className="text-[10px] font-black uppercase tracking-widest text-vos-600">Select Users</label>
          <Card className="bg-c-base border-b-subtle p-4 rounded-xl flex flex-col gap-2 max-h-64 overflow-y-auto custom-scrollbar">
            {allUsers.length === 0 ? (
              <p className="text-xs text-vos-700">No users available</p>
            ) : allUsers.map(u => (
              <label key={u} className="flex items-center gap-3 cursor-pointer group py-1">
                <input
                  type="checkbox"
                  checked={selected.includes(u)}
                  onChange={e => setSelected(prev => e.target.checked ? [...prev, u] : prev.filter(x => x !== u))}
                  className="accent-white"
                />
                <span className="text-xs text-vos-300 group-hover:text-t-primary transition-colors">{u}</span>
              </label>
            ))}
          </Card>
          <p className="text-[10px] text-vos-600">{selected.length} user{selected.length !== 1 ? 's' : ''} selected</p>
        </div>

        {error && <p className="text-xs text-ship-red font-bold">{error}</p>}

        <Button className="py-4 font-black uppercase tracking-widest" onClick={handleCreate} disabled={create.isPending}>
          {create.isPending ? 'Creating…' : 'Create Group'}
        </Button>
      </div>
    </div>
  )
}

function SystemHealth() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['system-health'],
    queryFn: systemApi.health,
  })

  const cpu  = data?.cpu_percent ?? 0
  const mem  = data?.memory?.percent ?? 0
  const disk = data?.disk_percent ?? 0
  const high = Math.max(cpu, mem, disk) > 85

  const bar = (val: number) => {
    const color = val > 85 ? 'bg-ship-red' : val > 60 ? 'bg-semantic-warning' : 'bg-semantic-success'
    return (
      <div className="h-1.5 w-full rounded-full bg-vos-50 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${val}%` }} />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase">System Health</h2>
          <p className="text-vos-500 text-xs">Monitor CPU, memory, and disk usage in real time.</p>
        </div>
        <Button variant="secondary" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw size={13} className={`mr-2 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {isLoading ? <Spinner /> : (
        <>
          <div className="grid grid-cols-3 gap-6">
            {[
              { label: 'CPU Usage', value: cpu },
              { label: 'Memory Usage', value: mem },
              { label: 'Disk Usage', value: disk },
            ].map(({ label, value }) => (
              <Card key={label} className="bg-c-base border-b-subtle p-6 rounded-2xl flex flex-col gap-4">
                <span className="text-[10px] font-black uppercase tracking-widest text-vos-500">{label}</span>
                <span className={`text-4xl font-black tracking-tighter ${value > 85 ? 'text-ship-red' : value > 60 ? 'text-semantic-warning' : 'text-t-primary'}`}>
                  {value}<span className="text-lg text-vos-500">%</span>
                </span>
                {bar(value)}
              </Card>
            ))}
          </div>

          <div className={`flex items-center gap-3 px-5 py-4 rounded-xl border text-xs font-bold ${
            high
              ? 'bg-ship-red/5 border-ship-red/20 text-ship-red'
              : 'bg-semantic-success/5 border-semantic-success/10 text-semantic-success'
          }`}>
            <div className={`w-2 h-2 rounded-full ${high ? 'bg-ship-red animate-pulse' : 'bg-semantic-success'}`} />
            {high
              ? 'High system load detected. Consider closing idle sessions.'
              : 'System resources are healthy and stable.'}
          </div>
        </>
      )}
    </div>
  )
}

// â”€â”€â”€ Admin: Quota Dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function AdminQuotaDashboard() {
  const { data: status, isLoading } = useQuery({ queryKey: ['quota-status'], queryFn: quotaApi.status })
  const { data: redistData, isLoading: redistLoading } = useQuery({ queryKey: ['quota-redistribution'], queryFn: quotaApi.redistribution })

  if (isLoading) return <Spinner />

  const quotaInfo = status as any
  const users = redistData as any

  return (
    <div className="flex flex-col gap-10 w-full max-w-4xl mx-auto">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase">Quota Dashboard</h2>
        <p className="text-vos-500 text-xs">Your quota usage and user creation limits.</p>
      </div>

      {/* Quota Status */}
      {quotaInfo && (
        <div className="flex flex-col gap-4">
          <h3 className="text-xs font-black uppercase tracking-widest text-vos-500">Your Quota Status</h3>
          <div className="grid grid-cols-3 gap-4">
            <Card className="bg-c-base border-b-subtle p-6 rounded-2xl flex flex-col gap-1">
              <span className="text-[10px] font-black uppercase tracking-widest text-vos-600">Daily Quota Pool</span>
              <span className="text-2xl font-black text-t-primary">{quotaInfo.current_count ?? 0}<span className="text-vos-600 text-sm">/{quotaInfo.daily_limit ?? 'âˆ‍'}</span></span>
            </Card>
            <Card className="bg-c-base border-b-subtle p-6 rounded-2xl flex flex-col gap-1">
              <span className="text-[10px] font-black uppercase tracking-widest text-vos-600">Remaining</span>
              <span className="text-2xl font-black text-t-primary">{quotaInfo.remaining ?? 'âˆ‍'}</span>
            </Card>
            <Card className="bg-c-base border-b-subtle p-6 rounded-2xl flex flex-col gap-1">
              <span className="text-[10px] font-black uppercase tracking-widest text-vos-600">Resets</span>
              <span className="text-2xl font-black text-t-primary">Daily</span>
            </Card>
          </div>
        </div>
      )}

      {/* Users quota table */}
      <div className="flex flex-col gap-4">
        <h3 className="text-xs font-black uppercase tracking-widest text-vos-500">Your Users</h3>
        {redistLoading ? <Spinner /> : (
          <Card className="p-0 overflow-hidden bg-c-base border-b-subtle rounded-2xl">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-page border-b border-b-subtle">
                <tr>
                  <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Username</th>
                  <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Daily Quota</th>
                  <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Used Today</th>
                  <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Remaining</th>
                  <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Usage %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-b-subtle">
                {!users?.users || users.users.length === 0 ? (
                  <tr><td colSpan={5} className="px-6 py-12 text-center text-vos-600">No users created yet</td></tr>
                ) : users.users.map((u: any) => (
                  <tr key={u.username} className="hover:bg-c-raised/30">
                    <td className="px-6 py-3 font-bold text-t-primary">{u.username}</td>
                    <td className="px-6 py-3 text-vos-400 font-mono">{u.daily_quota ?? '—'}</td>
                    <td className="px-6 py-3 text-vos-400 font-mono">{u.current_usage ?? 0}</td>
                    <td className="px-6 py-3 text-vos-400 font-mono">{u.remaining ?? '—'}</td>
                    <td className="px-6 py-3">
                      <span className={`text-xs font-bold ${(u.percentage_used ?? 0) > 80 ? 'text-ship-red' : 'text-semantic-success'}`}>
                        {u.percentage_used?.toFixed(1) ?? '0.0'}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </div>
  )
}

// â”€â”€â”€ Admin: Manage Users â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function AdminManageUsers() {
  const qc = useQueryClient()
  const myUsername = useAuthStore((s) => s.username)
  const { data: userData, isLoading } = useQuery({ queryKey: ['settings-users'], queryFn: settingsApi.users })
  const { data: redistData } = useQuery({ queryKey: ['quota-redistribution'], queryFn: quotaApi.redistribution })

  const [selectedUser, setSelectedUser] = useState('')
  const [appPassword, setAppPassword] = useState('')
  const [rmUsername, setRmUsername] = useState('')
  const [rmPassword, setRmPassword] = useState('')
  const [newQuota, setNewQuota] = useState<string | number>(0)

  // Admin sees only Auditors (their created users)
  const myUsers = (userData?.users ?? []).filter(u => u.role === 'Auditor')
  const redistUsers = (redistData as any)?.users ?? []

  const userToEdit = myUsers.find(u => u.username === selectedUser)
  const redistUser = redistUsers.find((u: any) => u.username === selectedUser)

  useEffect(() => {
    if (userToEdit) {
      setRmUsername(userToEdit.readymode_username ?? '')
      setNewQuota(redistUser?.daily_quota ?? userToEdit.daily_limit ?? 0)
    }
  }, [userToEdit, redistUser])

  const update = useMutation({
    mutationFn: () => settingsApi.updateUser(selectedUser, {
      daily_limit: Number(newQuota),
      readymode_username: rmUsername || undefined,
      readymode_password: rmPassword || undefined,
      password: appPassword || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings-users'] })
      qc.invalidateQueries({ queryKey: ['quota-redistribution'] })
      setAppPassword(''); setRmPassword('')
    },
  })

  const remove = useMutation({
    mutationFn: settingsApi.deleteUser,
    onSuccess: () => {
      setSelectedUser('')
      qc.invalidateQueries({ queryKey: ['settings-users'] })
    },
  })

  if (isLoading) return <Spinner />

  return (
    <div className="flex flex-col gap-10 w-full max-w-4xl mx-auto">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase">Manage Users</h2>
        <p className="text-vos-500 text-xs">View and manage all users created under your account.</p>
      </div>

      {/* Users table */}
      <Card className="p-0 overflow-hidden bg-c-base border-b-subtle rounded-2xl">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-page border-b border-b-subtle">
            <tr>
              <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Username</th>
              <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Daily Quota</th>
              <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Used Today</th>
              <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Remaining</th>
              <th className="px-6 py-3 text-[10px] font-black uppercase tracking-widest text-vos-700">Usage %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-b-subtle">
            {myUsers.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-12 text-center text-vos-600">You haven't created any users yet</td></tr>
            ) : myUsers.map(u => {
              const ru = redistUsers.find((r: any) => r.username === u.username)
              return (
                <tr key={u.username} className="hover:bg-c-raised/30">
                  <td className="px-6 py-3 font-bold text-t-primary">{u.username}</td>
                  <td className="px-6 py-3 text-vos-400 font-mono">{ru?.daily_quota ?? u.daily_limit ?? '—'}</td>
                  <td className="px-6 py-3 text-vos-400 font-mono">{ru?.current_usage ?? 0}</td>
                  <td className="px-6 py-3 text-vos-400 font-mono">{ru?.remaining ?? '—'}</td>
                  <td className="px-6 py-3">
                    <span className={`text-xs font-bold ${(ru?.percentage_used ?? 0) > 80 ? 'text-ship-red' : 'text-semantic-success'}`}>
                      {ru?.percentage_used?.toFixed(1) ?? '0.0'}%
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>

      {/* Edit selected user */}
      <div className="flex flex-col gap-6">
        <h3 className="text-xs font-black uppercase tracking-widest text-vos-500">Edit User</h3>
        <CustomSelect options={myUsers.map(u => u.username)} value={selectedUser} onChange={setSelectedUser} placeholder="Select user to edit…" />

        {selectedUser && (
          <Card className="bg-c-base border-b-subtle p-8 rounded-2xl flex flex-col gap-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Input label="APP PASSWORD" type="password" value={appPassword} onChange={e => setAppPassword(e.target.value)} placeholder="Leave blank to keep current" autoComplete="new-password" />
              <Input label="READYMODE USERNAME" value={rmUsername} onChange={e => setRmUsername(e.target.value)} placeholder="ReadyMode account" autoComplete="off" />
              <Input label="READYMODE PASSWORD" type="password" value={rmPassword} onChange={e => setRmPassword(e.target.value)} placeholder="Leave blank to keep current" autoComplete="new-password" />
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-vos-600">Daily Quota</label>
                <div className="flex h-[44px] w-full items-center rounded-lg bg-surface-page border border-b-subtle overflow-hidden">
                  <input type="number" value={newQuota} onChange={e => setNewQuota(e.target.value)} className="flex-1 bg-transparent px-4 text-xs font-bold text-t-primary outline-none" />
                  <div className="flex h-full border-l border-b-subtle">
                    <button type="button" onClick={() => setNewQuota(Math.max(0, Number(newQuota) - 100))} className="flex w-10 items-center justify-center text-vos-500 hover:text-t-primary"><Minus size={14} /></button>
                    <button type="button" onClick={() => setNewQuota(Number(newQuota) + 100)} className="flex w-10 items-center justify-center text-vos-500 hover:text-t-primary border-l border-b-subtle"><Plus size={14} /></button>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between pt-4 border-t border-b-subtle">
              <Button
                variant="danger"
                className="text-ship-red/60 hover:text-t-primary flex items-center gap-2"
                onClick={() => { if (confirm(`Delete user ${selectedUser}?`)) remove.mutate(selectedUser) }}
                disabled={remove.isPending}
              >
                <Trash2 size={13} /> Delete User
              </Button>
              <Button className="px-8 py-3 font-black uppercase" onClick={() => update.mutate()} disabled={update.isPending}>
                Save Changes
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}

function AppConfig() {
  const qc = useQueryClient()
  const [category, setCategory] = useState<AppConfigCategory>('audio')
  const { data, isLoading } = useQuery({ queryKey: ['app-config', category], queryFn: () => settingsApi.appConfig(category) })
  const [config, setConfig] = useState<Record<string, any>>({})

  useEffect(() => {
    if (data) setConfig(data)
  }, [data])

  const save = useMutation({
    mutationFn: () => settingsApi.updateAppConfig(category, config),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['app-config', category] }),
  })

  const updateKey = (key: string, value: string) => {
    setConfig(prev => ({ ...prev, [key]: value }))
  }

  // Helper to format labels from snake_case
  const formatLabel = (key: string) => {
    return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
  }

  return (
    <div className="flex flex-col gap-10 items-center w-full">
       <div className="flex flex-col gap-2 text-center">
        <h2 className="text-3xl font-black text-t-primary tracking-tighter uppercase">Parameters</h2>
        <p className="text-vos-500 text-[10px] font-black uppercase tracking-[0.2em] opacity-50">Low-level system tuning</p>
      </div>

      <Card className="flex w-full max-w-4xl flex-col gap-8 bg-c-base border-b-subtle p-10 rounded-2xl shadow-3xl backdrop-blur-xl">
        <div className="flex items-center justify-between border-b border-b-subtle pb-6">
          <div className="flex items-center gap-4">
             <div className="w-10 h-10 rounded-xl bg-ship-red/10 flex items-center justify-center text-ship-red border border-ship-red/20 shadow-[0_0_15px_rgba(239,68,68,0.1)]"><Settings2 size={20} /></div>
             <div className="flex flex-col">
               <h2 className="text-[11px] font-black uppercase tracking-[0.3em] text-t-primary">Engine Configuration</h2>
               <p className="text-[8px] font-bold text-vos-600 uppercase tracking-widest mt-0.5">Live environment variables</p>
             </div>
          </div>
          <div className="p-1 bg-surface-page rounded-xl border border-b-subtle shadow-inner">
            <CustomSelect options={['audio', 'detection']} value={category} onChange={(v) => setCategory(v as AppConfigCategory)} className="w-44 text-[10px] h-9 border-0 bg-transparent" />
          </div>
        </div>

        {isLoading ? (
          <div className="h-[400px] flex items-center justify-center"><Spinner /></div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8 py-4">
            {Object.keys(config).length === 0 ? (
              <div className="col-span-2 py-20 text-center opacity-20 flex flex-col items-center">
                <Database size={40} className="mb-4" />
                <span className="text-[10px] font-black uppercase tracking-widest">No parameters found for this category</span>
              </div>
            ) : Object.entries(config).map(([key, value]) => (
              <div key={key} className="flex flex-col gap-2.5">
                <label className="text-[9px] font-black uppercase tracking-[0.2em] text-vos-600 ml-1">{formatLabel(key)}</label>
                <div className="relative group">
                  <input
                    type="text"
                    value={typeof value === 'string' ? value.replace(/^"(.*)"$/, '$1') : value}
                    onChange={(e) => updateKey(key, e.target.value)}
                    className="w-full h-12 bg-surface-page border border-b-subtle rounded-xl px-5 text-xs font-bold text-t-primary outline-none focus:border-b-focus focus:bg-surface-card transition-all"
                    spellCheck={false}
                  />
                  <div className="absolute inset-0 rounded-xl bg-ship-red/5 opacity-0 group-focus-within:opacity-100 pointer-events-none transition-opacity" />
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="pt-6 border-t border-b-subtle flex flex-col gap-4">
          <Button 
            className="w-full py-5 text-[10px] font-black uppercase tracking-[0.3em] bg-[var(--btn-heavy-bg)] text-[var(--btn-heavy-text)] hover:bg-[var(--btn-heavy-hover)] shadow-2xl transition-all hover:scale-[1.01]" 
            onClick={() => save.mutate()} 
            disabled={save.isPending}
          >
            {save.isPending ? 'Deploying...' : 'Deploy Configurations'}
          </Button>
          <div className="flex items-center justify-center gap-2 opacity-30">
            <Shield size={10} className="text-vos-500" />
            <span className="text-[8px] font-black uppercase tracking-[0.2em] text-vos-500">Atomic configuration update — Restart not required</span>
          </div>
        </div>
      </Card>
    </div>
  )
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-40 opacity-20">
      <div className="w-24 h-24 rounded-full border-2 border-vos-500 flex items-center justify-center mb-8">
        <Settings2 size={40} className="text-vos-500" />
      </div>
      <h2 className="text-2xl font-black text-t-primary uppercase tracking-[0.5em]">{title}</h2>
      <p className="text-vos-500 text-[10px] font-black uppercase tracking-widest mt-4">Module in high-security standby</p>
    </div>
  )
}

function Badge({ role, children }: { role: string; children: React.ReactNode }) {
  const color = role === 'Owner' ? 'text-ship-red border-ship-red/20 bg-ship-red/5' : role === 'Admin' ? 'text-t-primary border-b-medium bg-vos-50' : 'text-vos-500 border-b-medium bg-vos-50'
  return (
    <span className={`px-2 py-0.5 rounded border text-[8px] font-black uppercase tracking-[0.2em] ${color}`}>
      {children}
    </span>
  )
}

function ProfileField({ label, value, active = false }: { label: string; value: string | number | undefined; active?: boolean }) {
  const displayValue = value === 999999 || value === '999999' ? '∞' : value
  return (
    <div className={`flex items-center justify-between px-4 py-3 rounded-xl border border-b-subtle bg-c-raised/30 ${active ? 'border-ship-red/20' : ''}`}>
      <span className="text-[8px] font-black uppercase tracking-widest text-vos-700">{label}</span>
      <span className={`text-[10px] font-bold ${active ? 'text-ship-red' : 'text-t-primary'} ${displayValue === '∞' ? 'text-[14px]' : ''}`}>{displayValue}</span>
    </div>
  )
}
