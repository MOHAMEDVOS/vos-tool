import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { settingsApi } from '@/api/settings'
import { Tabs } from '@/components/ui/Tabs'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { AgentAuditDashboard } from '@/features/dashboard/AgentAuditDashboard'
import { LiteAuditDashboard } from '@/features/dashboard/LiteAuditDashboard'
import { CampaignAuditDashboard } from '@/features/dashboard/CampaignAuditDashboard'
import { useAuthStore } from '@/store/authStore'
import { Key, ChevronDown } from 'lucide-react'

export function DashboardPage() {
  const qc = useQueryClient()
  const role = useAuthStore((s) => s.role)
  const isAuditor = role === 'Auditor'
  const [showConfig, setShowConfig] = useState(false)

  const TABS = [
    { id: 'agent',    label: 'Agent Audit' },
    { id: 'lite',     label: 'Lite Audit' },
    ...(!isAuditor ? [{ id: 'campaign', label: 'Campaign Audit' }] : []),
  ]

  const [active, setActive] = useState('agent')
  const [assemblyKey, setAssemblyKey] = useState('')
  const keyStatus = useQuery({ queryKey: ['assemblyai-key-status'], queryFn: settingsApi.assemblyAiKeyStatus })

  const updateKey = useMutation({
    mutationFn: () => settingsApi.updateAssemblyAiKey(assemblyKey),
    onSuccess: () => {
      setAssemblyKey('')
      qc.invalidateQueries({ queryKey: ['assemblyai-key-status'] })
    },
  })

  const clearKey = useMutation({
    mutationFn: () => settingsApi.updateAssemblyAiKey(''),
    onSuccess: () => {
      setAssemblyKey('')
      qc.invalidateQueries({ queryKey: ['assemblyai-key-status'] })
    },
  })

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-6">
        <div className="flex items-end justify-between border-b border-b-subtle pb-8">
          <div className="flex flex-col gap-1">
            <h1 className="font-display text-[42px] font-light tracking-[0.05em] text-t-primary leading-none">Dashboard</h1>
            <p className="text-[14px] text-t-muted font-medium tracking-tight">Overview of your automated audits and detections.</p>
          </div>
          <motion.button
            whileTap={{ scale: 0.98 }}
            onClick={() => setShowConfig(!showConfig)}
            className={`flex items-center gap-2 rounded-md px-4 py-2 text-[11px] font-bold uppercase tracking-[0.1em] transition-all border ${
              showConfig 
                ? 'bg-t-primary text-t-on-primary border-t-primary shadow-md' 
                : 'bg-c-base text-t-muted border-b-medium hover:border-t-primary hover:text-t-primary'
            }`}
          >
            <Key size={13} />
            {showConfig ? 'Hide Config' : 'Configure AI Key'}
            <ChevronDown size={13} className={`transition-transform duration-300 ${showConfig ? 'rotate-180' : ''}`} />
          </motion.button>
        </div>

        <AnimatePresence>
          {showConfig && (
            <motion.div
              initial={{ opacity: 0, height: 0, marginTop: -20 }}
              animate={{ opacity: 1, height: 'auto', marginTop: 0 }}
              exit={{ opacity: 0, height: 0, marginTop: -20 }}
              transition={{ duration: 0.3, ease: 'easeInOut' }}
              className="overflow-hidden"
            >
              <Card className="flex flex-col gap-5 bg-c-raised/50 border-b-medium backdrop-blur-sm">
                <div>
                  <h2 className="text-base font-black uppercase tracking-tight text-t-primary flex items-center gap-2">
                    <Key size={16} className="text-vos-500" />
                    My AssemblyAI API Key
                  </h2>
                  <p className="mt-1 text-sm text-vos-400">
                    Store a personal AssemblyAI API key. Encrypted and used for transcription when available.
                  </p>
                </div>
                <p className="text-sm text-vos-400">
                  Status: <strong className="text-t-primary font-bold">{keyStatus.data?.has_key ? 'Set' : 'Not set'}</strong>
                </p>
                <div>
                  <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em] text-vos-500">
                    Update your AssemblyAI API key
                  </label>
                  <Input
                    type="password"
                    value={assemblyKey}
                    onChange={(e) => setAssemblyKey(e.target.value)}
                    placeholder="Enter new key or leave blank to clear"
                  />
                </div>
                <div className="flex gap-3">
                  <Button onClick={() => updateKey.mutate()} disabled={!assemblyKey.trim() || updateKey.isPending}>Save key</Button>
                  {keyStatus.data?.has_key && (
                    <Button variant="danger" onClick={() => clearKey.mutate()} disabled={clearKey.isPending}>Clear key</Button>
                  )}
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <Tabs tabs={TABS} active={active} onChange={setActive} />
      {active === 'agent'    && <AgentAuditDashboard />}
      {active === 'lite'     && <LiteAuditDashboard />}
      {active === 'campaign' && !isAuditor && <CampaignAuditDashboard />}
    </div>
  )
}
