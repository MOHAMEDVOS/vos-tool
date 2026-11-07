# Step 5 — Fresh re-scan of `webapp/src` (post-refactor)

Scope: everything under `webapp/src`. Read-only; nothing changed. Checked today's
refactor (role table consolidation into `utils/permissions.ts`, SSE helper
`utils/sseStream.ts`, dead-component deletions, comment cleanup) for anything left
half-done, then scanned the rest of the tree fresh for current problems.

## What today's refactor got right (no leftovers found)

- `utils/permissions.ts` (new) is used consistently everywhere a role check used to be
  inlined: `App.tsx`, `Sidebar.tsx`, `UsageCard.tsx`, `DashboardPage.tsx`,
  `AuditPage.tsx`, `TlActionsPage.tsx`, `SettingsPage.tsx`. No stray `role === 'Owner'`
  /`'Admin'` access-gating checks remain outside it (the handful of remaining
  `role ===` / `a.role ===` hits in `SettingsPage.tsx` and `UsersPage.tsx` are display
  logic / a different "role" domain — ReadyMode account folder role — not access
  gating).
- `utils/sseStream.ts` (new) is used by every SSE call site (`api/scoring.ts`,
  `api/readymode.ts`, `pages/UsersPage.tsx`, 6 call sites) — no hand-rolled
  `fetch` + manual `text/event-stream` parsing left anywhere.
- Deleted components (`AICanvasBackground.tsx`, `AtmosphericOrbs.tsx`,
  `LoginCanvasBackground.tsx`, `ShockwaveOverlay.tsx`) have zero remaining references.
- `useAuditStream` hook was deleted and its types/logic correctly folded into
  `store/auditStore.ts`; every importer (`AuditPage.tsx`, `Sidebar.tsx`) was updated
  to the new source, nothing still points at the old path.
- `Button.tsx` dropped the unused `ghost`/`destroy` variants; zero remaining
  `variant="ghost"`/`"destroy"` call sites.
- `AuditPage.tsx`'s `dialerCheck`/`agentDialerCheck` duplicate state+handler pair was
  merged into one `dialerCheck` state keyed by a query key; both the campaign and
  agent code paths now share the UI block. Checked for stragglers — none.
- Comment-only cleanup (restating-the-code comments removed) is clean; no comment
  anywhere still describes something that was deleted.

## Hidden Links

1. **Agent-deduction aggregation copy-pasted between `ActionsPage.tsx:322-344` and
   `CallReviewPage.tsx:182-204`.** Both build a `Map<string, {flagged, releasing,
   lateHello, noRebuttals, longCall, wrongDispo, dialerNames}>` from a list of
   `FlaggedCall`s with the exact same six detection checks, then map it to
   `AgentDeductionRow[]`, line-for-line identical except for where the input list
   comes from. The *type* (`AgentDeductionRow`) and the *table* that renders it
   (`AgentDeductionsTable`) are already correctly shared (`CallReviewPage` imports
   both from `ActionsPage`) — only the code that *produces* the data was left
   un-shared. Change one of the six detection rules (e.g. add a 7th flag type) and
   it's easy to update one copy and forget the other.
   - `webapp/src/pages/ActionsPage.tsx:322-344`
   - `webapp/src/pages/CallReviewPage.tsx:182-204`

2. **Per-call issue-label logic implemented three separate times.** `ActionsPage.tsx`
   has `callMatchesFlagType` (line 20, a boolean matcher) and `callIssues` (line 266,
   a label-list builder) in the same file — already linked by an explicit comment
   ("Mirrors callIssues() below"), so at least that pair is self-aware. But
   `CallReviewPage.tsx`'s `CallCard` (lines 281-295) builds the same label list a
   third time, inline, with no comment pointing back to `callIssues`. All three encode
   the same five detection → label rules (Releasing / Late Hello / No Rebuttal(s) /
   Wrong Dispo(+reason) / Long VM/Dead with voicemail-vs-dead-call sub-labels).
   - `webapp/src/pages/ActionsPage.tsx:20-29` (`callMatchesFlagType`)
   - `webapp/src/pages/ActionsPage.tsx:266-280` (`callIssues`)
   - `webapp/src/pages/CallReviewPage.tsx:281-295` (inline `issues` array in `CallCard`)

