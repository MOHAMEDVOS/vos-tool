# Wrong Dispo: widen coverage to Wrong Number and Decision Maker - NYI

## Problem

`lib/wrong_dispo_detector.py` currently catches one mismatch: a clear DNC
phrase in the transcript paired with any non-"DNC - Decision Maker"
disposition. That already flags Wrong Number / Decision Maker - NYI when a
DNC phrase is present (the check is "any dispo other than DNC", not
"DNC only"), so nothing changes there.

What's missing: mismatches that don't involve a DNC phrase at all, but where
the disposition itself is contradicted by what's actually in the transcript.
Scoped first to the two dispositions `SCORING_DISPOSITIONS`
(`backend/api/scoring.py`) already singles out as the ambiguous ones that get
manually sampled for the 5-call scoring QA — "Wrong Number" and
"Decision Maker - NYI" — because those are exactly the two buckets an agent
can use as a dumping ground to dodge a harder, more specific disposition.

## Research: how the sibling project solves this

Per your instruction, scanned `~/Desktop/projects/TEXTING-AUDIT-AUTOMATION`
with graphify (AST + semantic extraction across 117 files) to see how it
defines labels and flags a wrong one — it has the same problem one channel
over (SMS instead of calls) and a much more mature "wrong label" system.

Mechanism found (`ai/scorer.py`, `ai/prefilter/tier1_phrases_v2.py`,
`ai/prefilter/label_validator.py`, `ai/prefilter/_guards.py`):

- **Deterministic phrase tier first, LLM only for what the tier can't
  decide.** A curated regex set per label (`_WRONG_NUMBER_PATTERNS`,
  `_NOT_THIS_PERSON_PATTERNS`, etc.) resolves the common, unambiguous cases
  for free; only the remainder goes to the LLM. Same shape as VOS's own
  3-layer rebuttal detection — this is the same idea, just applied to labels.
- **Explicit precedence between competing signals**, not "first match wins":
  *"DNC ALWAYS wins over Wrong Number"* is a literal comment in their Tier-1
  code — if a contact says both "wrong number" and an opt-out phrase, the
  actionable disposition is DNC, full stop, regardless of what else matched.
  A minor-disclosure rule beats Wrong Number too (compliance always wins).
- **Behavioral confirmation, not just keyword presence.** For Wrong Number
  specifically, they check what happens *after* the trigger phrase: did the
  agent keep pitching (`_AGENT_PITCH_AFTER_WN` patterns) with no reaction
  from the contact → real violation; did the contact re-engage afterward
  (gave an address, asked a question) → not a violation, that's correct
  funnel behavior. This is the part we are **not** copying yet — see Scope
  boundary below.
- **Defensible-alternative exceptions** (`is_defensible_alternative`): some
  disagreements are visibility, not error (e.g. DNC vs Not Interested with
  no explicit opt-out) — flagged at lower confidence instead of counted as a
  mistake. VOS doesn't have a confidence tier on this flag (plain Yes/No), so
  this maps to: keep the new phrase lists narrow/literal rather than modeling
  "sort of defensible" cases.
- **A label whitelist** so the AI's "should be" guess can't be a hallucinated
  disposition. VOS doesn't need this — dispositions come from each dialer's
  free-text CSV, there's no fixed enum to validate against, and the new
  checks never invent a "should be" value, only a Yes/No.

## Options considered

1. **Build the same tiered ML/LLM pipeline.** Effort XL, massive overkill for
   two dispositions and a single Yes/No flag column. Rejected.
2. **Generic rule-engine abstraction** (list of `{phrases, correct_dispo}`
   rule objects) so future dispositions are a one-line add. Rejected per
   "don't add premature abstraction for three things" — three explicit,
   readable checks in one function body are fine and match the file's
   existing style.
3. **Extend `wrong_dispo_detection()` in place with two more literal phrase
   checks**, mirroring the DNC check's own shape and reusing its
   `_normalize()` / dash-handling. Effort S, same precision-first philosophy
   as the original plan. **Chosen.**

## Solution

Two new checks, same "unambiguous phrase only" posture as the DNC check —
false positives are the expensive failure mode here (false accusation),
false negatives are cheap (silent miss, same as today).

