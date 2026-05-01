import { useMemo, useState, useEffect } from 'react'
import type { AgentAuditRow } from '@/types/api'
import { Badge } from '@/components/ui/Badge'

import { AGENT_AUDIT_COLUMN_ORDER, HIDDEN_COLUMNS, normalizeRow, DETECTION_COLS, detectionVariant } from '@/utils/audit'
import { ArrowUp, ArrowDown, Copy, Check, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

interface Props {
  rows: AgentAuditRow[]
  getRowClassName?: (row: Record<string, unknown>, index: number) => string
  leftActions?: React.ReactNode
}

export function AuditTable({ rows, leftActions }: Props) {
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [search, setSearch] = useState('')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [expandedCell, setExpandedCell] = useState<{ val: any; col: string } | null>(null)
  const [isTableCopied, setIsTableCopied] = useState(false)

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpandedCell(null)
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [])

  const { columns, rowData } = useMemo(() => {
    const columns = [...AGENT_AUDIT_COLUMN_ORDER]
    const normalized = rows.map(normalizeRow)

    let filtered = normalized
    if (search) {
      const q = search.toLowerCase()
      filtered = filtered.filter((r) => 
        Object.values(r).some((v) => String(v).toLowerCase().includes(q))
      )
    }

    if (sortCol) {
      filtered = [...filtered].sort((a, b) => {
        const va = String(a[sortCol] ?? '')
        const vb = String(b[sortCol] ?? '')
        return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
      })
    }

    return { columns, rowData: filtered }
  }, [rows, search, sortCol, sortDir])

  const handleSort = (col: string) => {
    if (sortCol === col) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
  }

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleCopyRows = () => {
    const tsv = rowData.map(row => 
      columns.map(col => {
        const val = row[col]
        if (val == null) return ""
        return String(val)
          .replace(/\t/g, " ")
          .replace(/\r\n/g, " ")
          .replace(/\n/g, " ")
          .replace(/\r/g, " ")
      }).join("\t")
    ).join("\n")

    navigator.clipboard.writeText(tsv)
    setIsTableCopied(true)
    setTimeout(() => setIsTableCopied(false), 3000)
  }

  if (!rows.length) {
    return <p className="py-8 text-sm text-t-muted text-center bg-c-base rounded-lg border border-b-subtle">No records found.</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-xl border border-b-subtle overflow-hidden bg-c-base shadow-2xl relative">
        <div className="overflow-auto max-h-[320px] custom-scrollbar">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-30 bg-c-base shadow-[inset_0_-1px_0_rgba(255,255,255,0.05)]">
              <tr>
                {columns.map((col) => (
                  <th 
                    key={col} 
                    onClick={() => handleSort(col)}
                    className="px-3 py-2.5 text-left text-[9px] font-black uppercase tracking-[0.15em] text-t-primary whitespace-nowrap border-r border-b-subtle last:border-r-0 cursor-pointer hover:bg-c-raised/50 transition-colors group"
                  >
                    <div className="flex items-center gap-2">
                      {col}
                      <div className={`transition-opacity ${sortCol === col ? 'opacity-100' : 'opacity-0 group-hover:opacity-30'}`}>
                        {sortCol === col && sortDir === 'desc' ? <ArrowDown size={10} /> : <ArrowUp size={10} />}
                      </div>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-b-subtle">
              {rowData.map((row, idx) => (
                <tr key={idx} className="hover:bg-c-raised/50 transition-colors group/row">
                  {columns.map((col) => {
                    const val = row[col]
                    const isDetection = DETECTION_COLS.has(col)
                    const variant = isDetection ? detectionVariant(val, col) : null
                    const isLargeText = col === 'Transcription' || col === 'Reason for calling'
                    const copyId = `${idx}-${col}`

                    let cellBg = ''
                    let textColor = 'text-t-primary'
                    if (isDetection && val != null && val !== '') {
                      if (variant === 'danger') {
                        cellBg = 'bg-semantic-error/10 text-semantic-error'
                        textColor = 'text-t-primary font-black'
                      }
                    }

                    return (
                      <td 
                        key={col} 
                        onDoubleClick={() => setExpandedCell({ val, col })}
                        className={`px-3 py-2 border-r border-b-subtle last:border-r-0 align-top group/cell relative cursor-default overflow-hidden ${cellBg} ${
                          isLargeText ? 'min-w-[100px] max-w-[180px]' : 'whitespace-nowrap max-w-[150px]'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 h-full">
                          {isDetection ? (
                            <span className={`text-[10px] font-black uppercase tracking-widest ${textColor}`}>
                              {val == null || val === '' ? '—' : String(val)}
                            </span>
                          ) : (
                            <span 
                              className={`block ${isLargeText ? 'text-t-primary leading-relaxed opacity-90' : 'text-t-primary font-medium truncate'} text-[11px]`}
                              style={isLargeText ? {
                                display: '-webkit-box',
                                WebkitLineClamp: 1,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden'
                              } : {}}
                            >
                              {val != null ? String(val) : '—'}
                            </span>
                          )}
                          
                          {val != null && val !== '' && col === 'Agent Name' && (
                            <button 
                              onClick={() => copyToClipboard(String(val), copyId)}
                              className="opacity-0 group-hover/cell:opacity-100 p-1 rounded hover:bg-c-raised transition-all text-vos-500 hover:text-t-primary shrink-0"
                            >
                              <AnimatePresence mode="wait">
                                {copiedId === copyId ? (
                                  <motion.div key="check" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                                    <Check size={12} className="text-green-500" />
                                  </motion.div>
                                ) : (
                                  <motion.div key="copy" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                                    <Copy size={12} />
                                  </motion.div>
                                )}
                              </AnimatePresence>
                            </button>
                          )}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 mt-2">
        <div className="flex items-center gap-4">
          {leftActions}
        </div>

        <div className="flex items-center gap-4">
          <AnimatePresence>
            {isTableCopied && (
              <motion.span 
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="text-[10px] text-semantic-success font-black uppercase tracking-widest"
              >
                Copied — Paste into your Google Sheet
              </motion.span>
            )}
          </AnimatePresence>
          <button
            onClick={handleCopyRows}
            className="group relative px-6 py-2.5 rounded-full bg-transparent hover:bg-c-raised border border-b-strong text-t-primary text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-300 active:scale-95 flex items-center gap-3 overflow-hidden"
          >
            {isTableCopied ? <Check size={14} className="text-semantic-success" /> : <Copy size={14} className="text-t-primary transition-colors" />}
            <span className="relative z-10">Copy {rowData.length} rows (no header)</span>
          </button>
        </div>
      </div>

      <AnimatePresence>
        {expandedCell && (
          <>
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[100] bg-surface-page/80 backdrop-blur-sm flex items-center justify-center p-8"
              onClick={() => setExpandedCell(null)}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.9, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.9, y: 20 }}
                className="w-full max-w-2xl bg-c-base border-2 border-ship-red rounded-2xl shadow-[0_0_50px_rgba(239,68,68,0.2)] overflow-hidden"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="px-6 py-4 border-b border-b-subtle flex items-center justify-between bg-c-raised/50">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-8 bg-ship-red rounded-full" />
                    <div>
                      <h3 className="text-xs font-black uppercase tracking-[0.2em] text-vos-500">Focused View</h3>
                      <p className="text-[10px] text-t-primary font-black uppercase tracking-wider opacity-60">{expandedCell.col}</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setExpandedCell(null)}
                    className="p-2 rounded-full hover:bg-c-raised text-t-muted hover:text-t-primary transition-all"
                  >
                    <X size={20} />
                  </button>
                </div>
                <div className="p-8 max-h-[60vh] overflow-auto custom-scrollbar">
                  <div className="text-base text-t-primary font-medium leading-relaxed whitespace-pre-wrap select-all selection:bg-ship-red selection:text-t-primary">
                    {String(expandedCell.val)}
                  </div>
                </div>
                <div className="px-6 py-4 bg-c-raised/30 border-t border-b-subtle flex justify-between items-center text-[9px] font-black uppercase tracking-widest text-t-muted">
                  <span>Double click or ESC to close</span>
                  <div className="flex gap-4">
                    <span className="flex items-center gap-1.5"><kbd className="px-1.5 py-0.5 rounded bg-c-base border border-b-medium text-t-primary">ESC</kbd> Close</span>
                    <span className="flex items-center gap-1.5"><kbd className="px-1.5 py-0.5 rounded bg-c-base border border-b-medium text-t-primary">CTRL+C</kbd> Copy</span>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