3. **Row-field normalization split into two unsynced places.** `utils/audit.ts`'s
   `normalizeRow()` exists specifically to absorb backend key-casing inconsistencies
   (`username`→`Auditor`, `audit_type`→`Audit Type`, `dialer_name`→`Dialer Name`,
   `Time` from metadata, etc.) and is used by `AuditTable.tsx` (line 34). But
   `CallReviewPage.tsx`'s `CallCard` does its own separate, ad hoc normalization for
   the same kind of inconsistency — `call.Time || call.Timestamp || call.timestamp`
   (line 365) and `call['File Name'] ?? call.filename ?? call.Filename` (line 298) —
   instead of extending/calling `normalizeRow`. A new backend casing variant for
   either field has to be fixed in both places to actually take effect everywhere.
   - `webapp/src/utils/audit.ts:29-70` (`normalizeRow`)
   - `webapp/src/pages/CallReviewPage.tsx:298, 365-377`

4. **Three independent implementations of "attach the bearer token."**
   `api/client.ts` has `authHeaders()` (lines 16-19) used by `uploadForm` and
   `sseStream.ts`, but `request()` (the function backing `api.get/post/put/delete`,
   lines 30-47) re-derives the token and builds the `Authorization` header itself
   instead of calling `authHeaders()`. A third copy lives in
   `api/readymode.ts`'s `cancel()` (line 94-98), which builds the header manually yet
   *again* and — unlike every other call in the file — calls bare `fetch('/api/readymode/cancel', …)`
   instead of going through `apiUrl()`. If `VITE_BACKEND_URL` is ever set to a
   cross-origin backend, every other API call keeps working and `cancel()` alone breaks.
   - `webapp/src/api/client.ts:12-19` vs `:36-40`
   - `webapp/src/api/readymode.ts:94-98`

5. **Query-string building copy-pasted five times in `api/dashboard.ts`.** Every
   method (`agentAudits`, `liteAudits`, `campaignAudits`, `flaggedCalls`,
   `campaignDisposition`) repeats the same `new URLSearchParams(); if (x) q.set(...)`
   shape by hand. A shared `buildQuery(params)` helper would collapse all five.
   - `webapp/src/api/dashboard.ts:5-49`

6. **`UsersPage.tsx`'s dialer-picker toggle/select-all logic is copy-pasted 3×** — once
   per mode (create/delete/duplicates): `toggleDialer`/`toggleAllDialers` (lines
   332-336), `toggleDeleteDialer`/`toggleAllDeleteDialers` (lines 391-395),
   `toggleDupDialer`/`toggleAllDupDialers` (lines 546-550) are byte-identical except
   for which state setter they close over.
   - `webapp/src/pages/UsersPage.tsx:332-336, 391-395, 546-550`

7. **`UsersPage.tsx`'s "sequential per-dialer uid-delete" loop is copy-pasted between
   `handleDeleteInactive` (lines 482-526) and `handleDeleteDuplicates` (lines
   606-650).** Both group selected `{dialerUrl, dialer, name, uid}` rows by dialer,
   loop sequentially, call `readSSEStream('/api/readymode-users/delete', …)` per
   dialer, and append to a results array on `done`/`error`/catch — identical shape,
   down to the comment explaining why it's sequential ("a uid-carrying request must
   target exactly one dialer").
   - `webapp/src/pages/UsersPage.tsx:482-526` and `:606-650`

8. **Delete-confirmation UI (`showConfirm` state + two-button inline confirm panel)
   copy-pasted across all three dashboard tabs.** `AgentAuditDashboard.tsx` (lines
   17-28, 99-124), `LiteAuditDashboard.tsx` (lines 15-21, 74-96), and
   `CampaignAuditDashboard.tsx` (lines 110-133, 265-292) each independently wire up
   `const [showConfirm, setShowConfirm] = useState(false)`, a `clearData` mutation
   that resets it on success, and the same `DestroyButton` → inline confirm-card →
   "Yes, Delete All" / "Cancel" markup.
   - `webapp/src/features/dashboard/AgentAuditDashboard.tsx:17-28,99-124`
   - `webapp/src/features/dashboard/LiteAuditDashboard.tsx:15-21,74-96`
   - `webapp/src/features/dashboard/CampaignAuditDashboard.tsx:110-133,265-292`

