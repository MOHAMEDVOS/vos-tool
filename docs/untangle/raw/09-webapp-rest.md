# webapp-rest — Problems (Step 2)

Scope: everything under `webapp/src/` except `pages/`, `App.tsx`, `main.tsx`, and
`components/layout/` (covered by another pass) — i.e. `api/`, `hooks/`, `store/`,
`types/`, `utils/`, `features/dashboard/`, `components/ui/`, `components/tables/`,
`components/auth/`, `components/KaraokeTranscript.tsx`. All 47 files in scope were read.
Read-only analysis — nothing below was changed.

**On the graphify signal:** partially confirmed, with a different shape than "props
drilling." `Spinner` itself is clean (just `size`/`variant`, no coupling found) — its
edge count looks like ordinary, justified reuse of a loading indicator across many
pages. `Button`'s edge count is a mix of the same ordinary reuse *plus* real duplication:
the same "confirm destructive action" panel (local `showConfirm` state + a `Button` +
`DestroyButton` pair) is copy-pasted near-verbatim into all three
`features/dashboard/*.tsx` files instead of being one component, and `Button.tsx` itself
carries two dead variants. The sharper version of the signal is in `utils/audit.ts`,
`store/`, and `api/`: business logic (what counts as "flagged," the auth token, the SSE
download/progress protocol) is reimplemented in multiple places by hand instead of living
in one place — see Hidden Links below.

## Hidden Links

- `utils/audit.ts:4-21` (`AGENT_AUDIT_COLUMN_ORDER`) and `utils/audit.ts:24-26`
  (`HIDDEN_COLUMNS`) — comments say these mirror `app.py:2457-2471` and `app.py:2442`
  respectively. The frontend's column list/order is a hand-copied mirror of a backend
  Python file by line number; a backend reorder silently desyncs this with no error.
- `utils/audit.ts:115-126` (`isRowFlagged`) — its own comment says it "mirrors
  backend/services/dashboard_service.py get_flagged_calls." The definition of "is this
  call flagged" is implemented twice, by hand, across the frontend/backend language
  boundary, with no shared schema or test tying them together. (MEMORY.md's own
  `wrong-dispo-flag`, `objection-gate-not-wired-into-flagging`, and
  `transcript-cache-drops-speaker-labels` notes show this exact class of drift has
  already caused real bugs.)
- `utils/audit.ts:108-110` says "The single check every 'No Rebuttal' issue
  count/badge/filter should use instead of a bare `row['Rebuttal Detection'] === 'No'`"
  — i.e. callers should use `isFairRebuttalMiss` (`utils/audit.ts:111-113`). But
  `detectionVariant` (`utils/audit.ts:129-146`), in the same file, reimplements the exact
  same `val === 'No'` + `NOT_A_FAIR_MISS.has(...)` check inline (`utils/audit.ts:132-136`)
  instead of calling `isFairRebuttalMiss`. The file violates its own documented rule.
