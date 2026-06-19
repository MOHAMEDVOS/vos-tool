# Company Scoring Sheet — Analysis ("Auditors-Scoring MOP")

Sheet: `1WQHD0ACs5K6iHXWxPnG8izcs-45KlFFyU3vufO7AxQE` · owner `hegazy@res-va.com` ·
title **"Auditors-Scoring MOP"**. This documents the **auditor tabs only** (Abdo / Aya / Zizi…),
which is where the sampled numbers get pasted for scoring.

## Tabs that matter
Each auditor has their own tab, all sharing one template. Tab ↔ auditor seen in the data:
- **Abdo** → Assigned Auditor `Mohamed Ibrahim Abdo Ali`
- **Aya**  → `Aya Samir Farahat`
- **Zizi** → `Zeinab ahmed anwer`

(There are also non-auditor tabs — daily AVG/calculations, cumulative index, links to another
workbook — out of scope.)

## Row layout (confirmed from real rows, 5/1/2026 block)
The left block (cols **A–G**) is what gets filled when a sample is added. Cols **H+** are the
manual scoring the auditor fills later.

| Col | Header | Example value | Source for auto-fill |
|-----|--------|---------------|----------------------|
| A | Date | `5/1/2026` | gather date |
| B | **RES-ID** | `RES-644` | ❓ unknown — see questions |
| C | Agent Name | `Belal Mohamed Ahmed` | ✅ have it |
| D | **Phone Number** | `(216) 409-5932 (601) 720-4459 (216) 973-9306 (216) 659-8446 (216) 253-0856` | ✅ have it — **5 phones, space-separated, ONE cell** |
| E | TL Name | `Asmaa Mustafa Kamel Sadek Algarawany` | ❓ agent→TL mapping, not in ReadyMode CSV |
| F | Assigned Auditor | `Mohamed Ibrahim Abdo Ali` | ✅ = the logged-in user / the tab |
| G | Dialer Name | `RESVA3` | ✅ have it (busiest dialer per agent) |
| H… | Missed BCS?, Intro (×3 Qs), Rebutalls, sound low?, sound cutting?, Tonality, dispositions?, technical issues?, Notes, … | `OH / No / Yes / Yes / Yes / No / No / Active / No …` | ✋ manual scoring — leave blank |
| (near end) | Performance Index % | `100.00%` | likely a **formula** — see risk |
| (last) | N.Of Leads | | manual |

### What this means for us
- **One row = one agent**, with that agent's 5 sampled numbers joined by spaces in the **Phone
  Number** cell (col D). This is *exactly* what `score_agents` already produces (a `phones` list).
- We can auto-fill **A, C, D, F, G** directly from a gather+generate run. `Date`, `Agent Name`,
  `Phone Number` (join the 5), `Assigned Auditor` (current user), `Dialer Name` (busiest dialer).
- **B (RES-ID)** and **E (TL Name)** are NOT written by us — see below.

## RES-ID + TL Name = auto-filled by the sheet  ✅ (confirmed by user)
Cols **B (RES-ID)** and **E (TL Name)** are **formulas keyed off Agent Name (col C)** — typing the
agent name makes the sheet fill them itself. So the append writes **A, C, D, F, G** and leaves
B + E blank for the sheet to populate.
- **Open detail:** is that lookup an `ARRAYFORMULA` (auto-extends to new rows) or a per-row
  `VLOOKUP` (must be copied down)? Can't tell from the read-only render — confirm via Sheets API
  once the service account has Editor access. If per-row, the append copies B/E formulas down from
  the last existing row.

## LIVE-VERIFIED against the sheet (service account `vos-reports@vos-railway.iam.gserviceaccount.com`) ✅

Tabs + gids: **Abdo** `1639531261`, **Aya** `49084812`, **Zizi** `1831112923` (+ non-auditor tabs).
All 20 cols. Header rows = **row 1 + row 2** (merged); **data starts row 3**. Abdo currently empty.

**Confirmed column map (A–T):**
`A Date · B RES-ID · C Agent Name · D Phone Number · E TL Name · F Assigned Auditor · G Dialer Name ·
H Missed BCS? · I "Did the homeowner have to say "hello" first?" (Late Hello) · J name+purpose? ·
K energy? · L "use rebutalls correctly?" · M "Agent's sound is low?" (Releasing) · N sound cutting up? ·
O Tonality · P dispositions errors? · Q technical issues? · R Notes · S Performance Index % · T N.Of Leads`

**ARRAYFORMULAs anchored at row 3 (DO NOT WRITE — writing breaks the spill):**
- `A` Date = `=ARRAYFORMULA(IF(C3:C<>"",Settings!D2,""))`  ← date auto-set from Settings!D2
- `B` RES-ID = `=ARRAYFORMULA(IF(C3:C<>"", VLOOKUP(C3:C,'DATA Validation'!E:F …)))`
- `E` TL Name = `=ARRAYFORMULA(… VLOOKUP(C3:C,'DATA Validation'!E:G …))`
- `F` Assigned Auditor = `=ARRAYFORMULA(IF(C3:C<>"",$F$2,""))`
- `S` Performance Index % = big ARRAYFORMULA computed from the scoring cells
→ all spill automatically the moment **C (Agent Name)** is filled. No copy-down.

