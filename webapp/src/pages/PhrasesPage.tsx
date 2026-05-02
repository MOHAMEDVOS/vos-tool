import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Trash2, X } from 'lucide-react'
import { phrasesApi } from '@/api/phrases'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Metric } from '@/components/ui/Metric'
import { Spinner } from '@/components/ui/Spinner'
import { Tabs } from '@/components/ui/Tabs'
import { SuccessFlash } from '@/components/ui/SuccessFlash'

type Tab = 'pending' | 'repository' | 'settings'

const TABS = [
  { id: 'pending', label: 'Pending Review' },
  { id: 'repository', label: 'Repository' },
  { id: 'settings', label: 'Learning Settings' },
]

export function PhrasesPage() {
  const [active, setActive] = useState<Tab>('pending')
  const { data: stats, isLoading } = useQuery({ queryKey: ['phrase-stats'], queryFn: phrasesApi.stats })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-t-primary">Phrase Management</h1>
        <p className="mt-1 text-sm text-vos-500">Owner tools for reviewing and tuning the rebuttal phrase repository.</p>
      </div>

      {isLoading ? (
        <Spinner />
      ) : stats ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Metric label="Total Phrases" value={stats.total_phrases} />
          <Metric label="Pending" value={stats.pending_count} />
          <Metric label="Auto Learned" value={stats.auto_learned_count} />
          <Metric label="Categories" value={stats.categories} />
        </div>
      ) : null}

      <Tabs tabs={TABS} active={active} onChange={(id) => setActive(id as Tab)} />
      {active === 'pending' && <PendingReview />}
      {active === 'repository' && <Repository />}
      {active === 'settings' && <LearningSettings />}
    </div>
  )
}

function PendingReview() {
  const qc = useQueryClient()
  const { data, isLoading, isError } = useQuery({ queryKey: ['phrases-pending'], queryFn: () => phrasesApi.pending() })
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['phrases-pending'] })
    qc.invalidateQueries({ queryKey: ['phrase-stats'] })
    qc.invalidateQueries({ queryKey: ['phrases-repository'] })
  }
  const approve = useMutation({ mutationFn: (id: string | number) => phrasesApi.approve(String(id)), onSuccess: invalidate })
  const reject = useMutation({ mutationFn: (id: string | number) => phrasesApi.reject(String(id)), onSuccess: invalidate })
  const approveAll = useMutation({ mutationFn: phrasesApi.approveAll, onSuccess: invalidate })

  if (isLoading) return <Spinner />
  if (isError) return <p className="text-sm text-ship-red">Failed to load pending phrases.</p>

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between gap-4">
        <p className="text-sm text-vos-500">{data?.length ?? 0} phrases waiting for review</p>
        <div className="flex items-center gap-3">
          <SuccessFlash show={approveAll.isSuccess} label="All Approved" />
          <Button size="sm" onClick={() => approveAll.mutate()} disabled={!data?.length || approveAll.isPending}>
            <Check size={14} /> Approve All
          </Button>
        </div>
      </div>

      {(data ?? []).map((phrase) => (
        <Card key={phrase.id} className="flex flex-col gap-3">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-t-primary">{phrase.phrase}</p>
              <p className="mt-1 text-xs text-vos-500">
                {phrase.category} آ· quality {phrase.quality_score ?? 'n/a'} آ· seen {phrase.detection_count ?? 0}أ—
              </p>
            </div>
            <div className="flex items-center gap-2">
              <SuccessFlash show={approve.isSuccess} label="Approved" />
              <Button size="sm" onClick={() => approve.mutate(phrase.id)} disabled={approve.isPending}>
                <Check size={14} /> Approve
              </Button>
              <Button size="sm" variant="danger" onClick={() => reject.mutate(phrase.id)} disabled={reject.isPending}>
                <X size={14} /> Reject
              </Button>
            </div>
          </div>
          {phrase.sample_contexts && (
            <p className="text-xs text-vos-500 italic border-l-2 border-b-subtle pl-3">{phrase.sample_contexts}</p>
          )}
        </Card>
      ))}

      {!data?.length && <p className="text-sm text-vos-500">No pending phrases right now.</p>}
    </div>
  )
}