## Needless Links

1. **`ProtectedRoute.tsx`'s `requiredRole` prop re-implements role gating on top of
   raw role strings, independent of `utils/permissions.ts`.** It's a second,
   parallel access-control mechanism (`if (!role || !allowed.includes(role))`,
   lines 35-38) sitting next to the `Feature`-based `canAccess()` system that the
   rest of the app was just consolidated onto. See also Surplus #1 below — it's
   also unused, so right now this is only a latent risk, not an active bug: if
   someone passes `requiredRole` to a route later, there will be two different
   "what can this role do" sources of truth to keep in sync.
   - `webapp/src/components/auth/ProtectedRoute.tsx:10,35-38`
   - `webapp/src/utils/permissions.ts`

2. **`App.tsx` renders every page as client-side tab state (`activeTab` in
   `uiStore`) behind a single catch-all route (`/*`), even though it imports and sets
   up `BrowserRouter`/`Routes`/`Route`.** Only `/login` is a real route. Every other
   "page" (`Dashboard`, `Audit`, `Settings`, etc.) is a `uiStore.activeTab` string
   compared in a chain of `&&`s, not a route — so the URL never reflects which page
   is open, there's no deep-linking/back-button support, and `react-router-dom` is
   pulled in for exactly one route. This is a real router being used as a single
   boolean gate; the tab system and the router don't know about each other.
   - `webapp/src/App.tsx:1-2, 73-107`
   - `webapp/src/store/uiStore.ts:4` (`NavTab`)

## Surplus

1. **`ProtectedRoute`'s `requiredRole` prop and its branch (lines 35-38) are dead
   code.** The only caller, `App.tsx:98`, renders `<ProtectedRoute>` with no
   `requiredRole` passed, and no other call site exists anywhere in `src/`.
   - `webapp/src/components/auth/ProtectedRoute.tsx:10, 35-38`

2. **`uiStore.loginAnimating` and `setLoginAnimating` are dead.** Defined (state +
   setter) but never read or called from anywhere else in `src/` (checked
   `LoginPage.tsx` and `App.tsx` specifically, since those are the plausible
   consumers — neither references it).
   - `webapp/src/store/uiStore.ts:11,16,29,41`

## Special Cases

- Seven `// eslint-disable-next-line react-hooks/set-state-in-effect` instances
  (`KaraokeTranscript.tsx:87`, `SuccessFlash.tsx:15`, `PhrasesPage.tsx:183`,
  `SettingsPage.tsx:307,553,1199,1322`, `AuditPage.tsx:433`) are all the same
  "populate local form state from server data once it loads" pattern. Each is a
  one-off suppression rather than a shared `useSyncedState`/derived-state helper, so
  the special case is repeated seven times instead of designed away once.
- `UsersPage.tsx` has two effects (lines 294-299 and 301-311) that both write
  `passwordsText` from overlapping triggers (`names.length` changing vs
  `loginIdsText` changing), each with its own `eslint-disable-next-line
  react-hooks/exhaustive-deps`. Two special-cased effects racing to own the same
  derived field — fragile if a third input is ever added to the password-generation
  rule.
- `api/readymode.ts:cancel()` is the one API call in the whole `api/` directory that
  takes an explicit `token` parameter and builds its own header instead of relying on
  `authHeaders()` — a parameter that exists only because this one caller didn't go
  through the shared path (see Hidden Link #4).

## Other (doesn't fit the three categories, but worth a flag)

- `PhrasesPage.tsx:84` has garbled/mis-encoded characters in rendered text:
  `{phrase.category} آ· quality ... آ· seen {phrase.detection_count ?? 0}أ—` — the
  middle-dot and "×" characters appear to have been mangled by an encoding
  round-trip (likely UTF-8 bytes misread as another codepage) and now render as
  stray Arabic-looking glyphs in the UI. Not a structural issue, just a real visible
  bug worth a one-line fix.

---

### Counts
- Hidden Links: 8
- Needless Links: 2
- Surplus: 2
- Special Cases: 3 (grouped)
- Other: 1 (encoding bug, out of category)
