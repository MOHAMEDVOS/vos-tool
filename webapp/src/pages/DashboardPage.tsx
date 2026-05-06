import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { settingsApi } from '@/api/settings'
import { Tabs } from '@/components/ui/Tabs'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { SuccessFlash } from '@/components/ui/SuccessFlash'
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
          <Button
            variant={showConfig ? 'primary' : 'secondary'}
            onClick={() => setShowConfig(!showConfig)}
            className="gap-2 h-9"
          >
            <Key size={13} />
            <span className="uppercase tracking-[0.1em]">{showConfig ? 'Hide Config' : 'Configure AI Key'}</span>
            <ChevronDown size={13} className={`transition-transform duration-300 ${showConfig ? 'rotate-180' : ''}`} />
          </Button>
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
              <Card className="flex flex-col bg-surface-card shadow-card overflow-hidden border border-b-medium">
                {/* Header */}
                <div className="px-6 py-4 border-b border-b-divider bg-surface-soft/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Key size={14} className="text-t-primary" />
                    <h2 className="text-[11px] font-bold uppercase tracking-[0.15em] text-t-primary">
                      AssemblyAI Configuration
                    </h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-medium text-t-muted uppercase tracking-widest">Status:</span>
                    <span className={`text-[10px] font-bold uppercase tracking-widest ${keyStatus.data?.has_key ? 'text-semantic-success' : 'text-t-muted'}`}>
                      {keyStatus.data?.has_key ? 'Active' : 'Missing'}
                    </span>
                  </div>
                </div>

                {/* Body */}
                <div className="p-6 flex flex-col gap-6">
                  <div>
                    <p className="text-[13px] text-t-secondary leading-relaxed max-w-xl">
                      Your AssemblyAI API key is used for secure, high-accuracy audio transcription. 
                      It is stored encrypted and only used for your private transcription jobs.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-[0.15em] text-t-muted">
                      API Key
                    </label>
                    <Input
                      type="password"
                      className="bg-surface-page/50 border border-b-medium focus:border-accent transition-all"
                      value={assemblyKey}
                      onChange={(e) => setAssemblyKey(e.target.value)}
                      placeholder="Enter new key (e.g. 78a5...)"
                    />
                    <p className="text-[11px] text-t-muted">
                      Enter a new key to update or leave blank to clear the current configuration.
                    </p>
                  </div>
                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-surface-soft/20 border-t border-t-divider flex items-center justify-between">
                  <SuccessFlash show={updateKey.isSuccess} label="Settings Updated" />
                  <div className="flex items-center gap-3">
                    {keyStatus.data?.has_key && (
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => clearKey.mutate()} 
                        disabled={clearKey.isPending}
                        className="text-semantic-error hover:bg-semantic-error/10 hover:text-semantic-error"
                      >
                        Clear Key
                      </Button>
                    )}
                    <Button 
                      variant="primary" 
                      size="sm"
                      onClick={() => updateKey.mutate()} 
                      disabled={!assemblyKey.trim() || updateKey.isPending}
                      className="min-w-[140px]"
                    >
                      {updateKey.isPending ? 'Saving...' : 'Save Configuration'}
                    </Button>
                  </div>
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
