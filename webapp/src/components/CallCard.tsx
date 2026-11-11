import React, { useEffect, useMemo, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { Spinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import type { FlaggedCall, WordTimestamp } from '@/types/api'
import { apiUrl, authHeaders, api } from '@/api/client'
import { Play, Pause, Volume2, MoreVertical, Download } from 'lucide-react'
import { KaraokeTranscript } from '@/components/KaraokeTranscript'
import { getCallIssues } from '@/utils/audit'

interface AudioPlayerProps {
  src: string
  isLateHello?: boolean
  audioRef: React.RefObject<HTMLAudioElement | null>
  onAudioMounted?: (el: HTMLAudioElement) => void
  downloadFileName?: string
}

function CustomAudioPlayer({ src, isLateHello, audioRef, onAudioMounted, downloadFileName }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)

  const showRedAlert = isLateHello && currentTime >= 5
  const barColor = showRedAlert ? '#ef4444' : 'var(--t-primary)'

  useEffect(() => {
    let frame = 0
    if (isPlaying) {
      const animate = () => {
        const audio = audioRef.current
        if (!audio) return
        setCurrentTime(audio.currentTime)
        frame = requestAnimationFrame(animate)
      }
      frame = requestAnimationFrame(animate)
    }
    return () => cancelAnimationFrame(frame)
  }, [audioRef, isPlaying])

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

      <motion.button
        whileTap={{ scale: 0.9 }}
        onClick={togglePlay}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-t-primary text-[var(--surface-card)] transition-transform hover:scale-105"
      >
        {isPlaying ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" className="ml-0.5" />}
      </motion.button>

      {downloadFileName && (
        <a
          href={src}
          download={downloadFileName}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-vos-600 transition-colors hover:bg-vos-50 hover:text-t-primary"
          title="Download recording"
        >
          <Download size={16} />
        </a>
      )}

      <div className="flex flex-col flex-1 gap-0.5 overflow-hidden">
        <div
          className="relative h-6 cursor-pointer overflow-hidden"
          onClick={handleSeek}
        >
          <div className="absolute inset-0 flex items-center gap-[2px] pointer-events-none">
            {bars.map((h, i) => (
              <div
                key={i}
                className="flex-1 min-w-[2px] rounded-full transition-colors duration-500"
                style={{ height: `${h}px`, backgroundColor: showRedAlert ? 'rgba(239, 68, 68, 0.15)' : 'var(--b-medium)' }}
              />
            ))}
          </div>

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

export function CallCard({ call }: { call: FlaggedCall }) {
  const issues = getCallIssues(call)

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

  const downloadFileName = useMemo(() => {
    const base = (fileName || `${call['Agent Name'] ?? 'call'}_${phone ?? ''}`).trim()
    const cleaned = base.split(/[/\\]/).pop() || 'recording'
    return /\.[a-z0-9]{2,4}$/i.test(cleaned) ? cleaned : `${cleaned}.mp3`
  }, [fileName, call, phone])

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

      <div className="flex flex-wrap items-center gap-3">
        <span className="font-medium text-vos-black">{call['Agent Name'] ?? 'Unknown Agent'}</span>
        <span className="text-sm text-vos-600">{call['Phone Number'] ?? ''}</span>
        <div className="ml-auto flex flex-wrap gap-2">
          {issues.map((issue) => <Badge key={issue} variant="danger">{issue}</Badge>)}
        </div>
      </div>

      <div className={transcription ? 'grid grid-cols-1 gap-3 lg:grid-cols-[1fr_340px]' : ''}>

        <div className="flex flex-col gap-3">
          {audioSrc ? (
            <AuthenticatedAudio
              src={audioSrc}
              isLateHello={call['Late Hello Detection'] === 'Yes'}
              audioRef={audioRef}
              onAudioMounted={setAudioEl}
              downloadFileName={downloadFileName}
            />
          ) : (
            <p className="text-sm text-ship-red">Audio not available{'—'}no file path, filename, or phone number.</p>
          )}

          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-vos-black">
            {(() => {
              // Priority: Use the pre-formatted 'Time' field first, then fall back to raw timestamps
              const displayTime = call.Time || call.Timestamp || call.timestamp
              if (!displayTime) return null
              
              let displayStr = String(displayTime)
              if (/^\d{13}$/.test(displayStr)) {
                displayStr = new Date(Number(displayStr)).toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: 'numeric',
                  minute: '2-digit',
                  hour12: true
                })
              }
              
              return (
                <span>
                  <span className="block text-xs font-medium uppercase tracking-wider text-vos-400 mb-0.5">Time</span>
                  {displayStr}
                </span>
              )
            })()}
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
  downloadFileName?: string
}

function AuthenticatedAudio({ src, isLateHello, audioRef, onAudioMounted, downloadFileName }: AuthenticatedAudioProps) {
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
  return <CustomAudioPlayer src={blobUrl} isLateHello={isLateHello} audioRef={audioRef} onAudioMounted={onAudioMounted} downloadFileName={downloadFileName} />
}