- `'vos_token'` is hard-coded as a raw localStorage key in three independent places:
  `api/client.ts:16` (`getToken`, read), `store/authStore.ts:26,31` (`setAuth`/`clearAuth`,
  write/remove), and `api/scoring.ts:67-69` (a private `token()` that duplicates
  `client.ts`'s read instead of importing it). Nothing ties the three together.
- Three independent hand-rolled SSE stream parsers, each re-implementing "read the
  response body, decode, split on `\n`, strip a `data:` prefix, `JSON.parse`, swallow
  parse errors as ping/keep-alive": `api/readymode.ts:100-118`, `api/scoring.ts:88-112`,
  and `api/scoring.ts:138-165`. A fix to one parsing edge case has to be repeated by hand
  in the other two.
- `hooks/useAuditStream.ts:33-51` (`parseStage`) is a byte-for-byte copy of
  `store/auditStore.ts:24-42` (`parseStage`) — same prefix table, same slicing. The
  analysis-progress regex `(?:Async|Lite) Progress: (\d+)\/(\d+)` is likewise duplicated
  at `useAuditStream.ts:101` and `auditStore.ts:85`. (The hook's copy is also dead code —
  see Surplus.)
- `store/auditStore.ts:24-42,85` and `hooks/useAuditStream.ts:33-65,101` both depend on an
  implicit text protocol the backend's SSE log lines must follow — literal prefixes like
  `"WAIT "`/`"SUCCESS:"`, the exact substring `"DOWNLOAD_COMPLETE"` or `"files
  downloaded"` (`useAuditStream.ts:59`), and the exact wording `"Async Progress: d/d"` /
  `"Lite Progress: d/d"`. None of this is a typed/shared contract with the backend — a
  log-wording change silently breaks stage coloring and the progress bar with no error
  surfaced anywhere.
- `store/badgeStore.ts:5-32` — the comment at line 6 says `seenByUser` is keyed by
  `currentUser` so "each user's seen state is independent." `setCurrentUser`
  (`badgeStore.ts:9,20`) is never called anywhere in the codebase (verified repo-wide).
  `currentUser` stays `''` forever, so the per-user partition the comment promises never
  actually happens — all users on one browser silently share one "seen" bucket.
- `features/dashboard/AgentAuditDashboard.tsx:26` invalidates React Query key
  `['badge-count']` after clearing agent-audit data, but the actual badge query
  (`hooks/useDashboard.ts:57-68`, `useFlaggedBadge`) is keyed `['flagged-count']`
  (`useDashboard.ts:60`). `LiteAuditDashboard.tsx:24` and `CampaignAuditDashboard.tsx:136`
  both correctly invalidate `['flagged-count']`. Clearing agent-audit data silently fails
  to refresh the sidebar's flagged-call badge — a hand-typed string must match a key
  defined elsewhere, and one of three call sites already has it wrong.
- `features/dashboard/AgentAuditDashboard.tsx:97` passes `getRowClassName` to
  `<AuditTable>` to put a red left border on rows for agents over the flag threshold.
  `components/tables/AuditTable.tsx:17` destructures only
  `{ rows, leftActions, excludeColumns = [] }` from `Props` — `getRowClassName` (declared
  in the `Props` interface at `AuditTable.tsx:12`) is never read anywhere in the
  component body; the `<tr>` className is the static literal at `AuditTable.tsx:111`. The
  "Attention Required" row highlight silently does nothing.
- `features/dashboard/CampaignAuditDashboard.tsx:147` checks
  `r['Audit Type'] || r['audit_type']` directly on rows that have never been through
  `normalizeRow` (`utils/audit.ts:29-71`, which is what actually reconciles
  `audit_type` → `'Audit Type'`). Normalization only happens inside
  `components/tables/AuditTable.tsx:34`, on a separate copy of the same row data, purely
  for display. Dashboard-level filtering/metrics and table-level rendering silently
  operate on two different (raw vs. normalized) views of what's conceptually the same
  rows.
- `types/api.ts:96-97` keeps both `'Reason for calling'?: string` and
  `'Reason for Calling'?: string` as permanent alternate fields instead of one canonical
  field, and `:99-101` keeps `Timestamp?`, `timestamp?`, and `Time?` as three separate
  optional fields for what is conceptually one value. Only `normalizeRow`
  (`utils/audit.ts:29-71`, called from exactly one place) reconciles any of this, so any
  code that reads `AgentAuditRow` directly — all three `features/dashboard/*.tsx` files do
  — has to remember which spelling is actually live.
- `types/api.ts:1` — "mirror backend Pydantic schemas exactly." The whole 289-line file is
  a hand-maintained mirror of the FastAPI backend's Pydantic models, with no codegen or
  shared schema. Every interface in it can silently drift the moment the matching
  backend model changes.

## Needless Links

- `components/tables/AuditTable.tsx` presents as a generic table (`Props.rows:
  AgentAuditRow[]`), but it imports one fixed, shared column list directly
  (`AGENT_AUDIT_COLUMN_ORDER`, from `utils/audit.ts:4`) and each caller subtracts a
  different subset of it: `excludeColumns={['Long VM/Dead Detection']}`
  (`features/dashboard/AgentAuditDashboard.tsx:96`),
  `excludeColumns={['Time', 'Long VM/Dead Detection']}`
  (`features/dashboard/CampaignAuditDashboard.tsx:263`), no exclusion at all
  (`features/dashboard/LiteAuditDashboard.tsx:66`). `excludeColumns` is a parameter only
  each specific dashboard's workflow understands, layered on top of a column list that
  isn't actually shared data so much as a shared default.
- `components/KaraokeTranscript.tsx:4-7` takes both `audioRef` and `audioEl` as two
  separate props for "the audio element." Its only caller
  (`pages/CallReviewPage.tsx:412`, confirmed the sole usage site repo-wide) has to track
  the same element in both a ref and state, purely to force a re-render when it mounts
  (comment at `CallReviewPage.tsx:320`). The component's one caller is managing an
  implementation detail — how `KaraokeTranscript` detects that the audio element
  mounted — that arguably belongs inside the component.
- `api/scoring.ts:67-69` defines a private `token()` that reads `localStorage` directly
  and hand-builds `Authorization: Bearer ${token()}` headers at `scoring.ts:80,130`, even
  though `scoring.ts:1` already imports from `./client`, which exports `authHeaders()`
  (`api/client.ts:19-22`) for exactly this job — and `authHeaders()` is already used
  correctly elsewhere (`pages/CallReviewPage.tsx:443`, outside this scope). Two
  conventions for "attach the bearer token" inside the same `api/` folder.
- `components/ui/ShockwaveOverlay.tsx:1-2` imports `animejs` and imperatively mutates
  `el.style` directly for one component's clip-path reveal, while every other component
  in `components/ui/` uses `framer-motion` declaratively for the same class of animation
  (20 files repo-wide import `framer-motion`; only 3 repo-wide import `animejs`, and the
  other two are outside this scope). Low-stakes in practice since `ShockwaveOverlay` is
  itself dead code (see Surplus), but it mirrors the same animejs-vs-framer-motion split
  in the still-live login page.

## Surplus

- `hooks/useAuditStream.ts:69-157` — the `useAuditStream()` hook itself is never called
  anywhere in the codebase (verified repo-wide: every consumer —
  `components/layout/Sidebar.tsx`, `pages/AuditPage.tsx`, `store/auditStore.ts` — imports
  only its exported types and the `inferPhase` helper, never the hook function). The
  entire duplicated state machine inside it (start/cancel/reset, SSE handling, the
  `parseStage` copy) is dead.
- `components/ui/AICanvasBackground.tsx` (198 lines) — never imported anywhere outside
  its own file (verified repo-wide). Fully dead.
- `components/ui/LoginCanvasBackground.tsx` (219 lines) — its own comment says it's "for
  login page," but it's never imported anywhere, including not by `pages/LoginPage.tsx`,
  which has its own separate video-background implementation. Fully dead.
- `components/ui/ShockwaveOverlay.tsx` (61 lines) — never imported anywhere, including
  not by `pages/LoginPage.tsx` (which runs its own inline `animejs` timeline instead).
  Fully dead.
- `components/ui/AtmosphericOrbs.tsx:3-4` — its own comment says "this component is a
  no-op"; confirmed never imported anywhere repo-wide. Dead code that documents its own
  deadness but was never deleted.
  (The four items above total roughly 480 lines of unused decorative/streaming code, and
  the three canvas/overlay components read like abandoned remnants of one earlier
  login-page design direction.)
- `components/ui/Button.tsx:10` (`'destroy'` in the variant union) and `:57-61` (the
  `destroy` entry in `variants`) — never selected by any caller (`grep
  variant="destroy"` → 0 hits repo-wide); every actual destructive button goes through
  the separate `DestroyButton` export instead (12 call sites across
  `features/dashboard/*.tsx` and `pages/ActionsPage.tsx`). Dead, and duplicates
  `DestroyButton`'s hand-rolled hex colors besides.
- `components/ui/Button.tsx:44-46` (`ghost` variant) — declared but never selected by any
  caller (0 hits for `variant="ghost"` repo-wide).
- `components/ui/Button.tsx:69-75` (`textSizes` table and the `currentTextSize`
  ternary) — `textSizes.action`, `.sm`, and `.md` are all the literal string
  `'text-[10px]'`. The lookup table and the variant-based ternary can never produce more
  than the one value every branch already shares.
- `hooks/useReports.ts:19-21` (`isGoogleNotConnectedError`) — exported but never imported
  anywhere else in the codebase (verified repo-wide).
- `api/user.ts:5` / `types/api.ts:35-46` (`EverythingPayload`) — of this payload's
  top-level fields, only `quota_and_usage.daily_usage` is ever read, by
  `store/quotaStore.ts:22` (the only caller of `getEverything()` anywhere in
  `webapp/src`). `dashboard_sharing`, `audits`, `phrase_stats`, `learned_rebuttals`, and
  `subscriptions` are typed but have no frontend consumer at all.

## Special Cases

- `components/ui/Select.tsx:44` — `setTimeout(() => inputRef.current?.focus(), 100)`, a
  flat 100ms guess that the dropdown's enter animation has finished mounting the search
  input before focusing it.
- `components/ui/Button.tsx:94-99` — `DestroyButton`'s own comment explains it exists as
  "a plain button with no motion, so it can't get stuck hidden": a whole second button
  component, built to work around one specific animation bug in the shared
  `motion.button` every other `Button` variant uses, instead of fixing the underlying
  issue once.
- `components/ui/SuccessFlash.tsx:15` and `components/KaraokeTranscript.tsx:88` both carry
  an identical `// eslint-disable-next-line react-hooks/set-state-in-effect`, suppressing
  the same lint rule for the same "reset derived state when a prop/flag changes" pattern,
  in two unrelated files, rather than through one shared convention.
- `api/readymode.ts:14-25` (`DISPOSITIONS`) — the comment says Voicemail is "deliberately
  absent and can never be added" because the backend hard-blocks it elsewhere
  (`automation/readymode_http.py`, outside this scope). A backend policy is encoded here
  as a silent omission from a UI list rather than something the UI (or backend) actively
  validates.
- `hooks/useReports.ts:19-21` (`isGoogleNotConnectedError`) — special-cases one exact
  backend error string (`error.message === 'google_not_connected'`) together with one
  exact HTTP status (401) to detect a specific integration state, rather than the backend
  returning a typed/structured error code. (Also currently dead — see Surplus.)
- `components/tables/AuditTable.tsx:116` (`col === 'Transcription' || col === 'Reason for
  calling'`) and `:155` (`col === 'Agent Name'`) — a table component that's otherwise
  driven by a generic column list special-cases three exact column-name strings for
  layout/clamping and for showing a copy button, instead of taking per-column behavior as
  data.
- `components/auth/ProtectedRoute.tsx:21-22` — `staleTime: 5 * 60 * 1000` on the
  `auth-me` check, justified by the comment "prevents re-auth during long audits."
  `ProtectedRoute` wraps every protected route (Dashboard, Settings, Users, etc.), but its
  cache freshness was tuned for one specific workflow (the Audit page's long-running
  ReadyMode download) and applies globally regardless.
