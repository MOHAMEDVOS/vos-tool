import React, { useEffect, useMemo, useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { useFlaggedCalls } from '@/hooks/useDashboard'
import { Spinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import type { FlaggedCall, WordTimestamp } from '@/types/api'
import { apiUrl, authHeaders, api } from '@/api/client'
import { RefreshCw, Play, Pause, Volume2, MoreVertical, Search } from 'lucide-react'
import { CustomSelect } from '@/components/ui/Select'
import { KaraokeTranscript } from '@/components/KaraokeTranscript'

/* ─── Custom Audio Player ─────────────────────────────────────── */
interface AudioPlayerProps {
  src: string
  isLateHello?: boolean
  audioRef: React.RefObject<HTMLAudioElement | null>
  onAudioMounted?: (el: HTMLAudioElement) => void
}

function CustomAudioPlayer({ src, isLateHello, audioRef, onAudioMounted }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const requestRef = useRef<number>(0)

  const showRedAlert = isLateHello && currentTime >= 5
  const barColor = showRedAlert ? '#ef4444' : 'var(--t-primary)'

  const animate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime)
      requestRef.current = requestAnimationFrame(animate)
    }
  }

  useEffect(() => {
    if (isPlaying) {
      requestRef.current = requestAnimationFrame(animate)
    } else {
      cancelAnimationFrame(requestRef.current)
    }
    return () => cancelAnimationFrame(requestRef.current)
  }, [isPlaying])

  const togglePlay = () => {
    if (!audioRef.current) return
    if (isPlaying) audioRef.current.pause()
    else audioRef.current.play()
    setIsPlaying(!isPlaying)
  }

  const onLoadedMetadata = () => {
    if (audioRef.current) setDuration(audioRef.current.duration)
  }

  const onEnded = () => {
    setIsPlaying(false)
    setCurrentTime(0)
  }

  const formatTime = (time: number) => {
    const mins = Math.floor(time / 60)
    const secs = Math.floor(time % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const percent = x / rect.width
    audioRef.current.currentTime = percent * duration
  }

  const bars = Array.from({ length: 60 }).map((_, i) => {
    const h = Math.sin(i * 0.4) * 5 + 10
    return Math.max(3, h)
  })

  return (
    <div className="flex items-center gap-4 w-full max-w-md bg-c-base rounded-full p-2 pr-5 border border-b-subtle shadow-2xl">
      <audio
        ref={el => {
          (audioRef as React.MutableRefObject<HTMLAudioElement | null>).current = el
          if (el) onAudioMounted?.(el)
        }}
        src={src}
        onLoadedMetadata={onLoadedMetadata}
        onEnded={onEnded}
      />

      {/* Play Button */}
      <motion.button
        whileTap={{ scale: 0.9 }}
        onClick={togglePlay}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-t-primary text-[var(--surface-card)] transition-transform hover:scale-105"
      >
        {isPlaying ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" className="ml-0.5" />}
      </motion.button>

      {/* Waveform Container */}
      <div className="flex flex-col flex-1 gap-0.5 overflow-hidden">
        <div
          className="relative h-6 cursor-pointer overflow-hidden"
          onClick={handleSeek}
        >
          {/* Background Layer */}
          <div className="absolute inset-0 flex items-center gap-[2px] pointer-events-none">
            {bars.map((h, i) => (
              <div
                key={i}
                className="flex-1 min-w-[2px] rounded-full transition-colors duration-500"
                style={{ height: `${h}px`, backgroundColor: showRedAlert ? 'rgba(239, 68, 68, 0.15)' : 'var(--b-medium)' }}
              />
            ))}
          </div>

          {/* Progress Layer */}
          <div
            className="absolute inset-0 flex items-center gap-[2px] pointer-events-none"
            style={{
              maskImage: `linear-gradient(to right, white ${(currentTime / duration) * 100}%, transparent ${(currentTime / duration) * 100}%)`,
              WebkitMaskImage: `linear-gradient(to right, white ${(currentTime / duration) * 100}%, transparent ${(currentTime / duration) * 100}%)`
            }}
          >
            {bars.map((h, i) => (
              <div
                key={i}
                className={`flex-1 min-w-[2px] rounded-full transition-all duration-500 ${isPlaying ? 'animate-waveform-pulse' : ''}`}
                style={{
                  height: `${h}px`,
                  backgroundColor: barColor,
                  opacity: 0.95,
                  animationDelay: `${i * 0.05}s`
                }}
              />
            ))}
          </div>
        </div>
        <div className="flex justify-between items-center px-0.5">
          <span className={`text-[10px] font-black uppercase tracking-widest transition-colors duration-300 ${currentTime >= 5 ? 'text-ship-red' : 'text-vos-400'}`}>
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
          <div className="flex gap-2 items-center text-vos-600">
            <Volume2 size={10} />
            <MoreVertical size={10} />
          </div>
        </div>
      </div>
    </div>
  )
}

type IssueFilter = 'All Issues' | 'Releasing Only' | 'Late Hello Only' | 'No Rebuttals Only'


export function CallReviewPage() {
  const { data: calls, isLoading, isError } = useFlaggedCalls()
  const [issueFilter, setIssueFilter] = useState<IssueFilter>('All Issues')
  const [agentFilter, setAgentFilter] = useState('All Agents')
  const [search, setSearch] = useState('')

  const agents = useMemo(() => {
    const names = [...new Set((calls ?? []).map((call) => call['Agent Name']).filter(Boolean) as string[])]
    return ['All Agents', ...names.sort()]
  }, [calls])

  const filtered = useMemo<FlaggedCall[]>(() => {
    let rows = calls ?? []
    if (issueFilter === 'Releasing Only') rows = rows.filter((row) => row['Releasing Detection'] === 'Yes')
    if (issueFilter === 'Late Hello Only') rows = rows.filter((row) => row['Late Hello Detection'] === 'Yes')
    if (issueFilter === 'No Rebuttals Only') rows = rows.filter((row) => row['Rebuttal Detection'] === 'No')
    if (agentFilter !== 'All Agents') rows = rows.filter((row) => row['Agent Name'] === agentFilter)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      rows = rows.filter((row) => JSON.stringify(row).toLowerCase().includes(q))
    }
    return rows
  }, [calls, issueFilter, agentFilter, search])

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (isError) return <p className="text-ship-red text-sm">Failed to load flagged calls.</p>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-t-primary tracking-tight">Call Review</h1>
        <p className="text-vos-400 text-sm">Listen to flagged calls. Audio is loaded securely from the backend.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <CustomSelect
          options={['All Issues', 'Releasing Only', 'Late Hello Only', 'No Rebuttals Only']}
          value={issueFilter}
          onChange={(v) => setIssueFilter(v as IssueFilter)}
          className="w-48"
        />

        <CustomSelect
          options={agents}
          value={agentFilter}
          onChange={setAgentFilter}
          className="w-48"
        />

        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-vos-600" size={14} />
          <input
            type="text"
            placeholder="Search phone / filename..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-[38px] bg-c-base border border-b-subtle rounded-md pl-9 pr-3 py-1.5 text-sm text-t-primary placeholder:text-vos-600 focus:outline-none focus:border-b-strong focus:ring-2 focus:ring-c-raised/50 transition-all"
          />
        </div>
      </div>

      <p className="text-sm text-vos-600">Showing {filtered.length} of {calls?.length ?? 0} flagged calls</p>

      {filtered.length === 0 && <p className="py-4 text-sm text-vos-400">No calls match the selected filters.</p>}

      <div className="flex flex-col gap-4">
        {filtered.map((call, index) => <CallCard key={index} call={call} />)}
      </div>
    </div>
  )
}

