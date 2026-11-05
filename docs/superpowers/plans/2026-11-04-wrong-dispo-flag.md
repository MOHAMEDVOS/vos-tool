# Wrong Dispo flag detection

## Problem

Heavy audit now has the full call transcript. Some homeowners explicitly say
they don't want to be contacted again, but the agent logs a disposition other
than "DNC - Decision Maker" (e.g. Wrong Number, Decision Maker - NYI). That
mismatch between what was said and what got recorded is currently invisible.

## Options considered

1. **Reuse the 3-layer rebuttal pipeline** (exact → semantic → LLM) for DNC
   phrases. Effort M, impact H, but the semantic/LLM layers are built for
   *ambiguous* objections — here they'd risk false positives ("call me back
   later" isn't DNC) on a category that's supposed to be unambiguous.
2. **New standalone exact/substring phrase-match module**, pure stdlib,
   Layer-1-only, mirrors `lib/campaign_audit_detector.py`'s style. Effort L,
   impact H, precision-first.
3. **Send every transcript to the LLM evaluator.** Cheap to wire, but ongoing
   cost/latency for a phrase category that doesn't need judgment calls.

**Chosen: Option 2.** The failure mode that actually hurts someone here is a
false positive — accusing an agent of mis-logging a call when they didn't.
That's the same asymmetry already written up for the rebuttal flag
(`rebuttal-flag-polarity` memory: a flag is a visible accusation, a miss is
silent) just pointed the other way — so precision beats recall. A curated
phrase list is cheap, auditable, and the risk (missing a new phrasing) fails
silently rather than falsely flagging an agent. Semantic matching can be
added later if real transcripts show it under-matching.

## Solution

Add a pure `wrong_dispo_detection(transcript, disposition) -> "Yes"/"No"`
check that fires only when **both**:
- the transcript contains an explicit, unambiguous DNC-style phrase, and
- the disposition is not "DNC - Decision Maker" (normalized for dash
  style/case/whitespace — see Gotcha below).

Wire it into the same per-call result dict that already carries "Late Hello
Detection" / "Releasing Detection", so it rides through storage via the
existing `metadata` JSONB round-trip in `agent_audit_results` — **no DB
migration needed** (this mirrors how "Agent Intro" / "Owner Name" already
ride along today; only the original 3 flags got dedicated columns). Surface
it in the same two places every other flag already surfaces.

### Gotcha found while reading the code

Disposition string formatting is inconsistent across the repo already:
`backend/api/scoring.py` hardcodes `"Decision Maker - NYI"` (hyphen) while
`lib/dashboard_manager.py` hardcodes `"Decision Maker – NYI"` (en-dash).
`lib/campaign_audit_detector.py` avoids the whole problem with prefix
matching instead of exact strings. The new check will do the same: lowercase,
collapse any dash variant, then check `starts with "dnc"` AND
`contains "decision maker"` — so it doesn't silently fail to match "DNC –
Decision Maker" vs "DNC - Decision Maker".

### Assumption to flag

Per your wording, only an exact "DNC - Decision Maker" counts as correct —
so "DNC - Unknown" would also get flagged if the transcript has a clear DNC
phrase, even though an agent who logs DNC-Unknown has arguably already
respected the request. Building it per your literal spec; say if DNC-Unknown
should also count as "correct" and I'll widen the check.

## Files

- `lib/wrong_dispo_detector.py` (new) — `DNC_PHRASES` list +
  `wrong_dispo_detection(transcript, disposition)`. Pure stdlib, no I/O, unit
  testable like `lib/campaign_audit_detector.py`.
- `audio_pipeline/detections.py` (`run_audit()`) / `processing/batch_engine.py`
  — wherever the per-call dict already has Transcription + Disposition in
  hand, call the new function and add a `"Wrong Dispo Detection"` key.
- `lib/dashboard_manager.py` — add `'Wrong Dispo Detection'` to the
  `campaign_audit_columns` default-fill list (~line 2516) so older rows
  without it don't break.
- `backend/services/dashboard_service.py::get_flagged_calls()` — OR the new
  flag into the existing quality/rebuttal/long-call condition (~line 215).
- `webapp/src/utils/audit.ts` — add `'Wrong Dispo Detection'` to the
  detection-columns list and the flagged-row OR condition (mirrors the
  backend function 1:1 today).
- `webapp/src/types/api.ts` — add the field to the row type.
- `webapp/src/pages/ActionsPage.tsx` / `CallReviewPage.tsx` — render the new
  flag label wherever Late Hello / Releasing / Rebuttal already show.
- `tests/test_wrong_dispo_detector.py` (new) — phrase hit/miss cases +
  disposition-normalization cases (hyphen vs en-dash, case, "DNC - Unknown"
  vs "DNC - Decision Maker").

## Scope boundary — not included unless you want it

This only adds the flag to Actions / Call Review (the per-call quality
flags). It does **not** wire into the 5-sample Scoring majority vote
(`lib/scoring_audit.py`, `lib/scoring_sampler.py`) or the company sheet
export. Reason: `SCORING_DISPOSITIONS` already restricts that pipeline to
calls logged as "Wrong Number"/"Decision Maker - NYI" — so "disposition !=
DNC" is already true for every sample it ever sees there, and the check
would collapse to "did any of the 5 samples mention a DNC phrase," which is
a real but separate decision (new scoring column, new majority-vote rule,
changes to the company MOP sheet mapping).

## Verification

- Unit tests on the new detector: phrase hits/misses, dash/case
  normalization, the DNC-Unknown edge case above.
- Replay a handful of stored transcripts offline the same way
  `scripts/rebuttal_eval/` replays rebuttal detection, to sanity-check the
  false-positive rate before trusting this on real audits
  (`rebuttal-eval-harness` memory).
- Manual: audit one call with an explicit DNC phrase and a non-DNC
  disposition, confirm it shows up flagged on the Actions page.

## Risk

The phrase list will under-match at first on phrasing not yet seen — a
silent miss, not a false accusation, so it fails in the safe direction.
Low risk otherwise: no schema change, no new dependency, additive to
existing flag logic.
