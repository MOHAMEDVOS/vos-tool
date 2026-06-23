import type { AgentAuditRow } from '@/types/api'

// Exact column order from app.py:2457-2471
export const AGENT_AUDIT_COLUMN_ORDER = [
  'Agent Name',
  'Phone Number',
  'Disposition',
  'Releasing Detection',
  'Late Hello Detection',
  'Long VM/Dead Detection',
  'Rebuttal Detection',
  'Transcription',
  'Dialer Name',
  'Agent Intro',
  'Owner Name',
  'Reason for calling',
  'Intro Score',
  'Status',
  'Time',
] as const

// Columns to hide from display (kept in data for CSV) - matches app.py:2442
export const HIDDEN_COLUMNS = new Set([
  'File Name', 'File Path', 'Call Duration', 'Confidence Score', 'audit_timestamp',
])

// Normalize column names to match display order
export function normalizeRow(row: AgentAuditRow): AgentAuditRow {
  const out: AgentAuditRow = { ...row }
  // Rename username to Auditor
  if ('username' in out) {
    out['Auditor'] = out['username']
    delete out['username']
  }
  // Rename audit_type to Audit Type
  if ('audit_type' in out) {
    out['Audit Type'] = out['audit_type']
    delete out['audit_type']
  }
  // Normalize "Reason for Calling" variants
  if ('Reason for Calling' in out && !('Reason for calling' in out)) {
    out['Reason for calling'] = out['Reason for Calling']
    delete out['Reason for Calling']
  }
  // Normalize snake_case dialer_name → "Dialer Name"
  if ('dialer_name' in out && !('Dialer Name' in out)) {
    out['Dialer Name'] = out['dialer_name'] as string
    delete out['dialer_name']
  }
  // Extract dialer name from file path when missing
  // Folder pattern: "{agent}-{date}_{counter} {dialer_name}/file.mp3"
  if (!out['Dialer Name']) {
    const fp = (out['File Path'] ?? out['file_path'] ?? '') as string
    if (fp) {
      const folder = fp.replace(/\\/g, '/').split('/').slice(-2, -1)[0] ?? ''
      const spaceIdx = folder.lastIndexOf(' ')
      if (spaceIdx !== -1) {
        out['Dialer Name'] = folder.slice(spaceIdx + 1)
      }
    }
  }
  
  // Explicitly map Time from metadata or root if it exists
  if (!out['Time'] && (out as any).metadata?.Time) {
    out['Time'] = (out as any).metadata.Time
  }
  
  return out
}

// True when the long VM/Dead-call detection holds a real flag label (e.g. "Voicemail 28s").
export function isLongCallFlagged(val: unknown): boolean {
  return val != null && val !== '' && val !== 'No'
}

// Long VM/Dead rows are deterministic from the CSV, so re-running an audit for the same
// agent+date re-inserts identical rows. Call Log ID isn't persisted, so dedupe these flagged
// rows on a natural key (agent + phone + label, e.g. "Voicemail 28s"). Non-long rows pass
// through untouched (audio rows can legitimately repeat across runs).
export function dedupeLongCallRows<T extends AgentAuditRow>(rows: T[]): T[] {
  const seen = new Set<string>()
  const out: T[] = []
  for (const r of rows) {
    if (isLongCallFlagged(r['Long VM/Dead Detection'])) {
      const key = [
        String(r['Agent Name'] ?? '').trim().toLowerCase(),
        String(r['Phone Number'] ?? '').trim(),
        String(r['Long VM/Dead Detection'] ?? '').trim().toLowerCase(),
      ].join('|')
      if (seen.has(key)) continue
      seen.add(key)
    }
    out.push(r)
  }
  return out
}

// Flag logic - mirrors app.py:2398-2403 exactly, plus long VM/Dead-call detection
export function isRowFlagged(row: AgentAuditRow): boolean {
  return (
    row['Releasing Detection'] === 'Yes' ||
    row['Late Hello Detection'] === 'Yes' ||
    isLongCallFlagged(row['Long VM/Dead Detection']) ||
    row['Rebuttal Detection'] === 'No'
  )
}

// Badge variant for detection columns
export function detectionVariant(val: unknown, col: string) {
  if (col === 'Rebuttal Detection') {
    return val === 'Yes' ? 'success' : val === 'No' ? 'danger' : 'muted'
  }
  if (col === 'Releasing Detection' || col === 'Late Hello Detection') {
    return val === 'Yes' ? 'danger' : 'success'
  }
  if (col === 'Long VM/Dead Detection') {
    return isLongCallFlagged(val) ? 'danger' : 'success'
  }
  return 'muted'
}

const DETECTION_COLS = new Set([
  'Releasing Detection', 'Late Hello Detection', 'Long VM/Dead Detection', 'Rebuttal Detection',
])
export { DETECTION_COLS }
