import type { AgentAuditRow, FlaggedCall } from '@/types/api'
import type { AgentDeductionRow } from '@/pages/ActionsPage'

// Exact column order from app.py:2457-2471
export const AGENT_AUDIT_COLUMN_ORDER = [
  'Agent Name',
  'Phone Number',
  'Disposition',
  'Releasing Detection',
  'Late Hello Detection',
  'Long VM/Dead Detection',
  'Rebuttal Detection',
  'Wrong Dispo Detection',
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
  if ('username' in out) {
    out['Auditor'] = out['username']
    delete out['username']
  }
  if ('audit_type' in out) {
    out['Audit Type'] = out['audit_type']
    delete out['audit_type']
  }
  if ('Reason for Calling' in out && !('Reason for calling' in out)) {
    out['Reason for calling'] = out['Reason for Calling']
    delete out['Reason for Calling']
  }
  if ('dialer_name' in out && !('Dialer Name' in out)) {
    out['Dialer Name'] = out['dialer_name'] as string
    delete out['dialer_name']
  }
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

  const metadataTime = row.metadata?.['Time']
  if (!out['Time'] && typeof metadataTime === 'string') {
    out['Time'] = metadataTime
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

// A "No" Rebuttal Detection where the owner never had anything to rebut, or
// closed the call before the agent got a turn, or the transcript was empty,
// isn't a fair flag -- see analyzer/objection_gate.py and
// docs/REBUTTAL_FALSE_FLAGS.md. "unparseable" (real content, no speaker
// labels) and "no_attempt" stay flagged -- there's no way to confirm those
// are unfair.
const NOT_A_FAIR_MISS = new Set(['no_objection', 'owner_ended_call', 'unusable'])

// The single check every "No Rebuttal" issue count/badge/filter should use
// instead of a bare `row['Rebuttal Detection'] === 'No'` -- keeps them all
// agreeing with isRowFlagged and the backend's get_flagged_calls.
export function isFairRebuttalMiss(row: AgentAuditRow): boolean {
  return row['Rebuttal Detection'] === 'No' && !NOT_A_FAIR_MISS.has(row['Objection Gate'] ?? '')
}

// Flag logic - mirrors backend/services/dashboard_service.py get_flagged_calls,
// plus long VM/Dead-call detection.
export function isRowFlagged(row: AgentAuditRow): boolean {
  const rebuttalIssue = isFairRebuttalMiss(row)
  return (
    row['Releasing Detection'] === 'Yes' ||
    row['Late Hello Detection'] === 'Yes' ||
    isLongCallFlagged(row['Long VM/Dead Detection']) ||
    rebuttalIssue ||
    row['Wrong Dispo Detection'] === 'Yes'
  )
}

export function detectionVariant(val: unknown, col: string, row?: AgentAuditRow) {
  if (col === 'Rebuttal Detection') {
    if (val === 'Yes') return 'success'
    if (val === 'No') {
      // A "No" that wasn't a fair miss isn't an issue -- don't paint it red.
      // Delegates to isFairRebuttalMiss so this always agrees with
      // isRowFlagged and the backend's get_flagged_calls.
      return isFairRebuttalMiss(row ?? { 'Rebuttal Detection': 'No' }) ? 'danger' : 'success'
    }
    return 'muted'
  }
  if (col === 'Releasing Detection' || col === 'Late Hello Detection' || col === 'Wrong Dispo Detection') {
    return val === 'Yes' ? 'danger' : 'success'
  }
  if (col === 'Long VM/Dead Detection') {
    return isLongCallFlagged(val) ? 'danger' : 'success'
  }
  return 'muted'
}

// Builds the human issue labels for one flagged call -- shared by the Actions page's
// Copy All text and the per-call card badges.
export function getCallIssues(row: FlaggedCall): string[] {
  const issues: string[] = []
  if (row['Releasing Detection'] === 'Yes') issues.push('Releasing')
  if (row['Late Hello Detection'] === 'Yes') issues.push('Late Hello')
  if (isFairRebuttalMiss(row)) issues.push('No Rebuttal')
  if (row['Wrong Dispo Detection'] === 'Yes') {
    const reason = row['Wrong Dispo Reason']
    issues.push(reason ? `Wrong Dispo ${reason}` : 'Wrong Dispo')
  }
  const lc = row['Long VM/Dead Detection']
  if (isLongCallFlagged(lc)) {
    const s = String(lc).toLowerCase()
    if (s.startsWith('voicemail')) issues.push('voicemail above 15 sec')
    else if (s.startsWith('dead call')) issues.push('Dead call above 15 sec')
    else issues.push('Long VM/Dead')
  }
  return issues
}

// Aggregates flagged calls (already deduped via dedupeLongCallRows) into one row per agent
// with the 6 detection counters -- used by ActionsPage.
export function buildAgentDeductions(rows: FlaggedCall[], totalCallsMap: Map<string, number>): AgentDeductionRow[] {
  const agentMap = new Map<string, { flagged: FlaggedCall[]; releasing: number; lateHello: number; noRebuttals: number; longCall: number; wrongDispo: number; dialerNames: Set<string> }>()
  for (const call of rows) {
    const name = (call['Agent Name'] ?? 'Unknown').trim()
    if (!agentMap.has(name)) agentMap.set(name, { flagged: [], releasing: 0, lateHello: 0, noRebuttals: 0, longCall: 0, wrongDispo: 0, dialerNames: new Set() })
    const entry = agentMap.get(name)!
    entry.flagged.push(call)
    if (call['Releasing Detection'] === 'Yes') entry.releasing++
    if (call['Late Hello Detection'] === 'Yes') entry.lateHello++
    if (isFairRebuttalMiss(call)) entry.noRebuttals++
    if (isLongCallFlagged(call['Long VM/Dead Detection'])) entry.longCall++
    if (call['Wrong Dispo Detection'] === 'Yes') entry.wrongDispo++
    const dialer = call['Dialer Name'] as string | undefined
    if (dialer) entry.dialerNames.add(dialer)
  }
  return [...agentMap.entries()].map(([agentName, data]) => ({
    agentName, totalCalls: totalCallsMap.get(agentName) ?? data.flagged.length,
    flaggedCalls: data.flagged.length, releasing: data.releasing, lateHello: data.lateHello,
    noRebuttals: data.noRebuttals, longCall: data.longCall, wrongDispo: data.wrongDispo,
    dialerNames: [...data.dialerNames].sort(), deduction: data.flagged.length >= 5,
  })).sort((a, b) => b.flaggedCalls - a.flaggedCalls)
}

const DETECTION_COLS = new Set([
  'Releasing Detection', 'Late Hello Detection', 'Long VM/Dead Detection', 'Rebuttal Detection',
  'Wrong Dispo Detection',
])
export { DETECTION_COLS }
