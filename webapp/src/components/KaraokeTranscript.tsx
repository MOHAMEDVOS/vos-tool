import React, { useEffect, useMemo, useRef, useCallback, useState } from 'react'
import type { WordTimestamp } from '@/types/api'

interface Props {
  words: WordTimestamp[]
  audioRef: React.RefObject<HTMLAudioElement | null>
  audioEl?: HTMLAudioElement | null
  fallbackText?: string
}

// Binary search: find the index of the word active at `time`.
// Returns -1 when time is before the first word or no match.
function findActiveIndex(words: WordTimestamp[], time: number): number {
  if (!words.length) return -1
  let lo = 0
  let hi = words.length - 1
  let result = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const w = words[mid]
    if (time >= w.start && time <= w.end) {
      return mid
    }
    if (time < w.start) {
      hi = mid - 1
    } else {
      result = mid   // time > w.end — remember last word before current time
      lo = mid + 1
    }
  }
  return result
}

// Group consecutive words by speaker so we can render speaker labels.
interface Segment {
  speaker: string | null
  startIdx: number
  endIdx: number   // inclusive
}

function buildSegments(words: WordTimestamp[]): Segment[] {
  if (!words.length) return []
  const segments: Segment[] = []
  let seg: Segment = { speaker: words[0].speaker ?? null, startIdx: 0, endIdx: 0 }
  for (let i = 1; i < words.length; i++) {
    const sp = words[i].speaker ?? null
    if (sp === seg.speaker) {
      seg.endIdx = i
    } else {
      segments.push(seg)
      seg = { speaker: sp, startIdx: i, endIdx: i }
    }
  }
  segments.push(seg)
  return segments
}

const SPEAKER_COLORS: Record<string, string> = {
  A: 'text-t-primary',
  B: 'text-vos-600',
  C: 'text-vos-500',
  D: 'text-vos-400',
}

function speakerColor(sp: string | null): string {
  if (!sp) return 'text-vos-400'
  return SPEAKER_COLORS[sp] ?? 'text-vos-400'
}