**So we WRITE only these columns (everything else auto/manual):** `C, D, G, H, I, J, K, L, M, N, O, P, Q, R`
(two contiguous blocks: **C:D** and **G:R** — skips the formula cols A,B,E,F). Leave **T** blank.

**Per-row values written:**
| Col | Value |
|---|---|
| C | Agent Name |
| D | phones **newline-stacked** (one per line, cell wrap on) |
| G | Dialer (UPPER, e.g. RESVA3) |
| H | `OH` |
| I | `Yes` if agent late-hello-flagged else `No` |
| J,K,L | `Yes`, `Yes`, `Yes` |
| M | `Yes` if agent releasing-flagged else `No` |
| N,O,P | `No`, `Active`, `No` |
| Q,R | `` , `` (blank) |

**Append point:** last non-empty row in col C + 1 (first agent → row 3 when empty).

### Flagged-vs-random rule (DECIDED ✅, threshold = 5)
- Agent with **≥ 5 flagged calls** → **flagged**: list **ALL** their flagged numbers (deduped, no cap),
  I/M set from the flag types, red flag = yes.
- Agent with **< 5 flagged calls (incl. 0)** → flags **ignored**, treated as **clean**: **5 random**
  numbers from their busiest dialer, I=No, M=No.
- Agent absent from both the random pool and (≥5) flagged set → **skipped**.

So the same `5` threshold gates both "red flag" and "use flagged numbers". (Verified in
`lib/scoring_sampler.score_agents`.)

### Heavy-releasing scoring block (10+ releasing samples)
An agent with **≥ 10 releasing-flagged numbers** in the row gets a distinct scoring block
(in `append_scoring_rows`): `H=AE, I=Yes, J=Yes, K=Yes, L=Yes, M=Yes, N=Yes, O=Sleepy, P=No`
(I=Yes intentionally also reads as late-hello). Everyone else keeps the standard block
(`H=OH … O=Active`) with only I (late-hello) and M (releasing) toggled by their flags.

## Fill logic — DECIDED ✅
**Row format:** one row per agent, 5 phones space-joined in col D.
**Target tab:** auto, via a **login → tab** map (VOS only knows `username`/login, no full name, so
name-matching alone is unreliable). Unmapped login → clear error, never writes to a wrong tab.

```
login → tab
mohamedabdo@res-va.com → Abdo
ayasamir@res-va.com    → Aya
zeinab@res-va.com      → Zizi
```
At runtime the tool still reads the live tab list to resolve each tab name → its real gid.

**We write:** A=Date, C=Agent Name, D=Phone Number (joined), G=Dialer Name (+ the 2 VOS scoring columns + fixed defaults below).
**Sheet auto-fills (do NOT write):** B=RES-ID, E=TL Name, F=Assigned Auditor (all formula-driven off col C / the tab).

**Only 2 scoring columns are driven by VOS; the rest are fixed defaults:**
| Header (locate by text at runtime) | VOS flag | Default | → Yes when |
|---|---|---|---|
| `Did the homeowner have to say "hello" first?` (Intro Q1) | **Late Hello** | `No` | agent has late-hello flagged calls |
| `Agent's sound is low?` | **Releasing** | `No` | agent has releasing flagged calls |

**Fixed defaults for every appended row (the rest of the scoring block):**
```
Missed BCS? = OH
Did the caller say his name and the purpose of the call? = Yes
Was the introduction delivered with energy and focus?   = Yes
Did the agent use rebutalls correctly?                  = Yes
Agent's sound is cutting up?                            = No
Tonality                                                = Active
Were there errors in dispositions?                      = No
Were there instances of technical issues?               = No
Notes                                                   = (blank)
```
i.e. the user's block `| OH | No | Yes | Yes | Yes | No | No | Active | No | |` with the two
VOS-driven columns overridden. `Performance Index %` (near end) is a formula — leave it.

**Per-agent flags come from the flagged index** (already built): clean/random agent → both `No`;
releasing-flagged → sound-is-low `Yes`; late-hello-flagged → hello-first `Yes`; both → both `Yes`.
`score_agents` will expose a per-agent `flag_types` list so the append can read these directly.

**Column targeting:** locate the 2 VOS columns + the default columns by **header-text match**
(read the 2 header rows via Sheets API), never by hardcoded index — the text render is lossy and
the template has merged headers. Verify live once the service account has Editor access.

## Risks / notes
- **Formulas:** Performance Index % (and possibly others) look computed. A plain values-append
  won't carry per-row formulas/formatting — we'd need to copy a template row's format/formula
  down, or confirm the sheet uses array-formulas.
- **Access:** the VOS service account (`GOOGLE_SERVICE_ACCOUNT_JSON`) must be shared as **Editor**
  on this sheet before it can append. Owner is `hegazy@res-va.com`.
- **Finding "the bottom":** need the last filled data row per tab (the template has header rows +
  a scoring grid), so append targets the right place.
- Tab gids/exact names need the Sheets API (the Drive text render doesn't expose them); easy once
  the service account has access.