function CallCard({ call }: { call: FlaggedCall }) {
  const issues: string[] = []
  if (call['Releasing Detection'] === 'Yes') issues.push('Releasing')
  if (call['Late Hello Detection'] === 'Yes') issues.push('Late Hello')
  if (call['Rebuttal Detection'] === 'No') issues.push('No Rebuttals')

  const filePath = call['File Path'] as string | undefined
  const fileName = (call['File Name'] ?? call.filename ?? call.Filename) as string | undefined
  const phone = call['Phone Number'] as string | undefined

  const audioQuery = filePath
    ? `file_path=${encodeURIComponent(filePath)}`
    : fileName
      ? `filename=${encodeURIComponent(fileName)}`
      : phone
        ? `phone=${encodeURIComponent(phone)}`
        : null

  const audioSrc = audioQuery ? `/api/system/recordings/serve?${audioQuery}` : null

  const transcription = call.Transcription?.trim()?.replace(/^n\/a$/i, '') || ''

  // Shared audioRef passed to both the player and the karaoke transcript
  const audioRef = useRef<HTMLAudioElement | null>(null)
  // State version so KaraokeTranscript re-renders when the audio element mounts
  const [audioEl, setAudioEl] = useState<HTMLAudioElement | null>(null)

  // Word timestamps — fetched on mount, independent of audio loading
  const [words, setWords] = useState<WordTimestamp[]>([])

  useEffect(() => {
    if (!audioQuery) return
    let cancelled = false
    api.get<{ words: WordTimestamp[] }>(`/api/system/recordings/words?${audioQuery}`)
      .then(res => { if (!cancelled) setWords(res.words ?? []) })
      .catch(() => { if (!cancelled) setWords([]) })
    return () => { cancelled = true }
  }, [audioQuery])

  return (
    <div className="flex flex-col gap-3 rounded-lg bg-surface-card shadow-card p-5 w-full border border-b-subtle">

      {/* Top row: name + phone + issue badges */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-medium text-vos-black">{call['Agent Name'] ?? 'Unknown Agent'}</span>
        <span className="text-sm text-vos-600">{call['Phone Number'] ?? ''}</span>
        <div className="ml-auto flex flex-wrap gap-2">
          {issues.map((issue) => <Badge key={issue} variant="danger">{issue}</Badge>)}
        </div>
      </div>

      {/* Body: audio left, transcription right */}
      <div className={transcription ? 'grid grid-cols-1 gap-3 lg:grid-cols-[1fr_340px]' : ''}>

        {/* Left — audio + metadata */}
        <div className="flex flex-col gap-3">
          {audioSrc ? (
            <AuthenticatedAudio
              src={audioSrc}
              isLateHello={call['Late Hello Detection'] === 'Yes'}
              audioRef={audioRef}
              onAudioMounted={setAudioEl}
            />
          ) : (
            <p className="text-sm text-ship-red">Audio not available{'—'}no file path, filename, or phone number.</p>
          )}

          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-vos-black">
            {call.Disposition && (
              <span>
                <span className="block text-xs font-medium uppercase tracking-wider text-vos-400 mb-0.5">Disposition</span>
                {call.Disposition}
              </span>
            )}
            {call['Dialer Name'] && (
              <span>
                <span className="block text-xs font-medium uppercase tracking-wider text-vos-400 mb-0.5">Dialer</span>
                {call['Dialer Name']}
              </span>
            )}
            {(call['Audit Type'] ?? call.audit_type) && (
              <span>
                <span className="block text-xs font-medium uppercase tracking-wider text-vos-400 mb-0.5">Type</span>
                {String(call['Audit Type'] ?? call.audit_type)}
              </span>
            )}
          </div>
        </div>

        {/* Right — karaoke transcript (falls back to plain text if no words) */}
        {transcription && (
          <KaraokeTranscript
            words={words}
            audioRef={audioRef}
            audioEl={audioEl}
            fallbackText={transcription}
          />
        )}
      </div>

    </div>
  )
}

interface AuthenticatedAudioProps {
  src: string
  isLateHello?: boolean
  audioRef: React.RefObject<HTMLAudioElement | null>
  onAudioMounted?: (el: HTMLAudioElement) => void
}

function AuthenticatedAudio({ src, isLateHello, audioRef, onAudioMounted }: AuthenticatedAudioProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    async function loadAudio() {
      setBlobUrl(null); setError(null)
      try {
        const response = await fetch(apiUrl(src), { headers: authHeaders() })
        if (!response.ok) {
          let detail = `HTTP ${response.status}`
          try { const json = await response.json(); detail = json.detail ?? detail } catch { /* ignore */ }
          throw new Error(detail)
        }
        const blob = await response.blob()
        if (blob.size === 0) throw new Error('Empty audio response')
        objectUrl = URL.createObjectURL(blob)
        if (!cancelled) setBlobUrl(objectUrl)
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    }
    loadAudio()
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [src])

  if (error) return <p className="text-sm text-ship-red">Audio failed to load: {error}</p>
  if (!blobUrl) return (
    <div className="flex h-10 items-center gap-3 rounded-md bg-vos-50 px-4 text-sm text-vos-600">
      <Spinner size="sm" /> Loading audio...
    </div>
  )
  return <CustomAudioPlayer src={blobUrl} isLateHello={isLateHello} audioRef={audioRef} onAudioMounted={onAudioMounted} />
}