function Repository() {
  const qc = useQueryClient()
  const [category, setCategory] = useState('General')
  const [phrase, setPhrase] = useState('')
  const [bulkText, setBulkText] = useState('')
  const { data, isLoading, isError } = useQuery({ queryKey: ['phrases-repository'], queryFn: phrasesApi.repository })
  const categories = useMemo(() => Object.keys(data ?? {}).sort(), [data])
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['phrases-repository'] })
    qc.invalidateQueries({ queryKey: ['phrase-stats'] })
  }
  const add = useMutation({ mutationFn: () => phrasesApi.add(phrase, category), onSuccess: () => { setPhrase(''); invalidate() } })
  const bulk = useMutation({
    mutationFn: () => phrasesApi.bulk(bulkText.split('\n').map((p) => p.trim()).filter(Boolean), category),
    onSuccess: () => { setBulkText(''); invalidate() },
  })
  const dedupe = useMutation({ mutationFn: phrasesApi.removeDuplicates, onSuccess: invalidate })

  if (isLoading) return <Spinner />
  if (isError) return <p className="text-sm text-ship-red">Failed to load phrase repository.</p>

  return (
    <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
      <Card className="flex flex-col gap-4">
        <Input label="Category" value={category} onChange={(e) => setCategory(e.target.value)} />
        <Input label="Single Phrase" value={phrase} onChange={(e) => setPhrase(e.target.value)} />
        <div className="flex items-center gap-3">
          <SuccessFlash show={add.isSuccess} label="Added" />
          <Button className="flex-1" onClick={() => add.mutate()} disabled={!phrase.trim() || !category.trim() || add.isPending}>
            Add Phrase
          </Button>
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wider text-vos-500">Bulk Phrases</span>
          <textarea
            value={bulkText}
            onChange={(e) => setBulkText(e.target.value)}
            rows={7}
            className="rounded-md bg-surface-input px-3 py-2 text-sm text-t-primary font-mono shadow-border outline-none focus:ring-2 focus:ring-[hsla(212,100%,48%,1)]"
          />
        </label>
        <Button onClick={() => bulk.mutate()} disabled={!bulkText.trim() || !category.trim() || bulk.isPending}>
          Import Bulk
        </Button>
        <Button variant="danger" onClick={() => dedupe.mutate()} disabled={dedupe.isPending}>
          <Trash2 size={14} /> Remove Duplicates
        </Button>
      </Card>

      <div className="flex flex-col gap-4">
        {categories.map((cat) => (
          <Card key={cat}>
            <h2 className="text-sm font-semibold text-t-primary">{cat}</h2>
            <p className="mb-3 text-xs text-vos-500">{data?.[cat]?.length ?? 0} phrases</p>
            <div className="max-h-52 overflow-y-auto text-sm text-t-primary">
              {(data?.[cat] ?? []).slice(0, 200).map((p) => (
                <div key={p} className="border-t border-b-subtle py-2">{p}</div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

function LearningSettings() {
  const qc = useQueryClient()
  const { data, isLoading, isError } = useQuery({ queryKey: ['phrase-settings'], queryFn: phrasesApi.settings })
  const [confidence, setConfidence] = useState('0.7')
  const [frequency, setFrequency] = useState('3')
  const [autoApprove, setAutoApprove] = useState('0.9')

  useEffect(() => {
    if (!data) return
    setConfidence(String(data.confidence_threshold ?? 0.7))
    setFrequency(String(data.frequency_threshold ?? 3))
    setAutoApprove(String(data.auto_approve_threshold ?? 0.9))
  }, [data])

  const update = useMutation({
    mutationFn: () => phrasesApi.updateSettings({
      confidence_threshold: Number(confidence),
      frequency_threshold: Number(frequency),
      auto_approve_threshold: Number(autoApprove),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['phrase-settings'] }),
  })

  if (isLoading) return <Spinner />
  if (isError) return <p className="text-sm text-ship-red">Failed to load learning settings.</p>

  return (
    <Card className="flex max-w-md flex-col gap-4">
      <Input label="Confidence Threshold" type="number" step="0.01" min="0.5" max="1" value={confidence} onChange={(e) => setConfidence(e.target.value)} />
      <Input label="Frequency Threshold" type="number" min="1" value={frequency} onChange={(e) => setFrequency(e.target.value)} />
      <Input label="Auto Approve Threshold" type="number" step="0.01" min="0.8" max="1" value={autoApprove} onChange={(e) => setAutoApprove(e.target.value)} />
      <div className="flex items-center gap-3">
        <SuccessFlash show={update.isSuccess} label="Saved" />
        <Button onClick={() => update.mutate()} disabled={update.isPending}>Save Settings</Button>
      </div>
    </Card>
  )
}
