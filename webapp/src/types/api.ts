// API request/response types — mirror backend Pydantic schemas exactly

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  username: string
  name?: string
  picture?: string
  role: string
  session_id: string
}

export interface UserInfo {
  username: string
  role: string
  daily_limit?: number
  readymode_username?: string
}

export interface UsageInfo {
  username: string
  daily_limit: number
  current_count: number
  remaining: number
  usage_percent: number
  date: string
  error?: string
}

export interface EverythingPayload {
  user: UserInfo
  quota_and_usage: {
    quota_status: Record<string, any>
    daily_usage: UsageInfo
  }
  dashboard_sharing: Record<string, any>
  audits: Record<string, any>
  phrase_stats: Record<string, any>
  learned_rebuttals: Record<string, any>
  subscriptions: Record<string, any>
}

// ─── Audit / Dashboard ───────────────────────────────────────────────────────

export interface AuditRecord {
  id: string
  timestamp: string
  agent_name?: string
  campaign?: string
  transcript?: string
  rebuttals?: Record<string, unknown>[]
  metadata?: Record<string, any>
}

export interface DashboardData {
  records: AuditRecord[]
  total_count: number
  filters?: AuditFilter
}

export interface AuditFilter {
  start_date?: string
  end_date?: string
  agent_name?: string
  campaign?: string
}

// Raw audit row as returned in metadata (mirrors DB columns)
export interface AgentAuditRow {
  'Agent Name'?: string
  'Phone Number'?: string
  Disposition?: string
  'Releasing Detection'?: string
  'Late Hello Detection'?: string
  'Rebuttal Detection'?: string
  Transcription?: string
  'Dialer Name'?: string
  'Agent Intro'?: string
  'Owner Name'?: string
  'Reason for calling'?: string
  'Reason for Calling'?: string
  'Intro Score'?: string | number
  Status?: string
  Timestamp?: string
  timestamp?: string
  Time?: string
  username?: string
  audit_type?: string
  'File Name'?: string
  'File Path'?: string
  [key: string]: any
}

export interface FlaggedCall extends AgentAuditRow {
  id?: string
}

export interface WordTimestamp {
  word: string
  start: number  // seconds
  end: number    // seconds
  speaker?: string | null
}

export interface WordTimestampsResponse {
  words: WordTimestamp[]
}

// ─── Phrases ────────────────────────────────────────────────────────────────

export interface PhraseStats {
  total_phrases: number
  pending_count: number
  auto_learned_count: number
  categories: number
  last_updated: string
}

export interface PhraseLearningSettings {
  confidence_threshold?: number
  frequency_threshold?: number
  auto_approve_threshold?: number
}

export interface PendingPhrase {
  id: string
  phrase: string
  category: string
  confidence?: number
  detection_count?: number
  first_detected?: string
  last_detected?: string
  sample_contexts?: string
  similar_to?: string
  quality_score?: number
  canonical_form?: string
  quality_tier?: string
}

// ─── System / Health ────────────────────────────────────────────────────────

export interface SystemHealth {
  cpu_percent: number
  memory: {
    percent: number
    used_mb: number
  }
  disk_percent: number
}

export interface GenericActionResponse {
  success: boolean
  message?: string
}

export interface ReadonlyStatus {
  read_only: boolean
  migration_status?: Record<string, unknown> | null
}

export interface SessionInfo {
  username?: string
  session_id?: string
  created_at?: string
  last_activity?: string
  expires_at?: string
  is_active?: boolean
  [key: string]: unknown
}

// ─── Settings ───────────────────────────────────────────────────────────────

export interface UserSettings {
  daily_limit?: number
  readymode_username?: string
  readymode_password?: string
  assemblyai_api_key?: string
  assemblyai_api_key_encrypted?: string
  preferences?: Record<string, unknown>
}

export interface CreateUserRequest {
  username: string
  password?: string
  role?: string
  daily_limit?: number
  readymode_username?: string
  readymode_password?: string
}

export interface UpdateUserRequest {
  role?: string
  daily_limit?: number
  readymode_username?: string
  readymode_password?: string
  password?: string
}

export interface ReadyModeStatus {
  status: string
  downloaded_count?: number
  analyzed_count?: number
  message?: string
}

export type AppConfigCategory = 'audio' | 'detection'

export interface UserListResponse {
  users: UserInfo[]
  total: number
}

export interface QuotaStatus {
  used?: number
  limit?: number
  remaining?: number
  [key: string]: unknown
}

export interface SharingConfig {
  sharing_groups?: Record<string, unknown>
  user_dashboard_mode?: Record<string, string>
  [key: string]: unknown
}

// ─── Campaign Reachability Scan ──────────────────────────────────────────────

export interface ReachabilityScan {
  campaign_name: string
  username: string
  scan_date: string
  timestamp: string
  total_calls: number
  verdict: 'LOW' | 'GOOD'
  low_total: number
  good_total: number
  low_counts: Record<string, number>
  good_counts: Record<string, number>
  created_at: string
}