### Check 2 — Wrong Number
`WRONG_NUMBER_PHRASES`: literal identity/ownership denial only ("wrong
number", "wrong person", "not my number", "i dont own this
house/property", "im not the owner", "you have the wrong
number/person") — deliberately excludes softer things like "wrong address"
(could just be a mailing-address correction from the same owner, not an
identity denial).

Fires when a Wrong Number phrase is present **and** the disposition is
neither "Wrong Number" **nor** "DNC - Decision Maker" — the second
exclusion is the sibling project's "DNC always wins over Wrong Number" rule,
reused directly: if the transcript has both signals, DNC is the stricter,
correct disposition and Wrong Number isn't the miss to flag.

### Check 3 — Decision Maker - NYI used as a dumping ground
`NYI_CONTRADICTION_PHRASES`: literal, unambiguous acceptance/commitment
phrases that contradict "not yet interested" ("yes im interested", "i want
to sell", "send me the offer/contract", "lets move forward", "when can we
close/sign", "i accept the offer").

Fires only when the disposition normalizes to "Decision Maker - NYI"
specifically **and** one of these phrases is present. (The DNC-contradicts-
NYI direction is already covered by Check 1 — any non-DNC disposition,
including NYI, already gets flagged there.)

### Not changing

- Function signature: `wrong_dispo_detection(transcript, disposition) ->
  "Yes"/"No"`. Same two args, same return shape.
- Every call site already wired in the first Wrong Dispo pass (the per-call
  result dict in `audio_pipeline/audio_processor.py` /
  `processing/batch_engine.py`, `dashboard_manager.py`, dashboard_service,
  webapp types/utils/pages/dashboards). **Zero other files need to
  change** — this is the payoff of having kept the flag a single pure
  function with one `"Wrong Dispo Detection"` column everywhere.

## Scope boundary — not included unless you want it

- **No behavioral/after-the-fact analysis** (did the agent keep pitching
  after a Wrong Number claim, did the contact re-engage). That needs
  message-by-message timeline parsing the current transcript string doesn't
  cleanly give us at this layer, and it's the part of the sibling project
  most prone to needing tuning over time. Flag it if real calls show agents
  gaming Wrong Number this way (claiming wrong number mid-call, then
  continuing to pitch) — the literal phrase-presence check above can't catch
  that direction at all.
- **Still Actions/Call Review only**, not the 5-sample Scoring majority
  vote / company sheet — same reasoning as the original plan: every sample
  that pipeline ever sees is already Wrong Number or NYI by construction
  (`SCORING_DISPOSITIONS`), so wiring in there is a separate, bigger
  decision (new scoring column, majority-vote rule, MOP sheet mapping), not
  a side effect of widening the phrase lists.
- **No "should be X" reason text.** Every other heavy-audit flag in VOS
  (Releasing, Late Hello, Rebuttal) is a plain Yes/No with no explanation
  column, so this stays consistent rather than becoming the one flag with
  prose attached.

## Files

- `lib/wrong_dispo_detector.py` — add `WRONG_NUMBER_PHRASES`,
  `NYI_CONTRADICTION_PHRASES`, `_is_wrong_number()` /
  `_is_decision_maker_nyi()` helpers (same shape as `_is_dnc_decision_maker`),
  and the two new checks inside `wrong_dispo_detection()`.
- `tests/test_wrong_dispo_detector.py` — add hit/miss cases for both new
  checks, plus the DNC-wins-over-Wrong-Number precedence case and the
  NYI-exact-match (not "any non-NYI") case.

## Verification

- Unit tests: phrase hits/misses for both new checks, the DNC-over-Wrong-
  Number precedence case, NYI contradiction only fires when disposition is
  actually NYI (not e.g. "Decision Maker").
- Full existing suite still green (confirms nothing in the untouched 40+
  other tests regressed).
- `tsc -b` not needed — no frontend files touched.

## Risk

Same shape as the original: phrase lists under-match unseen phrasing (silent
miss, safe direction). The one new risk worth naming: "wrong number" /
"wrong person" said in a context that isn't actually an identity denial is
rare but not impossible — accepted, matches the precision-first posture
already chosen for this flag. Widen or narrow the lists as real audited
calls show hits or misses.