export function KaraokeTranscript({ words, audioRef, audioEl, fallbackText }: Props) {
  const [activeIdx, setActiveIdx] = useState(-1)
  const rafRef = useRef<number>(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const wordRefs = useRef<(HTMLSpanElement | null)[]>([])
  const audioNodeRef = useRef<HTMLAudioElement | null>(null)
  const segments = useMemo(() => buildSegments(words), [words])
  const lastScrolledIdx = useRef<number>(-1)
  const userScrollingUntil = useRef<number>(0)   // timestamp — pause auto-scroll when user scrolls

  const setWordRef = useCallback((index: number, element: HTMLSpanElement | null) => {
    wordRefs.current[index] = element
  }, [])

  // Rebuild segments only when words change
  useEffect(() => {
    wordRefs.current = new Array(words.length).fill(null)
    // Reset the highlighted word when the transcript changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveIdx(-1)
    lastScrolledIdx.current = -1
  }, [words])

  // Detect manual scroll — pause auto-scroll for 3 s
  useEffect(() => {
    const box = containerRef.current
    if (!box) return
    const onScroll = () => { userScrollingUntil.current = Date.now() + 3000 }
    box.addEventListener('scroll', onScroll, { passive: true })
    return () => box.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    const audio = audioEl ?? audioRef.current
    if (!audio || !words.length) return
    audioNodeRef.current = audio

    const tick = () => {
      const currentAudio = audioNodeRef.current
      if (!currentAudio) return
      const idx = findActiveIndex(words, currentAudio.currentTime)
      setActiveIdx((current) => current === idx ? current : idx)

      const box = containerRef.current
      const word = wordRefs.current[idx]
      const userScrolling = Date.now() < userScrollingUntil.current
      if (idx >= 0 && idx !== lastScrolledIdx.current && word && box && !userScrolling) {
        const wordRect = word.getBoundingClientRect()
        const boxRect = box.getBoundingClientRect()
        const wordBottomRelative = wordRect.bottom - boxRect.top
        if (wordBottomRelative > boxRect.height) {
          const newScrollTop = box.scrollTop + (wordBottomRelative - boxRect.height) + 8
          box.scrollTo({ top: newScrollTop, behavior: 'instant' })
        }
        lastScrolledIdx.current = idx
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    const start = () => { rafRef.current = requestAnimationFrame(tick) }
    const stop  = () => cancelAnimationFrame(rafRef.current)
    const reset = () => { stop(); setActiveIdx(-1) }
    const onSeeked = () => setActiveIdx(findActiveIndex(words, audio.currentTime))

    audio.addEventListener('play',   start)
    audio.addEventListener('pause',  stop)
    audio.addEventListener('ended',  reset)
    audio.addEventListener('seeked', onSeeked)

    return () => {
      stop()
      audio.removeEventListener('play',   start)
      audio.removeEventListener('pause',  stop)
      audio.removeEventListener('ended',  reset)
      audio.removeEventListener('seeked', onSeeked)
    }
  }, [words, audioRef, audioEl])

  // Click a word → seek audio to its start time
  const handleWordClick = (start: number) => {
    const audio = audioNodeRef.current ?? audioRef.current
    if (!audio) return
    audio.currentTime = start
    if (audio.paused) audio.play()
  }

  // No word timestamps — fall back to plain text
  if (!words.length) {
    if (!fallbackText) return null
    return (
      <div className="flex flex-col rounded-lg border border-b-medium bg-c-deep overflow-hidden">
        <div className="px-3 py-2 border-b border-b-medium shrink-0">
          <span className="text-[9px] font-black uppercase tracking-[0.18em] text-vos-400">Transcription</span>
        </div>
        <div className="flex-1 overflow-y-auto max-h-[220px] px-3 py-2.5 custom-scrollbar">
          <p className="text-[10px] leading-relaxed text-t-label whitespace-pre-wrap">{fallbackText}</p>
        </div>
      </div>
    )
  }

  const hasSpeakers = words.some(w => w.speaker)

  return (
    <div className="flex flex-col rounded-lg border border-b-medium bg-c-deep overflow-hidden">
      <div className="px-3 py-2 border-b border-b-medium shrink-0 flex items-center gap-2">
        <span className="text-[9px] font-black uppercase tracking-[0.18em] text-vos-400">Transcription</span>
        <span className="text-[9px] uppercase tracking-widest text-vos-600 ml-auto">click word to seek</span>
      </div>

      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto max-h-[220px] px-3 py-2.5 custom-scrollbar"
      >
        {hasSpeakers ? (
          // Speaker-segmented layout
          segments.map((seg, si) => (
            <div key={si}>
              <span className={`text-[9px] font-bold uppercase tracking-widest mr-1.5 ${speakerColor(seg.speaker)}`}>
                {seg.speaker ?? '?'}:
              </span>
              {words.slice(seg.startIdx, seg.endIdx + 1).map((w, wi) => {
                const globalIdx = seg.startIdx + wi
                return (
                  <WordSpan
                    key={globalIdx}
                    word={w.word}
                    isActive={activeIdx === globalIdx}
                    isPast={activeIdx > globalIdx}
                    onClick={() => handleWordClick(w.start)}
                    ref={el => setWordRef(globalIdx, el)}
                  />
                )
              })}
            </div>
          ))
        ) : (
          // Flat layout — no speakers
          <p className="text-[10px] leading-relaxed">
            {words.map((w, i) => (
              <WordSpan
                key={i}
                word={w.word}
                isActive={activeIdx === i}
                isPast={activeIdx > i}
                onClick={() => handleWordClick(w.start)}
                ref={el => setWordRef(i, el)}
              />
            ))}
          </p>
        )}
      </div>
    </div>
  )
}

interface WordSpanProps {
  word: string
  isActive: boolean
  isPast: boolean
  onClick: () => void
  ref: (el: HTMLSpanElement | null) => void
}

function WordSpan({ word, isActive, isPast, onClick, ref }: WordSpanProps) {
  return (
    <span
      ref={ref}
      onClick={onClick}
      className={[
        'inline-block cursor-pointer rounded px-0.5 mx-[1px] text-[10px] transition-all duration-75 select-none',
        isActive
          ? 'bg-t-primary text-[var(--surface-card)] font-semibold scale-[1.05]'
          : isPast
            ? 'text-vos-600'
            : 'text-t-label hover:text-t-primary hover:bg-c-raised',
      ].join(' ')}
    >
      {word}
    </span>
  )
}
